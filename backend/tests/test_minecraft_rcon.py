"""Minecraft RCON packet / TPS 解析 / 属性脱敏。"""

from __future__ import annotations

import struct
from types import SimpleNamespace

from app.services.minecraft_pack import (
    merge_rcon_properties,
    parse_properties,
    redact_properties,
)
from app.services.minecraft_profile import desired_snapshot, playbook_from_snapshot
from app.services.minecraft_rcon import TYPE_AUTH, pack_packet, parse_perf_text


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
        public_host="zhange.space",
        public_port=25565,
    )
    playbook = playbook_from_snapshot(desired_snapshot(row))
    assert playbook is not None
    assert "rcon.password" not in playbook["properties"]
    assert "rcon_password_set" not in playbook
