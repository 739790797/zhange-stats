"""MAA Worker：槽位 Docker 生命周期、对账、截图与日常任务。"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from PIL import Image

from docker_ops import DockerOps, DockerOpsError

LOG = logging.getLogger("maa-worker")

APP_BASE_URL = os.environ.get("MAA_APP_BASE_URL", "http://app:8000").rstrip("/")
WORKER_TOKEN = os.environ.get("MAA_WORKER_TOKEN", "").strip()
DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
POLL_INTERVAL = float(os.environ.get("MAA_WORKER_POLL_SEC", "5"))
ADB_READY_ATTEMPTS = int(os.environ.get("MAA_ADB_READY_ATTEMPTS", "2"))
ADB_READY_DELAY = float(os.environ.get("MAA_ADB_READY_DELAY_SEC", "2"))
# 单次 wait 未就绪时保持 provisioning 并重试；超过轮次才 error
# 每轮仅短等 ADB，避免长时间卡住无法处理销毁等动作
PROVISION_MAX_ROUNDS = int(os.environ.get("MAA_PROVISION_MAX_ROUNDS", "60"))
REDROID_IMAGE = os.environ.get(
    "MAA_REDROID_IMAGE", "redroid/redroid:11.0.0-latest"
)
DOCKER_NETWORK = os.environ.get("MAA_DOCKER_NETWORK", "zhange-stats_maa")
MAA_CLI = os.environ.get("MAA_CLI_PATH", "maa")
ADB_PATH = os.environ.get("ADB_PATH", "adb")
SCREENSHOT_INTERVAL = float(os.environ.get("MAA_SCREENSHOT_INTERVAL_SEC", "15"))

# 进程内：slot_id → 已尝试等待轮次（避免 ADB 慢启动被标成 error）
_provision_rounds: dict[int, int] = {}

# 供给步骤（写入 last_error 供管理端展示；细节进 runtime.log）
PROVISION_STEPS: dict[int, str] = {
    1: "环境检测",
    2: "创建容器",
    3: "等待 Android",
    4: "连接 ADB",
    5: "完成就绪",
}
PROVISION_STEP_TOTAL = len(PROVISION_STEPS)

# Windows：避免 adb/maa-cli 子进程弹出黑色控制台窗口
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def provision_progress(step: int, text: str = "") -> str:
    """精简进度/报错：`[2/5 创建容器] …`。"""
    name = PROVISION_STEPS.get(step, f"步骤{step}")
    head = f"[{step}/{PROVISION_STEP_TOTAL} {name}]"
    text = (text or "").strip()
    return f"{head} {text}".strip() if text else head


def _short_err(msg: str, *, limit: int = 80) -> str:
    one = " ".join((msg or "").split())
    if len(one) <= limit:
        return one
    return one[: limit - 1] + "…"


def _run(cmd: list[str], **kwargs):
    """subprocess.run 包装：Windows 下不弹控制台。"""
    if _CREATE_NO_WINDOW and "creationflags" not in kwargs:
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)


def _headers() -> dict[str, str]:
    return {"X-Maa-Worker-Token": WORKER_TOKEN}


def pull_state(client: httpx.Client) -> dict:
    r = client.get(f"{APP_BASE_URL}/api/internal/maa/pull", headers=_headers())
    r.raise_for_status()
    return r.json()


def heartbeat(client: httpx.Client, payload: dict) -> None:
    r = client.post(
        f"{APP_BASE_URL}/api/internal/maa/heartbeat",
        headers=_headers(),
        json=payload,
    )
    r.raise_for_status()


def update_job(client: httpx.Client, job_id: int, status: str, error: str | None = None) -> None:
    r = client.post(
        f"{APP_BASE_URL}/api/internal/maa/jobs/update",
        headers=_headers(),
        json={"job_id": job_id, "status": status, "error": error},
    )
    r.raise_for_status()


def save_screenshot(slot_id: int, png_bytes: bytes) -> str:
    rel = f"maa/{slot_id}/latest.jpg"
    out = DATA_DIR / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.jpg")
    from io import BytesIO

    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > 720:
        scale = 720 / long_side
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    img.save(tmp, format="JPEG", quality=75, optimize=True)
    tmp.replace(out)
    return rel.replace("\\", "/")


def append_slot_log(slot_id: int, text: str) -> None:
    """写入槽位运行日志，供管理端查看。"""
    path = DATA_DIR / "maa" / str(slot_id) / "runtime.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    block = text if text.endswith("\n") else text + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {block}")
    # 限制体积：超过 ~256KB 截断保留尾部
    try:
        if path.stat().st_size > 256 * 1024:
            data = path.read_text(encoding="utf-8", errors="replace")
            path.write_text(data[-180_000:], encoding="utf-8")
    except OSError:
        pass


def refresh_slot_runtime_log(ops: DockerOps, slot: dict) -> None:
    sid = slot.get("id")
    name = slot.get("container_name")
    if not sid:
        return
    lines = [
        f"status={slot.get('status')} desired={slot.get('desired_action')} "
        f"adb={slot.get('adb_endpoint') or '-'}",
    ]
    err = (slot.get("last_error") or "").strip()
    if err:
        lines.append(f"last_error={err[:500]}")
    if name:
        boot = ops.android_boot_hint(name)
        lines.append(f"boot_hint={boot}")
        clog = ops.container_logs(name, tail=40).strip()
        if clog:
            lines.append("--- docker logs (tail) ---")
            lines.append(clog)
    append_slot_log(int(sid), "\n".join(lines) + "\n")


def adb_screencap(endpoint: str) -> bytes | None:
    if not endpoint:
        return None
    adb = _resolve_adb()
    if not adb:
        return None
    try:
        _run(
            [adb, "connect", endpoint],
            check=False,
            capture_output=True,
            timeout=15,
        )
        cap = _run(
            [adb, "-s", endpoint, "exec-out", "screencap", "-p"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        if cap.stdout[:8].startswith(b"\x89PNG") or b"PNG" in cap.stdout[:20]:
            return cap.stdout
        # 部分设备返回 CRLF 污染
        data = cap.stdout.replace(b"\r\n", b"\n")
        if data.startswith(b"\x89PNG"):
            return data
    except (subprocess.SubprocessError, OSError) as e:
        LOG.warning("screencap failed %s: %s", endpoint, e)
    return None


def capture_slot_png(
    ops: DockerOps, *, endpoint: str, container_name: str | None
) -> bytes | None:
    """优先 ADB；失败则尝试容器内 screencap（供给中也可能出图）。"""
    png = adb_screencap(endpoint)
    if png:
        return png
    if container_name:
        return ops.container_screencap(container_name)
    return None


def run_maa_daily(endpoint: str) -> tuple[bool, str]:
    """尝试 maa-cli；不可用时仅截图占位并返回提示。"""
    if shutil.which(MAA_CLI) or Path(MAA_CLI).exists():
        try:
            env = os.environ.copy()
            # maa-cli 连接地址因版本而异；优先环境变量透传
            env["MAA_CONNECTION_ADDRESS"] = endpoint
            proc = _run(
                [MAA_CLI, "run", "daily"],
                capture_output=True,
                text=True,
                timeout=3600,
                env=env,
            )
            if proc.returncode == 0:
                return True, "maa-cli daily ok"
            return False, (proc.stderr or proc.stdout or f"exit {proc.returncode}")[:2000]
        except (subprocess.SubprocessError, OSError) as e:
            return False, f"maa-cli error: {e}"
    return (
        False,
        "maa-cli 未安装：已记录任务失败。请在 Worker 镜像安装 maa-cli 后重试。",
    )


def handle_provision(ops: DockerOps, client: httpx.Client, slot: dict) -> None:
    """创建 Android 容器并自动上线到就绪（online）。未就绪时保持供给中并持续重试。"""
    slot_id = slot["id"]
    name = slot.get("container_name") or f"zhange-maa-slot-{slot_id}"
    volume = slot.get("volume_name") or f"zhange-maa-slot-{slot_id}-data"
    try:
        ops.ensure_network()
        heartbeat(
            client,
            {
                "slot_id": slot_id,
                "status": "provisioning",
                "desired_action": "provision",
                "clear_desired_action": False,
                "container_name": name,
                "volume_name": volume,
                "last_error": provision_progress(1, "检测 binder…"),
            },
        )
        binder_ok, binder_msg = ops.check_binder_support()
        if not binder_ok:
            short = "宿主机不支持 binder，请在 Linux 运行"
            LOG.error("binder unavailable slot=%s %s", slot_id, binder_msg)
            append_slot_log(slot_id, f"binder check failed: {binder_msg}")
            if ops.container_exists(name):
                ops.remove_container(name)
            _provision_rounds.pop(slot_id, None)
            heartbeat(
                client,
                {
                    "slot_id": slot_id,
                    "status": "error",
                    "clear_desired_action": True,
                    "container_name": name,
                    "volume_name": volume,
                    "last_error": provision_progress(1, short),
                    "audit_action": "provision_no_binder",
                    "audit_message": binder_msg[:2000],
                    "audit_result": "failed",
                },
            )
            return

        heartbeat(
            client,
            {
                "slot_id": slot_id,
                "status": "provisioning",
                "desired_action": "provision",
                "clear_desired_action": False,
                "container_name": name,
                "volume_name": volume,
                "last_error": provision_progress(2, "准备 Android 容器…"),
            },
        )
        # 重试时复用已有容器，避免反复 recreate 打断 Android 启动
        endpoint = ops.ensure_slot(
            name=name,
            volume=volume,
            image=REDROID_IMAGE,
        )
        ready, ready_msg = wait_adb_ready(
            endpoint, attempts=ADB_READY_ATTEMPTS, delay_sec=ADB_READY_DELAY
        )
        stats = ops.container_stats(name)
        boot_hint = ops.android_boot_hint(name)
        if not ready:
            rounds = _provision_rounds.get(slot_id, 0) + 1
            _provision_rounds[slot_id] = rounds
            boot_done = "boot=1" in boot_hint
            step = 4 if boot_done else 3
            wait_text = (
                f"第 {rounds}/{PROVISION_MAX_ROUNDS} 轮"
                if boot_done
                else f"第 {rounds}/{PROVISION_MAX_ROUNDS} 轮，系统启动中"
            )
            detail = f"{ready_msg}; {boot_hint}; round={rounds}/{PROVISION_MAX_ROUNDS}"
            LOG.warning("provision waiting ADB slot=%s %s", slot_id, detail)
            append_slot_log(slot_id, f"provision waiting: {detail}")
            if name:
                clog = ops.container_logs(name, tail=30).strip()
                if clog:
                    append_slot_log(slot_id, "docker logs:\n" + clog)
            if rounds >= PROVISION_MAX_ROUNDS:
                _provision_rounds.pop(slot_id, None)
                fail = (
                    "ADB 连接超时，详见日志"
                    if boot_done
                    else "Android 启动超时，详见日志"
                )
                heartbeat(
                    client,
                    {
                        "slot_id": slot_id,
                        "status": "error",
                        "clear_desired_action": True,
                        "container_name": name,
                        "volume_name": volume,
                        "adb_endpoint": endpoint,
                        "last_error": provision_progress(step, fail),
                        "cpu_percent": stats.get("cpu_percent") or "",
                        "memory_usage_mb": stats.get("memory_usage_mb") or "",
                        "audit_action": "provision_adb_not_ready",
                        "audit_message": detail[:2000],
                        "audit_result": "failed",
                    },
                )
                return
            # 保持 provisioning；勿覆盖可能已下发的 destroy
            payload: dict = {
                "slot_id": slot_id,
                "status": "provisioning",
                "desired_action": "provision",
                "clear_desired_action": False,
                "container_name": name,
                "volume_name": volume,
                "adb_endpoint": endpoint,
                "last_error": provision_progress(step, wait_text),
                "cpu_percent": stats.get("cpu_percent") or "",
                "memory_usage_mb": stats.get("memory_usage_mb") or "",
            }
            # ADB 未通时跳过截图，避免再卡几十秒
            heartbeat(client, payload)
            return
        _provision_rounds.pop(slot_id, None)
        maa_ok = bool(shutil.which(MAA_CLI) or Path(MAA_CLI).exists())
        maa_note = "maa-cli 可用" if maa_ok else "maa-cli 未安装（日常任务将失败，Android 已就绪）"
        ready_payload: dict = {
            "slot_id": slot_id,
            "status": "online",
            "clear_desired_action": True,
            "container_name": name,
            "volume_name": volume,
            "adb_endpoint": endpoint,
            "last_error": "" if maa_ok else provision_progress(5, "maa-cli 未安装"),
            "cpu_percent": stats.get("cpu_percent"),
            "memory_usage_mb": stats.get("memory_usage_mb"),
            "audit_action": "provision_ready",
            "audit_message": f"Android 已就绪（{endpoint}）；{maa_note}",
            "audit_result": "success",
        }
        png = capture_slot_png(ops, endpoint=endpoint, container_name=name)
        if png:
            ready_payload["screenshot_relpath"] = save_screenshot(slot_id, png)
        heartbeat(client, ready_payload)
    except DockerOpsError as e:
        LOG.exception("provision failed slot=%s", slot_id)
        _provision_rounds.pop(slot_id, None)
        raw = str(e)
        append_slot_log(slot_id, f"provision failed: {raw}")
        step = 1 if "binder" in raw.lower() else 2
        short = (
            "宿主机不支持 binder，请在 Linux 运行"
            if "binder" in raw.lower()
            else _short_err(raw)
        )
        heartbeat(
            client,
            {
                "slot_id": slot_id,
                "status": "error",
                "clear_desired_action": True,
                "last_error": provision_progress(step, short),
                "audit_action": "provision_failed",
                "audit_message": raw[:2000],
                "audit_result": "failed",
            },
        )


def wait_adb_ready(endpoint: str, *, attempts: int = 24, delay_sec: float = 5.0) -> tuple[bool, str]:
    """轮询 adb connect，确认设备在线。单次调用应短，便于 Worker 及时处理销毁。"""
    adb = _resolve_adb()
    if not adb:
        return False, "未找到 adb"
    last = "adb not tried"
    for i in range(max(1, attempts)):
        try:
            _run(
                [adb, "disconnect", endpoint],
                check=False,
                capture_output=True,
                timeout=3,
            )
            conn = _run(
                [adb, "connect", endpoint],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            proc = _run(
                [adb, "-s", endpoint, "get-state"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            state = (proc.stdout or "").strip().lower()
            conn_msg = (conn.stdout or conn.stderr or "").strip().replace("\n", " ")
            last = f"attempt={i + 1} state={state or (proc.stderr or '').strip()} conn={conn_msg}"
            if state == "device":
                return True, last
        except (subprocess.SubprocessError, OSError) as e:
            last = f"attempt={i + 1} error={e}"
        time.sleep(delay_sec)
    return False, f"ADB 未就绪: {last}"


def _resolve_adb() -> str | None:
    if shutil.which(ADB_PATH):
        return ADB_PATH
    if shutil.which("adb"):
        return "adb"
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "adb.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        Path(r"C:\Android\platform-tools\adb.exe"),
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    return None


def handle_start(ops: DockerOps, client: httpx.Client, slot: dict) -> None:
    name = slot.get("container_name")
    if not name:
        heartbeat(
            client,
            {
                "slot_id": slot["id"],
                "status": "error",
                "clear_desired_action": True,
                "last_error": "缺少 container_name",
                "audit_action": "start_failed",
                "audit_result": "failed",
                "audit_message": "缺少 container_name",
            },
        )
        return
    try:
        endpoint = ops.start_container(name)
        stats = ops.container_stats(name)
        ready, ready_msg = wait_adb_ready(
            endpoint, attempts=max(3, ADB_READY_ATTEMPTS // 2), delay_sec=ADB_READY_DELAY
        )
        if not ready:
            append_slot_log(slot["id"], f"start ADB not ready: {ready_msg}")
            heartbeat(
                client,
                {
                    "slot_id": slot["id"],
                    "status": "error",
                    "clear_desired_action": True,
                    "adb_endpoint": endpoint,
                    "last_error": provision_progress(4, "ADB 未就绪"),
                    "audit_action": "start_adb_not_ready",
                    "audit_message": ready_msg[:2000],
                    "audit_result": "failed",
                },
            )
            return
        heartbeat(
            client,
            {
                "slot_id": slot["id"],
                "status": "online",
                "clear_desired_action": True,
                "adb_endpoint": endpoint,
                "last_error": "",
                "cpu_percent": stats.get("cpu_percent"),
                "memory_usage_mb": stats.get("memory_usage_mb"),
                "audit_action": "start_ok",
                "audit_message": f"容器已启动并就绪（{endpoint}）",
                "audit_result": "success",
            },
        )
    except DockerOpsError as e:
        heartbeat(
            client,
            {
                "slot_id": slot["id"],
                "status": "error",
                "clear_desired_action": True,
                "last_error": str(e)[:2000],
                "audit_action": "start_failed",
                "audit_message": str(e)[:2000],
                "audit_result": "failed",
            },
        )


def handle_stop(ops: DockerOps, client: httpx.Client, slot: dict) -> None:
    name = slot.get("container_name")
    try:
        if name:
            ops.stop_container(name)
        heartbeat(
            client,
            {
                "slot_id": slot["id"],
                "status": "offline",
                "clear_desired_action": True,
                "last_error": "",
                "cpu_percent": "",
                "memory_usage_mb": "",
                "audit_action": "stop_ok",
                "audit_message": "容器已停止（数据卷保留）",
                "audit_result": "success",
            },
        )
    except DockerOpsError as e:
        heartbeat(
            client,
            {
                "slot_id": slot["id"],
                "status": "error",
                "clear_desired_action": True,
                "last_error": str(e)[:2000],
                "audit_action": "stop_failed",
                "audit_message": str(e)[:2000],
                "audit_result": "failed",
            },
        )


def handle_destroy(ops: DockerOps, client: httpx.Client, slot: dict) -> None:
    name = slot.get("container_name")
    volume = slot.get("volume_name")
    try:
        if name:
            ops.remove_container(name)
        if volume:
            ops.remove_volume(volume)
        # 清理截图目录
        shot_dir = DATA_DIR / "maa" / str(slot["id"])
        if shot_dir.is_dir():
            shutil.rmtree(shot_dir, ignore_errors=True)
        heartbeat(
            client,
            {
                "slot_id": slot["id"],
                "status": "destroyed",
                "clear_desired_action": True,
                "last_error": "",
                "audit_action": "destroy_ok",
                "audit_message": "容器与数据卷已销毁",
                "audit_result": "success",
            },
        )
    except DockerOpsError as e:
        heartbeat(
            client,
            {
                "slot_id": slot["id"],
                "status": "error",
                "clear_desired_action": True,
                "last_error": str(e)[:2000],
                "audit_action": "destroy_failed",
                "audit_message": str(e)[:2000],
                "audit_result": "failed",
            },
        )


def reconcile(ops: DockerOps, client: httpx.Client, slots: list[dict]) -> None:
    """台账有 / 运行时无 → error；运行时有托管标签但台账无 → 销毁。"""
    known_names = {
        s.get("container_name")
        for s in slots
        if s.get("container_name") and s.get("status") != "destroyed"
    }
    for slot in slots:
        name = slot.get("container_name")
        status = slot.get("status")
        if not name or status in ("destroyed", "provisioning", "destroying"):
            continue
        if status in ("online", "offline") and not ops.container_exists(name):
            heartbeat(
                client,
                {
                    "slot_id": slot["id"],
                    "status": "error",
                    "last_error": "运行时容器缺失",
                    "audit_action": "reconcile_missing_runtime",
                    "audit_message": f"台账存在但容器 {name} 不存在",
                    "audit_result": "failed",
                },
            )
    for name in ops.list_managed_containers():
        if name not in known_names:
            LOG.warning("orphan managed container %s — removing", name)
            try:
                ops.remove_container(name)
                # volume 名约定
                if name.startswith("zhange-maa-slot-"):
                    sid = name.removeprefix("zhange-maa-slot-")
                    ops.remove_volume(f"zhange-maa-slot-{sid}-data")
            except DockerOpsError as e:
                LOG.error("orphan cleanup failed %s: %s", name, e)


def process_jobs(client: httpx.Client, slots: list[dict], jobs: list[dict]) -> None:
    slot_map = {s["id"]: s for s in slots}
    for job in jobs:
        if job["status"] != "queued":
            continue
        slot = slot_map.get(job["slot_id"])
        if not slot or slot.get("status") != "online":
            update_job(client, job["id"], "failed", "槽位未在线")
            continue
        if job["job_type"] == "stop":
            update_job(client, job["id"], "success", None)
            continue
        if job["job_type"] != "daily":
            update_job(client, job["id"], "failed", f"未知任务类型 {job['job_type']}")
            continue
        update_job(client, job["id"], "running", None)
        endpoint = slot.get("adb_endpoint") or ""
        # 任务前后截图
        name = slot.get("container_name")
        png = capture_slot_png(ops, endpoint=endpoint, container_name=name)
        if png:
            rel = save_screenshot(slot["id"], png)
            heartbeat(
                client,
                {"slot_id": slot["id"], "screenshot_relpath": rel},
            )
        ok, msg = run_maa_daily(endpoint)
        png2 = capture_slot_png(ops, endpoint=endpoint, container_name=name)
        if png2:
            rel = save_screenshot(slot["id"], png2)
            heartbeat(
                client,
                {"slot_id": slot["id"], "screenshot_relpath": rel},
            )
        update_job(client, job["id"], "success" if ok else "failed", None if ok else msg)


def refresh_slot_screenshots(
    ops: DockerOps, client: httpx.Client, slots: list[dict], last_shot: dict[int, float]
) -> None:
    """在线与供给中均尝试刷新截图与容器占用。"""
    now = time.time()
    for slot in slots:
        status = slot.get("status")
        if status not in ("online", "provisioning"):
            continue
        name = slot.get("container_name")
        endpoint = slot.get("adb_endpoint") or ""
        sid = slot["id"]
        due = now - last_shot.get(sid, 0) >= SCREENSHOT_INTERVAL
        png = None
        # 供给中 ADB 通常未通：跳过截图，只刷占用，避免每次卡死
        if due and status == "online":
            png = capture_slot_png(ops, endpoint=endpoint, container_name=name)
            if png:
                last_shot[sid] = now
        stats = ops.container_stats(name) if name else {}
        payload: dict = {
            "slot_id": sid,
            "cpu_percent": stats.get("cpu_percent") or "",
            "memory_usage_mb": stats.get("memory_usage_mb") or "",
        }
        if png:
            payload["screenshot_relpath"] = save_screenshot(sid, png)
        if status == "provisioning":
            if not (payload["cpu_percent"] or payload["memory_usage_mb"]):
                continue
            try:
                heartbeat(client, payload)
            except httpx.HTTPError as e:
                LOG.warning("heartbeat stats failed: %s", e)
            continue
        try:
            heartbeat(client, payload)
        except httpx.HTTPError as e:
            LOG.warning("heartbeat stats failed: %s", e)


def collect_host_stats() -> dict[str, str]:
    """采集 Worker 所在宿主机（Docker 环境）CPU / 内存。"""
    try:
        import psutil  # type: ignore
    except ImportError:
        return {}
    try:
        # 非阻塞采样，避免每轮卡 0.2s
        cpu = psutil.cpu_percent(interval=None)
        if cpu == 0.0:
            cpu = psutil.cpu_percent(interval=0.05)
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": f"{cpu:.1f}",
            "memory_used_mb": f"{mem.used / (1024 * 1024):.0f}",
            "memory_total_mb": f"{mem.total / (1024 * 1024):.0f}",
            "cpu_count": str(psutil.cpu_count(logical=True) or 0),
        }
    except Exception as e:  # noqa: BLE001
        LOG.debug("host stats failed: %s", e)
        return {}


def report_host_stats(client: httpx.Client) -> None:
    stats = collect_host_stats()
    if not stats:
        return
    try:
        r = client.post(
            f"{APP_BASE_URL}/api/internal/maa/host-stats",
            headers=_headers(),
            json=stats,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        LOG.warning("host-stats report failed: %s", e)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not WORKER_TOKEN:
        raise SystemExit("MAA_WORKER_TOKEN is required")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ops = DockerOps(network=DOCKER_NETWORK)
    last_shot: dict[int, float] = {}
    reconcile_every = 12  # ~1 min if poll=5s
    tick = 0
    LOG.info("maa-worker starting app=%s network=%s", APP_BASE_URL, DOCKER_NETWORK)
    with httpx.Client(timeout=60.0) as client:
        while True:
            try:
                state = pull_state(client)
                slots = state.get("slots") or []
                jobs = state.get("jobs") or []
                # 先上报宿主机占用，避免长供给等待挡住环境指标
                report_host_stats(client)

                def _prio(s: dict) -> int:
                    action = s.get("desired_action")
                    status = s.get("status")
                    if action == "destroy" or status == "destroying":
                        return 0
                    if action == "stop":
                        return 1
                    if action == "start":
                        return 2
                    if action == "provision" or status == "provisioning":
                        return 3
                    return 9

                for slot in sorted(slots, key=_prio):
                    action = slot.get("desired_action")
                    status = slot.get("status")
                    if action == "destroy" or status == "destroying":
                        handle_destroy(ops, client, slot)
                    elif action == "stop":
                        handle_stop(ops, client, slot)
                    elif action == "start":
                        handle_start(ops, client, slot)
                    elif action == "provision" or (
                        status == "provisioning" and not action
                    ):
                        handle_provision(ops, client, slot)
                process_jobs(client, slots, jobs)
                refresh_slot_screenshots(ops, client, slots, last_shot)
                for slot in slots:
                    if slot.get("status") in ("provisioning", "online", "error", "destroying"):
                        try:
                            refresh_slot_runtime_log(ops, slot)
                        except Exception:  # noqa: BLE001
                            LOG.debug("runtime log refresh failed", exc_info=True)
                tick += 1
                if tick >= reconcile_every:
                    tick = 0
                    # 重新 pull 后再对账
                    state = pull_state(client)
                    reconcile(ops, client, state.get("slots") or [])
            except Exception:
                LOG.exception("worker loop error")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
