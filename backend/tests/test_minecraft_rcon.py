"""Minecraft RCON packet / TPS 解析 / 属性脱敏。"""

from __future__ import annotations

import socket
import struct
import threading
from types import SimpleNamespace

import pytest

from app.services.minecraft.pack import (
    merge_rcon_properties,
    parse_properties,
    redact_properties,
)
from app.services.minecraft.profile import desired_snapshot, playbook_from_snapshot
from app.services.minecraft.rcon import (
    TYPE_AUTH,
    TYPE_EXEC,
    TYPE_RESPONSE,
    MinecraftRconError,
    pack_packet,
    parse_perf_text,
    query_list,
    query_perf,
    rcon_exec,
    reset_session,
    session_connected,
    unpack_packet,
)


def test_pack_packet_layout():
    pkt = pack_packet(7, TYPE_AUTH, "abc")
    length = struct.unpack_from("<i", pkt, 0)[0]
    assert length == len(pkt) - 4
    req_id, ptype = struct.unpack_from("<ii", pkt, 4)
    assert req_id == 7
    assert ptype == TYPE_AUTH
    assert pkt[12:-2] == b"abc"
    assert pkt[-2:] == b"\x00\x00"


def test_parse_spark_tps_and_median_mspt():
    raw = (
        "[⚡] TPS from last 5s, 10s, 1m, 5m, 15m:\n"
        "[⚡]  19.98, 19.99, 20.0, 20.0, 20.0\n"
        "[⚡]\n"
        "[⚡] Tick durations (min/med/95%ile/max ms) from last 10s, 1m:\n"
        "[⚡]  1.2/2.4/8.1/41.0; 1.3/2.5/7.8/39.2\n"
    )
    parsed = parse_perf_text(raw)
    assert parsed["tps"] == 19.98
    assert parsed["mspt"] == 2.4


def test_parse_paper_same_line_tps():
    raw = "TPS from last 1m, 5m, 15m: 20.0, 19.8, 19.6\nMean tick time: 3.5 ms"
    parsed = parse_perf_text(raw)
    assert parsed["tps"] == 20.0
    assert parsed["mspt"] == 3.5


def test_parse_tick_query_ignores_target_rate():
    raw = (
        "The game is running normally with a target rate of 20.0000 ticks per second.\n"
        "Average time per tick: 12.5ms\n"
    )
    parsed = parse_perf_text(raw)
    assert parsed["mspt"] == 12.5
    assert parsed["tps"] == 20.0


def test_redact_and_merge_rcon_properties():
    merged = merge_rcon_properties(
        "motd=hi\n",
        enabled=True,
        port=25575,
        password="s3cret",
    )
    props = parse_properties(merged)
    assert props["enable-rcon"] == "true"
    assert props["rcon.port"] == "25575"
    assert props["rcon.password"] == "s3cret"
    assert props["broadcast-rcon-to-ops"] == "false"
    assert "rcon.password" not in redact_properties(props)


def test_playbook_hides_rcon_password():
    row = SimpleNamespace(
        mc_version="1.21.1",
        loader="neoforge",
        loader_version="",
        mods_json=[],
        overrides_json={"server.properties": "motd=hi\nrcon.password=supersecret\n"},
    )
    playbook = playbook_from_snapshot(desired_snapshot(row))
    assert playbook is not None
    assert "rcon.password" not in playbook["properties"]
    assert "rcon_password_set" not in playbook


class FakeRcon:
    def __init__(self, password: str = "secret", replies: dict[str, str] | None = None):
        self.password = password
        self.replies = replies or {}
        self.commands: list[str] = []
        self.connections = 0
        self.close_after = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self._sock.settimeout(0.2)
        self.port = int(self._sock.getsockname()[1])
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=2)

    def _accept(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with self._lock:
                self.connections += 1
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn: socket.socket) -> None:
        conn.settimeout(2)
        try:
            while not self._stop.is_set():
                try:
                    req_id, ptype, body = unpack_packet(conn)
                except (MinecraftRconError, TimeoutError, OSError):
                    return
                if ptype == TYPE_AUTH:
                    ok = body == self.password
                    conn.sendall(
                        pack_packet(req_id if ok else -1, TYPE_EXEC, "")
                    )
                    continue
                if ptype != TYPE_EXEC:
                    continue
                with self._lock:
                    self.commands.append(body)
                    count = len(self.commands)
                    close_after = self.close_after
                reply = self.replies.get(body, body)
                conn.sendall(pack_packet(req_id, TYPE_RESPONSE, reply))
                if close_after and count >= close_after:
                    return
        finally:
            try:
                conn.close()
            except OSError:
                pass


@pytest.fixture
def rcon_session():
    reset_session()
    yield
    reset_session()


def test_rcon_reuses_tcp_session(rcon_session):
    server = FakeRcon(
        replies={
            "list": "There are 1 of a max of 20 players online: BaiYi",
            "spark tps": "TPS from last 5s, 10s, 1m, 5m, 15m: 20.0, 20.0, 20.0, 20.0, 20.0",
        }
    )
    try:
        assert query_list("127.0.0.1", server.port, "secret") == ["BaiYi"]
        parsed = query_perf("127.0.0.1", server.port, "secret")
        assert parsed["tps"] == 20.0
        assert server.connections == 1
        assert session_connected()
        assert server.commands == ["list", "spark tps"]
    finally:
        server.close()


def test_rcon_reconnects_after_peer_close(rcon_session):
    server = FakeRcon(replies={"list": "There are 0 of a max of 20 players online:"})
    server.close_after = 1
    try:
        assert query_list("127.0.0.1", server.port, "secret") == []
        assert query_list("127.0.0.1", server.port, "secret") == []
        assert server.connections == 2
        assert server.commands == ["list", "list"]
    finally:
        server.close()


def test_rcon_wrong_password(rcon_session):
    server = FakeRcon()
    try:
        with pytest.raises(MinecraftRconError, match="密码"):
            rcon_exec("127.0.0.1", server.port, "nope", "list")
        assert session_connected() is False
    finally:
        server.close()
