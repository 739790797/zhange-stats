"""Minecraft / Pelican console helpers."""

from __future__ import annotations

import json

import pytest

from app.services.minecraft_console import (
    client_command_to_wings,
    parse_stats_payload,
    parse_wings_message,
)
from app.services.pelican_client import PelicanError, parse_websocket_credentials


def test_parse_websocket_credentials_pterodactyl_shape():
    socket, token = parse_websocket_credentials(
        {"data": {"token": "jwt-here", "socket": "wss://wings.example/ws"}}
    )
    assert socket == "wss://wings.example/ws"
    assert token == "jwt-here"


def test_parse_websocket_credentials_attributes_shape():
    socket, token = parse_websocket_credentials(
        {
            "data": {
                "attributes": {
                    "token": "abc",
                    "socket_url": "wss://node.example/api/servers/x/ws",
                }
            }
        }
    )
    assert "node.example" in socket
    assert token == "abc"


def test_parse_websocket_credentials_rejects_empty():
    with pytest.raises(PelicanError):
        parse_websocket_credentials({"data": {"token": "", "socket": ""}})


def test_client_command_to_wings_ok():
    msg = client_command_to_wings({"event": "command", "command": "list"})
    assert msg == {"event": "send command", "args": ["list"]}


def test_client_command_rejects_set_state_and_newlines():
    assert client_command_to_wings({"event": "set state", "args": ["kill"]}) is None
    assert client_command_to_wings({"event": "command", "command": "say\nhack"}) is None
    assert client_command_to_wings({"event": "command", "command": ""}) is None
    assert client_command_to_wings({"event": "command", "command": "x" * 2000}) is None


def test_parse_wings_console_and_stats():
    parsed = parse_wings_message(
        json.dumps({"event": "console output", "args": ["Hello"]})
    )
    assert parsed == {"event": "console output", "args": ["Hello"]}
    stats = parse_stats_payload(
        [
            json.dumps(
                {
                    "cpu_absolute": 12.5,
                    "memory_bytes": 1024,
                    "memory_limit_bytes": 2048,
                    "disk_bytes": 4096,
                    "uptime": 9000,
                    "state": "running",
                    "network": {"rx_bytes": 10, "tx_bytes": 20},
                }
            )
        ]
    )
    assert stats is not None
    assert stats["cpu"] == 12.5
    assert stats["memory_bytes"] == 1024
    assert stats["disk_bytes"] == 4096
    assert stats["network_rx_bytes"] == 10
    assert stats["network_tx_bytes"] == 20
    assert stats["state"] == "running"


def test_parse_server_meta_name_and_default_allocation():
    from app.services.pelican_client import parse_server_meta

    meta = parse_server_meta(
        {
            "attributes": {
                "name": "我的世界",
                "limits": {"memory": 0, "cpu": 0, "disk": 0},
            },
            "relationships": {
                "allocations": {
                    "data": [
                        {
                            "attributes": {
                                "ip": "127.0.0.1",
                                "port": 25566,
                                "is_default": False,
                            }
                        },
                        {
                            "attributes": {
                                "ip": "0.0.0.0",
                                "ip_alias": "mc.example",
                                "port": 25565,
                                "is_default": True,
                            }
                        },
                    ]
                }
            },
        }
    )
    assert meta["name"] == "我的世界"
    assert meta["address"] == "mc.example:25565"
    assert meta["memory_limit_mb"] == 0
    assert meta["cpu_limit"] == 0
    assert meta["disk_limit_mb"] == 0


def test_parse_server_meta_reads_panel_resource_limits():
    from app.services.pelican_client import parse_server_meta

    meta = parse_server_meta(
        {
            "attributes": {
                "name": "我的世界",
                "limits": {"memory": 8192, "cpu": 400, "disk": 20480},
            }
        }
    )
    assert meta["memory_limit_mb"] == 8192
    assert meta["cpu_limit"] == 400
    assert meta["disk_limit_mb"] == 20480
