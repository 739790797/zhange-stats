"""一次 SteamCMD 登录。口令和令牌只进这次进程，成功后的凭证由 SteamCMD 自己留下。"""

from __future__ import annotations

import atexit
import logging
import re
import threading
import time

from app.services.ror2.console_io import ConsoleIO, open_console
from app.services.ror2.steamcmd import SteamCmdError, clean_username, ensure_steamcmd

log = logging.getLogger("zhange.ror2")

LOGIN_TIMEOUT_SEC = 5 * 60
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)")
_CODE = re.compile(r"^[A-Za-z0-9]{1,16}$")

_lock = threading.Lock()
_current: _LoginRun | None = None


class SteamCmdBusy(SteamCmdError):
    pass


class _LoginRun:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self._password = password
        self.secrets = [password]
        self.state = "starting"
        self.message = "正在启动 SteamCMD"
        self.started = time.monotonic()
        self.io: ConsoleIO | None = None
        self._login_sent = False
        self._state_lock = threading.Lock()
        self.output = ""

    def public(self) -> dict[str, str]:
        with self._state_lock:
            return {"state": self.state, "message": self.message}

    def set_state(self, state: str, message: str) -> None:
        with self._state_lock:
            if self.state in {"ok", "error"} and state not in {"ok", "error"}:
                return
            self.state = state
            self.message = message

    def redact(self, text: str) -> str:
        redacted = text
        for secret in self.secrets:
            if secret:
                redacted = redacted.replace(secret, "***")
        return redacted

    def remember(self, line: str) -> None:
        self.output = (self.output + "\n" + line)[-4000:]


def login_status() -> dict[str, str]:
    with _lock:
        run = _current
    if run is None:
        return {"state": "idle", "message": ""}
    _expire(run)
    return run.public()


def start_login(username: str, password: str, *, console_factory=None) -> dict[str, str]:
    global _current
    user = clean_username(username)
    secret = _clean_password(password)
    with _lock:
        run = _current
        if run is not None and run.public()["state"] in {"starting", "need_guard", "need_mobile"}:
            raise SteamCmdBusy("已有登录在进行")
        if run is not None and run.io is not None:
            run.io.close()
        current = _LoginRun(user, secret)
        _current = current
    from app.services.integrations_config import save_integrations

    save_integrations(None, {"steamcmd_username": user})
    try:
        executable = ensure_steamcmd()
        factory = console_factory or open_console
        console = factory([str(executable)], cwd=str(executable.parent))
    except SteamCmdError as exc:
        current.set_state("error", str(exc))
        raise
    except OSError as exc:
        current.set_state("error", "无法启动 steamcmd")
        raise SteamCmdError("无法启动 steamcmd") from exc
    current.io = console
    threading.Thread(target=_loop, args=(current,), name="steamcmd-login", daemon=True).start()
    log.info("steamcmd 登录开始")
    return current.public()


def submit_guard(code: str) -> dict[str, str]:
    clean = (code or "").strip()
    if _CODE.fullmatch(clean) is None:
        raise SteamCmdError("令牌无效")
    with _lock:
        run = _current
    if run is None or run.public()["state"] != "need_guard" or run.io is None:
        raise SteamCmdError("现在不需要令牌")
    run.secrets.append(clean)
    run.set_state("starting", "正在校验令牌")
    run.io.write(clean + "\r\n")
    return run.public()


def cancel_login() -> dict[str, str]:
    with _lock:
        run = _current
    if run is None:
        return {"state": "idle", "message": ""}
    if run.io is not None:
        run.io.close()
    if run.public()["state"] not in {"ok", "error"}:
        run.set_state("error", "已取消登录")
    return run.public()


def reset_login_for_tests() -> None:
    global _current
    cancel_login()
    with _lock:
        _current = None


def classify_steamcmd_text(text: str) -> str | None:
    low = _ANSI.sub("", text).lower()
    if any(
        bit in low
        for bit in (
            "steam mobile app",
            "confirm your sign in",
            "confirm the login",
            "waiting for confirmation",
        )
    ):
        return "need_mobile"
    if any(bit in low for bit in ("steam guard code", "two-factor code", "two factor code", "guard code:")):
        return "need_guard"
    if "waiting for user info" in low and "ok" in low:
        return "ok"
    if any(
        bit in low
        for bit in (
            "invalid password",
            "invalid login auth code",
            "rate limit exceeded",
            "account logon denied",
            "login failure",
        )
    ):
        return "error"
    return None


def _clean_password(value: str) -> str:
    text = value or ""
    if not text.strip() or any(ord(char) < 32 for char in text) or len(text) > 128:
        raise SteamCmdError("密码无效")
    return text


def _expire(run: _LoginRun) -> None:
    if run.public()["state"] in {"ok", "error", "idle"}:
        return
    if time.monotonic() - run.started <= LOGIN_TIMEOUT_SEC:
        return
    run.set_state("error", "登录超时")
    if run.io is not None:
        run.io.kill()


def _loop(run: _LoginRun) -> None:
    console = run.io
    if console is None:
        return
    pending = ""
    try:
        while run.public()["state"] not in {"ok", "error"}:
            _expire(run)
            if run.public()["state"] == "error":
                break
            chunk = console.read(0.2)
            if chunk:
                pending = _drain(run, pending + chunk)
            if console.poll() is not None:
                extra = console.read(0)
                if extra:
                    pending += extra
                if pending.strip():
                    _drain(run, pending + "\n")
                if run.public()["state"] not in {"ok", "error"}:
                    run.set_state("error", explain_steamcmd_exit(run.output))
                break
    except OSError:
        if run.public()["state"] not in {"ok", "error"}:
            run.set_state("error", "无法读取 SteamCMD 输出")
    finally:
        if run.public()["state"] == "ok":
            try:
                console.write("quit\r\n")
            except OSError:
                pass
            console.wait(15)
        else:
            console.kill()
        finished = run.public()
        if finished["state"] == "error":
            log.warning("steamcmd 登录失败 %s", finished["message"])
        else:
            log.info("steamcmd 登录结束 state=%s", finished["state"])


def _drain(run: _LoginRun, pending: str) -> str:
    text = pending.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    rest = lines[-1]
    for line in lines[:-1]:
        _handle_line(run, line)
    if rest and (classify_steamcmd_text(rest) or "steam>" in rest.lower()):
        _handle_line(run, rest)
        return ""
    return rest


def _handle_line(run: _LoginRun, line: str) -> None:
    visible = run.redact(_ANSI.sub("", line)).strip()
    if not visible:
        return
    run.remember(visible)
    if "steam>" in visible.lower() and not run._login_sent and run.io is not None:
        run._login_sent = True
        token = _console_token(run.username)
        secret = _console_token(run._password)
        run.io.write(f"login {token} {secret}\r\n")
        run._password = ""
        return
    event = classify_steamcmd_text(visible)
    if event == "need_guard":
        run.set_state("need_guard", "请输入这次登录收到的令牌。邮箱验证码要等 Steam 发出后再填。")
    elif event == "need_mobile":
        run.set_state("need_mobile", "请在手机 Steam 上允许这次登录。")
    elif event == "ok":
        run.set_state("ok", "已登录。之后的更新会使用这份凭证。")
    elif event == "error":
        run.set_state("error", _error_message(visible))


def _console_token(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def explain_steamcmd_exit(text: str) -> str:
    """进程在登录完成前退出。把能对上的启动失败说清楚，其余留下最后几行。"""
    low = text.lower()
    if "exec format error" in low or "cannot execute binary file" in low:
        return "SteamCMD 无法启动：程序是 x86 32 位的，当前系统架构无法执行。"
    if any(bit in low for bit in ("steam.dll", "vcruntime", "msvcp140")):
        return "SteamCMD 无法启动：Windows 缺少 Visual C++ 运行库。"
    if "permission denied" in low and "steamcmd" in low:
        return "SteamCMD 无法启动：程序没有执行权限。"
    if (
        "error while loading shared libraries" in low
        or "ld-linux.so.2" in low
        or ("no such file or directory" in low and "steamcmd" in low)
    ):
        return (
            "SteamCMD 无法启动：系统缺少 32 位运行库。"
            "请在主机执行 sudo apt-get install -y libc6-i386 lib32gcc-s1 后再登录。"
        )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "SteamCMD 已退出，登录未完成"
    tail = " | ".join(lines[-3:])
    if len(tail) > 180:
        tail = tail[-180:]
    return f"SteamCMD 已退出，登录未完成：{tail}"


def _error_message(line: str) -> str:
    low = line.lower()
    if "rate limit" in low:
        return "Steam 暂时拒绝登录，请稍后再试"
    if "auth code" in low or "two-factor" in low or "two factor" in low or "steam guard" in low:
        return "令牌不正确"
    if "password" in low or "logon denied" in low:
        return "账号或密码不正确"
    return "SteamCMD 登录失败"


def _shutdown() -> None:
    with _lock:
        run = _current
    if run is not None and run.io is not None:
        run.io.close()


atexit.register(_shutdown)
