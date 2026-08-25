"""Pelican Panel Client API（与网页同一套入口：power / files）。

不直连 Wings。Base URL 填 Panel 根地址。
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

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


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""
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
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
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
    except urllib.error.HTTPError as exc:
        detail = _read_error_body(exc)
        raise PelicanError(friendly_error(exc.code, detail), status_code=exc.code) from exc
    except urllib.error.URLError as exc:
        raise PelicanError(f"无法连接 Pelican：{exc.reason}") from exc
    except TimeoutError as exc:
        raise PelicanError("连接 Pelican 超时") from exc


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


def _application_root(base_url: str) -> str:
    root = normalize_pelican_base_url(base_url)
    if not root:
        raise PelicanError("未配置 Pelican Panel 地址")
    return f"{root}/api/application"


def parse_internal_id(data: Any) -> int:
    if not isinstance(data, dict):
        return 0
    attrs = data.get("attributes") if isinstance(data.get("attributes"), dict) else data
    if not isinstance(attrs, dict):
        return 0
    return _as_int(attrs.get("internal_id") or attrs.get("id"))


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


def get_application_server(
    base_url: str,
    application_token: str,
    server_id: int,
) -> dict[str, Any]:
    url = f"{_application_root(base_url)}/servers/{int(server_id)}"
    data = _request("GET", url, application_token)
    parsed = parse_application_server(data)
    if not parsed.get("id"):
        raise PelicanError("Pelican 未返回 Application 服务器")
    return parsed


def find_application_server(
    base_url: str,
    application_token: str,
    server_uuid: str,
) -> dict[str, Any] | None:
    ident = normalize_server_uuid(server_uuid)
    if not ident:
        return None
    for key, value in (("uuid", ident), ("uuid_short", ident)):
        q = urllib.parse.urlencode({f"filter[{key}]": value, "per_page": "1"})
        url = f"{_application_root(base_url)}/servers?{q}"
        data = _request("GET", url, application_token)
        if not isinstance(data, dict):
            continue
        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            continue
        parsed = parse_application_server(rows[0])
        if parsed.get("id"):
            return parsed
    return None


def update_application_startup(
    base_url: str,
    application_token: str,
    server_id: int,
    *,
    startup: str,
    environment: dict[str, str],
    egg_id: int,
    image: str,
    skip_scripts: bool = True,
) -> dict[str, Any]:
    url = f"{_application_root(base_url)}/servers/{int(server_id)}/startup"
    data = _request(
        "PATCH",
        url,
        application_token,
        json_body={
            "startup": startup,
            "environment": environment,
            "egg": int(egg_id),
            "image": image,
            "skip_scripts": bool(skip_scripts),
        },
    )
    return parse_application_server(data) if isinstance(data, dict) else {}


def get_application_egg(
    base_url: str,
    application_token: str,
    egg_id: int,
) -> dict[str, Any]:
    url = f"{_application_root(base_url)}/eggs/{int(egg_id)}?include=variables"
    data = _request("GET", url, application_token)
    return data if isinstance(data, dict) else {}


def parse_egg_variable_defaults(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    rel = data.get("relationships") if isinstance(data.get("relationships"), dict) else {}
    attrs = data.get("attributes") if isinstance(data.get("attributes"), dict) else {}
    if not rel and isinstance(attrs.get("relationships"), dict):
        rel = attrs["relationships"]
    block = rel.get("variables") if isinstance(rel, dict) else None
    rows = block.get("data") if isinstance(block, dict) else None
    if not isinstance(rows, list):
        return {}
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = row.get("attributes") if isinstance(row.get("attributes"), dict) else row
        if not isinstance(item, dict):
            continue
        key = str(item.get("env_variable") or item.get("env") or "").strip()
        if not key:
            continue
        default = item.get("default_value")
        out[key] = "" if default is None else str(default)
    return out


def parse_egg_startup_and_image(data: Any) -> tuple[str, str]:
    if not isinstance(data, dict):
        return "", ""
    attrs = data.get("attributes") if isinstance(data.get("attributes"), dict) else data
    if not isinstance(attrs, dict):
        return "", ""
    startup = str(attrs.get("startup") or "")
    commands = attrs.get("startup_commands")
    if not startup and isinstance(commands, dict):
        startup = str(next(iter(commands.values()), "") or "")
    elif not startup and isinstance(commands, list) and commands:
        startup = str(commands[0] or "")
    docker = attrs.get("docker_images")
    image = ""
    if isinstance(docker, dict) and docker:
        image = str(next(iter(docker.values()), "") or "")
    elif isinstance(docker, list) and docker:
        image = str(docker[0] or "")
    if not image:
        image = str(attrs.get("docker_image") or "")
    return startup, image


def list_application_eggs(base_url: str, application_token: str) -> list[dict[str, Any]]:
    """用 Application API 列出 Nest 下全部 Egg（用于匹配 Minecraft 加载器）。"""
    token = (application_token or "").strip()
    if not token:
        return []
    url = f"{_application_root(base_url)}/nests?include=eggs&per_page=100"
    data = _request("GET", url, token)
    if not isinstance(data, dict):
        return []
    nests = data.get("data")
    if not isinstance(nests, list):
        return []
    out: list[dict[str, Any]] = []
    for nest in nests:
        if not isinstance(nest, dict):
            continue
        nest_attrs = (
            nest.get("attributes") if isinstance(nest.get("attributes"), dict) else nest
        )
        nest_name = str(nest_attrs.get("name") or "")
        nest_id = nest_attrs.get("id")
        rel = nest.get("relationships") if isinstance(nest.get("relationships"), dict) else {}
        if not rel and isinstance(nest_attrs, dict):
            rel = nest_attrs.get("relationships") if isinstance(nest_attrs.get("relationships"), dict) else {}
        eggs_block = rel.get("eggs") if isinstance(rel, dict) else None
        eggs = eggs_block.get("data") if isinstance(eggs_block, dict) else None
        if not isinstance(eggs, list):
            continue
        for egg in eggs:
            if not isinstance(egg, dict):
                continue
            attrs = egg.get("attributes") if isinstance(egg.get("attributes"), dict) else egg
            if not isinstance(attrs, dict):
                continue
            docker = attrs.get("docker_images")
            images: list[str] = []
            if isinstance(docker, dict):
                images = [str(v) for v in docker.values() if v]
            elif isinstance(docker, list):
                images = [str(v) for v in docker if v]
            try:
                parsed_egg_id = int(attrs.get("id")) if attrs.get("id") is not None else None
            except (TypeError, ValueError):
                parsed_egg_id = None
            try:
                parsed_nest_id = int(nest_id) if nest_id is not None else None
            except (TypeError, ValueError):
                parsed_nest_id = None
            out.append(
                {
                    "egg_id": parsed_egg_id,
                    "uuid": str(attrs.get("uuid") or ""),
                    "name": str(attrs.get("name") or ""),
                    "description": str(attrs.get("description") or ""),
                    "nest": nest_name,
                    "nest_id": parsed_nest_id,
                    "docker_images": images,
                    "startup": str(attrs.get("startup") or ""),
                }
            )
    return out
