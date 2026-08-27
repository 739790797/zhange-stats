"""Pelican Panel Client API（与网页同一套入口：power / files）。

不直连 Wings。Base URL 填 Panel 根地址。
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import Any

from app.core.http_client import HttpRequestError, http_request

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
LONG_TIMEOUT = 120.0
USER_AGENT = "zhange-stats-pelican/1.0"


class PelicanError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_pelican_base_url(base_url: str) -> str:
    root = (base_url or "").strip().rstrip("/")
    if not root:
        return ""
    lower = root.lower()
    for suffix in ("/api/client", "/api"):
        if lower.endswith(suffix):
            root = root[: -len(suffix)].rstrip("/")
            lower = root.lower()
    return root


def normalize_server_uuid(value: str) -> str:
    text = (value or "").strip()
    return text


def pelican_configured(base_url: str, token: str, server_uuid: str) -> bool:
    return bool(
        normalize_pelican_base_url(base_url)
        and (token or "").strip()
        and normalize_server_uuid(server_uuid)
    )


def normalize_remote_directory(path: str) -> str:
    text = (path or "/").replace("\\", "/").strip() or "/"
    if not text.startswith("/"):
        text = f"/{text}"
    parts: list[str] = []
    for part in text.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            raise PelicanError("路径不合法")
        parts.append(part)
    return "/" + "/".join(parts) if parts else "/"


def normalize_remote_file_path(path: str) -> str:
    full = normalize_remote_directory(path)
    if full == "/":
        raise PelicanError("文件路径为空")
    return full


def split_remote_path(path: str) -> tuple[str, str]:
    full = normalize_remote_file_path(path)
    parent, _, name = full.rpartition("/")
    if not name:
        raise PelicanError("文件路径为空")
    return (parent or "/"), name


def join_remote_path(directory: str, name: str) -> str:
    base = sanitize_filename(name)
    root = normalize_remote_directory(directory)
    return f"{root}/{base}" if root != "/" else f"/{base}"


def sanitize_filename(name: str, *, allow_path: bool = False) -> str:
    text = (name or "").replace("\\", "/").strip()
    if allow_path:
        text = text.rsplit("/", 1)[-1].strip()
    elif "/" in text:
        raise PelicanError("文件名不合法")
    if not text or text in {".", ".."} or "\x00" in text:
        raise PelicanError("文件名不合法")
    return text


def normalize_rename_target(value: str) -> str:
    text = (value or "").replace("\\", "/").strip().lstrip("/")
    parts = [p for p in text.split("/") if p and p != "."]
    if not parts or any(p == ".." for p in parts) or any("\x00" in p for p in parts):
        raise PelicanError("目标路径不合法")
    return "/".join(parts)


def _headers(token: str, *, content_type: str | None = "application/json") -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {(token or '').strip()}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _server_root(base_url: str, server_uuid: str) -> str:
    root = normalize_pelican_base_url(base_url)
    ident = normalize_server_uuid(server_uuid)
    if not root or not ident:
        raise PelicanError("未配置 Pelican（请在集成密钥中填写 Panel 地址、Client Token 与 Server UUID）")
    return f"{root}/api/client/servers/{urllib.parse.quote(ident, safe='-')}"


def _read_error_body(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:300]
    errors = data.get("errors") if isinstance(data, dict) else None
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            detail = first.get("detail") or first.get("code") or ""
            if detail:
                return str(detail)
    if isinstance(data, dict) and data.get("message"):
        return str(data["message"])
    return raw[:300]


def friendly_error(status_code: int, detail: str) -> str:
    text = (detail or "").lower()
    if status_code == 403 and "application api key" in text and "client api key" in text:
        return (
            "填的是 Application API Key，这里需要 Client API Key。"
            "请到 Pelican 右上角账号 → API Credentials 新建一把（权限含 console、files 与 power），"
            "不要用管理后台 Application API。"
        )
    if status_code == 401:
        return "Token 无效或已撤销，请重新创建 Client API Key。"
    if status_code == 404:
        return "找不到这台服，请核对 Server UUID，并确认该 Client Key 所属账号能看到这台服。"
    msg = f"Pelican HTTP {status_code}"
    if detail:
        return f"{msg}：{detail}"
    return msg


def is_absent_file_error(exc: PelicanError) -> bool:
    """Wings/Panel 常把缺文件、读目录当成 400/404，或包成通用 500。"""
    return exc.status_code in {400, 404, 500}


def _request(
    method: str,
    url: str,
    token: str,
    *,
    json_body: dict[str, Any] | None = None,
    raw_body: bytes | None = None,
    content_type: str | None = "application/json",
    timeout: float = DEFAULT_TIMEOUT,
    decode: str = "auto",
) -> Any:
    data: bytes | None = None
    headers = _headers(token, content_type=content_type)
    if raw_body is not None:
        data = raw_body
    elif json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
    try:
        resp = http_request(
            method, url, headers=headers, content=data, timeout=timeout
        )
        payload = resp.content
        if resp.status_code >= 400:
            detail = _read_error_body(payload.decode("utf-8", errors="replace"))
            raise PelicanError(
                friendly_error(resp.status_code, detail),
                status_code=resp.status_code,
            )
        if decode == "bytes":
            return payload
        if not payload:
            return "" if decode == "text" else None
        text = payload.decode("utf-8", errors="replace")
        if decode == "text":
            return text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    except PelicanError:
        raise
    except HttpRequestError as exc:
        msg = str(exc)
        if "超时" in msg:
            raise PelicanError("连接 Pelican 超时") from exc
        raise PelicanError(f"无法连接 Pelican：{exc}") from exc


def get_server(base_url: str, token: str, server_uuid: str) -> dict[str, Any]:
    url = _server_root(base_url, server_uuid)
    data = _request("GET", url, token)
    if not isinstance(data, dict):
        raise PelicanError("Pelican 返回的服务器信息无效")
    return data


def get_resources(base_url: str, token: str, server_uuid: str) -> dict[str, Any]:
    url = f"{_server_root(base_url, server_uuid)}/resources"
    data = _request("GET", url, token)
    if not isinstance(data, dict):
        raise PelicanError("Pelican 返回的资源信息无效")
    return data


def power_state_from_resources(data: dict[str, Any]) -> str:
    attrs = data.get("attributes") if isinstance(data, dict) else None
    if not isinstance(attrs, dict):
        return "unknown"
    state = str(attrs.get("current_state") or "").strip().lower()
    return state or "unknown"


def send_power(
    base_url: str,
    token: str,
    server_uuid: str,
    signal: str,
) -> None:
    allowed = {"start", "stop", "restart", "kill"}
    sig = (signal or "").strip().lower()
    if sig not in allowed:
        raise PelicanError("无效的电源信号")
    url = f"{_server_root(base_url, server_uuid)}/power"
    _request("POST", url, token, json_body={"signal": sig})


def get_startup(base_url: str, token: str, server_uuid: str) -> dict[str, Any]:
    url = f"{_server_root(base_url, server_uuid)}/startup"
    data = _request("GET", url, token)
    return data if isinstance(data, dict) else {}


def startup_command(data: dict[str, Any]) -> str:
    inner = data.get("data") if isinstance(data, dict) else None
    # Pelican/Pterodactyl 有时直接 attributes，有时 data.attributes
    if isinstance(inner, dict):
        attrs = inner.get("attributes") if isinstance(inner.get("attributes"), dict) else inner
        if isinstance(attrs, dict):
            cmd = attrs.get("startup_command") or attrs.get("command") or ""
            if cmd:
                return str(cmd)
    attrs = data.get("attributes") if isinstance(data, dict) else None
    if isinstance(attrs, dict):
        return str(attrs.get("startup_command") or attrs.get("command") or "")
    meta = data.get("meta") if isinstance(data, dict) else None
    if isinstance(meta, dict):
        return str(meta.get("startup_command") or "")
    return ""


def parse_file_object(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else row
    if not isinstance(attrs, dict):
        return None
    name = str(attrs.get("name") or "")
    if not name:
        return None
    if "is_file" in attrs:
        is_file = bool(attrs.get("is_file"))
    elif "file" in attrs:
        is_file = bool(attrs.get("file"))
    else:
        is_file = True
    try:
        size = int(attrs.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    created = str(attrs.get("created_at") or "").strip() or None
    modified = str(attrs.get("modified_at") or "").strip() or None
    return {
        "name": name,
        "is_file": is_file,
        "is_symlink": bool(attrs.get("is_symlink", False)),
        "size": size,
        "mode": str(attrs.get("mode") or ""),
        "mode_bits": str(attrs.get("mode_bits") or ""),
        "mimetype": str(attrs.get("mimetype") or ""),
        "created_at": created,
        "modified_at": modified,
    }


def list_files(
    base_url: str,
    token: str,
    server_uuid: str,
    directory: str,
) -> list[dict[str, Any]]:
    directory = normalize_remote_directory(directory)
    q = urllib.parse.urlencode({"directory": directory})
    url = f"{_server_root(base_url, server_uuid)}/files/list?{q}"
    data = _request("GET", url, token)
    if not isinstance(data, dict):
        return []
    rows = data.get("data")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        parsed = parse_file_object(row)
        if parsed:
            out.append(parsed)
    return out


def get_file_contents(
    base_url: str,
    token: str,
    server_uuid: str,
    path: str,
) -> str:
    rel = normalize_remote_file_path(path)
    q = urllib.parse.urlencode({"file": rel})
    url = f"{_server_root(base_url, server_uuid)}/files/contents?{q}"
    text = _request("GET", url, token, decode="text")
    return text if isinstance(text, str) else ""


def get_download_url(
    base_url: str,
    token: str,
    server_uuid: str,
    path: str,
) -> str:
    rel = normalize_remote_file_path(path)
    q = urllib.parse.urlencode({"file": rel})
    url = f"{_server_root(base_url, server_uuid)}/files/download?{q}"
    data = _request("GET", url, token)
    if not isinstance(data, dict):
        raise PelicanError("Pelican 未返回下载地址")
    attrs = data.get("attributes") if isinstance(data.get("attributes"), dict) else data
    signed = str(attrs.get("url") or "").strip() if isinstance(attrs, dict) else ""
    if not signed:
        raise PelicanError("Pelican 未返回下载地址")
    return signed


def download_file(
    base_url: str,
    token: str,
    server_uuid: str,
    path: str,
    *,
    max_bytes: int,
    timeout: float = LONG_TIMEOUT,
) -> bytes:
    """经签名 URL 拉二进制（jar）；不要走 files/contents，那是给文本编辑用的。"""
    if max_bytes <= 0:
        raise PelicanError("下载大小限制不合法")
    signed = get_download_url(base_url, token, server_uuid, path)
    try:
        resp = http_request(
            "GET",
            signed,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            timeout=timeout,
        )
    except HttpRequestError as exc:
        raise PelicanError(f"下载失败：{exc}") from exc
    if resp.status_code >= 400:
        detail = resp.content.decode("utf-8", errors="replace")[:300]
        raise PelicanError(friendly_error(resp.status_code, detail), status_code=resp.status_code)
    try:
        content_length = int(resp.headers.get("content-length") or 0)
    except (TypeError, ValueError):
        content_length = 0
    if content_length > max_bytes:
        raise PelicanError("文件过大，无法读取模组信息")
    data = resp.content
    if len(data) > max_bytes:
        raise PelicanError("文件过大，无法读取模组信息")
    return data


def rename_files(
    base_url: str,
    token: str,
    server_uuid: str,
    *,
    root: str,
    files: list[tuple[str, str]],
) -> None:
    directory = normalize_remote_directory(root)
    payload = []
    for src, dest in files:
        frm = sanitize_filename(src) if "/" not in (src or "").replace("\\", "/") else split_remote_path(src)[1]
        payload.append({"from": frm, "to": normalize_rename_target(dest)})
    if not payload:
        return
    url = f"{_server_root(base_url, server_uuid)}/files/rename"
    _request("PUT", url, token, json_body={"root": directory, "files": payload})


def copy_file(
    base_url: str,
    token: str,
    server_uuid: str,
    path: str,
) -> None:
    loc = normalize_remote_file_path(path)
    url = f"{_server_root(base_url, server_uuid)}/files/copy"
    _request("POST", url, token, json_body={"location": loc})


def compress_files(
    base_url: str,
    token: str,
    server_uuid: str,
    *,
    root: str,
    files: list[str],
    name: str | None = None,
    extension: str | None = None,
) -> dict[str, Any] | None:
    names = [sanitize_filename(n) for n in files if n]
    if not names:
        raise PelicanError("请选择要压缩的文件")
    directory = normalize_remote_directory(root)
    body: dict[str, Any] = {"root": directory, "files": names}
    if name and str(name).strip():
        body["name"] = sanitize_filename(str(name).strip())
    ext = (extension or "").strip().lower()
    if ext:
        body["extension"] = ext
    url = f"{_server_root(base_url, server_uuid)}/files/compress"
    data = _request("POST", url, token, json_body=body, timeout=LONG_TIMEOUT)
    if not isinstance(data, dict):
        return None
    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    return parse_file_object(inner)


def decompress_file(
    base_url: str,
    token: str,
    server_uuid: str,
    *,
    root: str,
    name: str,
) -> None:
    directory = normalize_remote_directory(root)
    filename = sanitize_filename(name)
    url = f"{_server_root(base_url, server_uuid)}/files/decompress"
    _request(
        "POST",
        url,
        token,
        json_body={"root": directory, "file": filename},
        timeout=LONG_TIMEOUT,
    )


def write_file(
    base_url: str,
    token: str,
    server_uuid: str,
    path: str,
    content: str | bytes,
    *,
    timeout: float = LONG_TIMEOUT,
) -> None:
    rel = normalize_remote_file_path(path)
    q = urllib.parse.urlencode({"file": rel})
    url = f"{_server_root(base_url, server_uuid)}/files/write?{q}"
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    _request(
        "POST",
        url,
        token,
        raw_body=raw,
        content_type="text/plain",
        timeout=timeout,
    )


def pull_file(
    base_url: str,
    token: str,
    server_uuid: str,
    *,
    url: str,
    directory: str,
    filename: str,
    timeout: float = LONG_TIMEOUT,
) -> None:
    endpoint = f"{_server_root(base_url, server_uuid)}/files/pull"
    directory = normalize_remote_directory(directory)
    _request(
        "POST",
        endpoint,
        token,
        json_body={
            "url": url,
            "directory": directory,
            "filename": sanitize_filename(filename),
            "use_header": False,
            "foreground": True,
        },
        timeout=timeout,
    )


def delete_files(
    base_url: str,
    token: str,
    server_uuid: str,
    *,
    root: str,
    files: list[str],
) -> None:
    names = [sanitize_filename(n) for n in files if n]
    if not names:
        return
    directory = normalize_remote_directory(root)
    url = f"{_server_root(base_url, server_uuid)}/files/delete"
    _request(
        "POST",
        url,
        token,
        json_body={"root": directory, "files": names},
    )


def chmod_files(
    base_url: str,
    token: str,
    server_uuid: str,
    *,
    root: str,
    files: list[dict[str, str]],
) -> None:
    directory = normalize_remote_directory(root)
    payload: list[dict[str, str]] = []
    for row in files:
        name = sanitize_filename(str(row.get("file") or ""))
        mode = str(row.get("mode") or "").strip()
        if not name or not mode:
            continue
        payload.append({"file": name, "mode": mode})
    if not payload:
        raise PelicanError("没有可修改权限的文件")
    url = f"{_server_root(base_url, server_uuid)}/files/chmod"
    _request(
        "POST",
        url,
        token,
        json_body={"root": directory, "files": payload},
    )


def chmod_file(
    base_url: str,
    token: str,
    server_uuid: str,
    path: str,
    mode: str = "0755",
) -> None:
    directory, name = split_remote_path(path)
    chmod_files(
        base_url,
        token,
        server_uuid,
        root=directory,
        files=[{"file": name, "mode": mode}],
    )


def create_folder(
    base_url: str,
    token: str,
    server_uuid: str,
    *,
    root: str,
    name: str,
    ignore_exists: bool = True,
) -> None:
    url = f"{_server_root(base_url, server_uuid)}/files/create-folder"
    directory = normalize_remote_directory(root)
    folder = sanitize_filename(name)
    try:
        _request(
            "POST",
            url,
            token,
            json_body={"root": directory, "name": folder},
        )
    except PelicanError as exc:
        # 已存在时部分面板返回 400，开服编排忽略；文件管理要提示
        if ignore_exists and exc.status_code in {400, 409, 422}:
            logger.debug("create-folder %s/%s: %s", directory, folder, exc)
            return
        raise


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_server_meta(data: Any) -> dict[str, Any]:
    """Pelican GET /servers/{uuid}：名称、默认 allocation、资源上限。"""
    if not isinstance(data, dict):
        return {
            "name": "",
            "address": "",
            "memory_limit_mb": 0,
            "cpu_limit": 0,
            "disk_limit_mb": 0,
        }
    attrs = data.get("attributes") if isinstance(data.get("attributes"), dict) else {}
    name = str(attrs.get("name") or "")
    limits = attrs.get("limits") if isinstance(attrs.get("limits"), dict) else {}
    rel = data.get("relationships") if isinstance(data.get("relationships"), dict) else {}
    if not rel:
        rel = attrs.get("relationships") if isinstance(attrs.get("relationships"), dict) else {}
    alloc_block = rel.get("allocations") if isinstance(rel, dict) else None
    rows = alloc_block.get("data") if isinstance(alloc_block, dict) else None
    host = ""
    port = 0
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = row.get("attributes") if isinstance(row.get("attributes"), dict) else row
            alias = str(item.get("ip_alias") or "").strip()
            ip = str(item.get("ip") or "").strip()
            p = _as_int(item.get("port"))
            chosen = alias or ip
            if not chosen:
                continue
            is_default = bool(item.get("is_default") or item.get("default"))
            if is_default or not host:
                host = chosen
                port = p
                if is_default:
                    break
    address = f"{host}:{port}" if host and port else host
    return {
        "name": name,
        "address": address,
        "memory_limit_mb": _as_int(limits.get("memory")),
        "cpu_limit": _as_int(limits.get("cpu")),
        "disk_limit_mb": _as_int(limits.get("disk")),
    }


def parse_websocket_credentials(data: Any) -> tuple[str, str]:
    if not isinstance(data, dict):
        raise PelicanError("Pelican 返回的控制台凭证无效")
    inner = data.get("data")
    if isinstance(inner, dict) and isinstance(inner.get("attributes"), dict):
        inner = inner["attributes"]
    elif not isinstance(inner, dict):
        inner = data.get("attributes") if isinstance(data.get("attributes"), dict) else data
    if not isinstance(inner, dict):
        raise PelicanError("Pelican 返回的控制台凭证无效")
    socket = str(inner.get("socket") or inner.get("socket_url") or "").strip()
    token = str(inner.get("token") or "").strip()
    if not socket or not token:
        raise PelicanError("Pelican 未返回控制台 websocket 地址")
    return socket, token


def get_websocket(base_url: str, token: str, server_uuid: str) -> tuple[str, str]:
    url = f"{_server_root(base_url, server_uuid)}/websocket"
    data = _request("GET", url, token)
    return parse_websocket_credentials(data)


def startup_details(data: dict[str, Any]) -> dict[str, Any]:
    """解析 GET /startup：命令、Docker 镜像、Egg 环境变量。"""
    command = startup_command(data)
    variables: list[dict[str, str]] = []
    rows = data.get("data")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else row
            if not isinstance(attrs, dict):
                continue
            key = str(attrs.get("env_variable") or attrs.get("env") or "").strip()
            if not key:
                continue
            variables.append(
                {
                    "key": key,
                    "name": str(attrs.get("name") or key),
                    "value": str(
                        attrs.get("server_value")
                        if attrs.get("server_value") is not None
                        else attrs.get("default_value")
                        or ""
                    ),
                }
            )
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    images = meta.get("docker_images")
    docker_images: list[str] = []
    if isinstance(images, dict):
        docker_images = [str(v) for v in images.values() if v]
    elif isinstance(images, list):
        docker_images = [str(v) for v in images if v]
    image = str(meta.get("docker_image") or meta.get("image") or "")
    if image and image not in docker_images:
        docker_images.insert(0, image)
    return {
        "command": command,
        "docker_images": docker_images,
        "variables": variables,
    }


def update_startup_variable(
    base_url: str,
    token: str,
    server_uuid: str,
    key: str,
    value: str,
) -> None:
    env_key = (key or "").strip()
    if not env_key:
        raise PelicanError("启动变量名为空")
    url = f"{_server_root(base_url, server_uuid)}/startup/variable"
    _request(
        "PUT",
        url,
        token,
        json_body={"key": env_key, "value": str(value or "")},
    )


def parse_application_server(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "id": 0,
            "uuid": "",
            "egg_id": 0,
            "startup": "",
            "image": "",
            "environment": {},
        }
    attrs = data.get("attributes") if isinstance(data.get("attributes"), dict) else data
    if not isinstance(attrs, dict):
        attrs = {}
    container = attrs.get("container") if isinstance(attrs.get("container"), dict) else {}
    env_raw = container.get("environment") if isinstance(container.get("environment"), dict) else {}
    environment = {
        str(key): "" if value is None else str(value) for key, value in env_raw.items()
    }
    return {
        "id": _as_int(attrs.get("id")),
        "uuid": str(attrs.get("uuid") or ""),
        "egg_id": _as_int(attrs.get("egg")),
        "startup": str(container.get("startup_command") or attrs.get("startup") or ""),
        "image": str(container.get("image") or ""),
        "environment": environment,
    }
