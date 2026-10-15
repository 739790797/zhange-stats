"""SteamCMD 固定在战鸽根目录，口令不出现在失败信息里。"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.services.ror2.steamcmd import (
    ROR2_APP_ID,
    SteamCmdError,
    build_argv,
    ensure_steamcmd,
    lang_dir_from_steamcmd,
    run_ror2_update,
)


def test_build_argv_updates_ror2_with_the_cached_login(tmp_path: Path) -> None:
    executable = tmp_path / "steamcmd" / "steamcmd.exe"
    argv = build_argv(executable, "alice")
    assert "+force_install_dir" not in argv
    assert "secret-pass" not in argv
    assert argv[argv.index("+login") + 1] == "alice"
    assert argv.index("+login") < argv.index("+app_update")
    assert argv[argv.index("+app_update") + 1] == ROR2_APP_ID
    assert argv[-1] == "+quit"
    folder = lang_dir_from_steamcmd(executable)
    assert folder.as_posix().endswith(
        "steamcmd/steamapps/common/Risk of Rain 2/Risk of Rain 2_Data/StreamingAssets/Language/zh-CN"
    )


def test_ensure_uses_the_root_copy_without_downloading(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "steamcmd"
    home.mkdir()
    executable = home / "steamcmd.exe"
    executable.write_bytes(b"MZ")
    monkeypatch.setattr("app.services.ror2.steamcmd.os.name", "nt")
    monkeypatch.setattr("app.services.ror2.steamcmd.steamcmd_home", lambda: home)

    def _forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("已有可执行文件时不应下载")

    monkeypatch.setattr("app.services.ror2.steamcmd.http_request", _forbidden)
    assert ensure_steamcmd() == executable


def test_ensure_downloads_the_windows_bootstrap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "steamcmd"
    monkeypatch.setattr("app.services.ror2.steamcmd.os.name", "nt")
    monkeypatch.setattr("app.services.ror2.steamcmd.steamcmd_home", lambda: home)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("steamcmd.exe", b"MZ")

    class _Response:
        status_code = 200
        content = payload.getvalue()

    monkeypatch.setattr("app.services.ror2.steamcmd.http_request", lambda *_args, **_kwargs: _Response())
    assert ensure_steamcmd() == home / "steamcmd.exe"
    assert (home / "steamcmd.exe").read_bytes() == b"MZ"


def test_ensure_rejects_a_path_that_escapes_the_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "steamcmd"
    monkeypatch.setattr("app.services.ror2.steamcmd.os.name", "nt")
    monkeypatch.setattr("app.services.ror2.steamcmd.steamcmd_home", lambda: home)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("../steamcmd.exe", b"MZ")

    class _Response:
        status_code = 200
        content = payload.getvalue()

    monkeypatch.setattr("app.services.ror2.steamcmd.http_request", lambda *_args, **_kwargs: _Response())
    with pytest.raises(SteamCmdError, match="路径不安全"):
        ensure_steamcmd()
    assert not (tmp_path / "steamcmd.exe").exists()


def test_failure_output_drops_the_password(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executable = tmp_path / "steamcmd" / "steamcmd.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"")

    class _Result:
        returncode = 7
        stdout = "FAILED (Invalid Password)"
        stderr = ""

    monkeypatch.setattr("app.services.ror2.steamcmd.ensure_steamcmd", lambda: executable)
    monkeypatch.setattr("app.services.ror2.steamcmd.subprocess.run", lambda *args, **kwargs: _Result())
    with pytest.raises(SteamCmdError, match="重新登录") as caught:
        run_ror2_update({"steamcmd_username": "alice"})
    assert "secret-pass" not in str(caught.value)


def test_cached_account_returns_the_name_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "steamcmd"
    (home / "config").mkdir(parents=True)
    (home / "config" / "config.vdf").write_text(
        """
"InstallConfigStore"
{
  "Software"
  {
    "Valve"
    {
      "Steam"
      {
        "Accounts"
        {
          "alice"
          {
            "SteamID" "76561198000000000"
          }
        }
        "ConnectCache"
        {
          "hash" "super-secret-token"
        }
      }
    }
  }
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.ror2.steamcmd.steamcmd_home", lambda: home)
    from app.services.ror2.steamcmd import cached_account

    assert cached_account() == "alice"


def test_console_log_tail_uses_the_latest_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "steamcmd"
    (home / "logs").mkdir(parents=True)
    (home / "logs" / "console_log.txt").write_text(
        "\n".join(
            [
                "Client version: 1",
                " Update state (0x61) downloading, progress: 10.00 (100 / 1000)",
                "Client version: 2",
                " Update state (0x81) verifying update, progress: 50.00 (500 / 1000)",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.ror2.steamcmd.steamcmd_home", lambda: home)
    from app.services.ror2.steamcmd import console_log_tail

    tail, progress = console_log_tail()
    assert "Client version: 1" not in tail
    assert progress is not None
    assert progress["phase"] == "steamcmd_verify"
    assert progress["percent"] == 50.0
    assert progress["bytes"] == 500
    assert progress["total_bytes"] == 1000

