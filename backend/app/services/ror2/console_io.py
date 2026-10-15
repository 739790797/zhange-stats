"""给 SteamCMD 一块真正的控制台。

登录提示在普通管道里经常不刷新。Windows 用 pywinpty 的 ConPTY，Linux 用 pty，
这样口令走控制台输入，不出现在进程参数里。
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Protocol


class ConsoleIO(Protocol):
    def read(self, timeout: float) -> str: ...

    def write(self, text: str) -> None: ...

    def poll(self) -> int | None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float) -> int: ...

    def close(self) -> None: ...


def open_console(argv: list[str], *, cwd: str) -> ConsoleIO:
    if os.name == "nt":
        return _WinptyConsole(argv, cwd)
    return _PosixConsole(argv, cwd)


class _PosixConsole:
    def __init__(self, argv: list[str], cwd: str) -> None:
        import fcntl
        import pty

        master, slave = pty.openpty()
        try:
            self._proc = subprocess.Popen(
                argv,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                cwd=cwd,
                close_fds=True,
            )
        except OSError:
            os.close(master)
            os.close(slave)
            raise
        os.close(slave)
        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self._master = master
        self._closed = False

    def read(self, timeout: float) -> str:
        import select

        if self._closed:
            return ""
        ready, _, _ = select.select([self._master], [], [], timeout)
        if not ready:
            return ""
        try:
            data = os.read(self._master, 65536)
        except OSError:
            return ""
        return data.decode("utf-8", "replace")

    def write(self, text: str) -> None:
        if self._closed:
            return
        os.write(self._master, text.encode("utf-8"))

    def poll(self) -> int | None:
        return self._proc.poll()

    def kill(self) -> None:
        if self._proc.poll() is None:
            self._proc.kill()

    def wait(self, timeout: float) -> int:
        try:
            return self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.kill()
            return self._proc.wait(timeout=5)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.kill()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        os.close(self._master)


class _WinptyConsole:
    def __init__(self, argv: list[str], cwd: str) -> None:
        from winpty import PtyProcess

        self._proc = PtyProcess.spawn(argv, cwd=cwd)
        self._closed = False

    def read(self, timeout: float) -> str:
        if self._closed:
            return ""
        self._proc.fileobj.settimeout(timeout if timeout > 0 else 0.01)
        try:
            return self._proc.read(65536)
        except (TimeoutError, EOFError, OSError):
            return ""

    def write(self, text: str) -> None:
        if self._closed:
            return
        self._proc.write(text)

    def poll(self) -> int | None:
        if self._proc.isalive():
            return None
        return self._proc.exitstatus

    def kill(self) -> None:
        if not self._proc.isalive():
            return
        try:
            self._proc.terminate(force=True)
        except OSError:
            pass
        if self._proc.isalive():
            subprocess.run(
                ["taskkill", "/PID", str(self._proc.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

    def wait(self, timeout: float) -> int:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            code = self.poll()
            if code is not None:
                return code
            time.sleep(0.05)
        self.kill()
        return self.poll() if self.poll() is not None else 1

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.kill()
        try:
            self._proc.close(force=True)
        except OSError:
            pass
