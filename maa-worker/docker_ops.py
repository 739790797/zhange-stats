"""Docker 操作封装：Redroid 槽位生命周期。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import docker
from docker.errors import APIError, ContainerError, ImageNotFound, NotFound

LOG = logging.getLogger("maa-worker.docker")

MANAGED_LABEL = "zhange.maa.managed"


class DockerOpsError(RuntimeError):
    pass


def _running_in_container() -> bool:
    return Path("/.dockerenv").exists()


def _short_detail(msg: str, *, limit: int = 80) -> str:
    one = " ".join((msg or "").split())
    if len(one) <= limit:
        return one
    return one[: limit - 1] + "…"


class DockerOps:
    def __init__(self, network: str) -> None:
        self.network = network
        try:
            self.client = docker.from_env()
        except Exception as e:  # noqa: BLE001
            raise DockerOpsError(f"无法连接 Docker: {e}") from e
        self._binder_cache: tuple[bool, str] | None = None

    def ensure_network(self) -> None:
        try:
            self.client.networks.get(self.network)
        except NotFound:
            LOG.info("creating network %s", self.network)
            self.client.networks.create(self.network, driver="bridge", check_duplicate=True)

    def container_exists(self, name: str) -> bool:
        try:
            self.client.containers.get(name)
            return True
        except NotFound:
            return False

    def check_binder_support(self, *, force: bool = False) -> tuple[bool, str]:
        """检测宿主机内核是否支持 binderfs（Redroid 必需）。"""
        if self._binder_cache is not None and not force:
            return self._binder_cache
        probe_image = os.environ.get("MAA_PROBE_IMAGE", "alpine:3.20")
        try:
            try:
                self.client.images.get(probe_image)
            except ImageNotFound:
                LOG.info("pulling probe image %s", probe_image)
                self.client.images.pull(probe_image)
            out = self.client.containers.run(
                probe_image,
                command=[
                    "sh",
                    "-c",
                    "mkdir -p /mnt/bf && mount -t binder binder /mnt/bf "
                    "&& ls /mnt/bf && umount /mnt/bf && echo BINDER_OK",
                ],
                privileged=True,
                remove=True,
                network_mode="none",
            )
            text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out)
            ok = "BINDER_OK" in text
            msg = text.strip() or ("binderfs ok" if ok else "binderfs mount failed")
            self._binder_cache = (ok, msg)
            return self._binder_cache
        except (APIError, ContainerError, OSError) as e:
            detail = str(e)
            if "No such device" in detail or "255" in detail:
                msg = "宿主机不支持 binder，请在 Linux 运行"
            else:
                msg = f"binder 检测失败：{_short_detail(detail)}"
            self._binder_cache = (False, msg)
            return self._binder_cache

    def ensure_slot(self, *, name: str, volume: str, image: str) -> str:
        """若容器已存在则复用（供给重试不重建）；否则创建。返回 ADB endpoint。"""
        if self.container_exists(name):
            try:
                c = self.client.containers.get(name)
                if c.status != "running":
                    c.start()
            except APIError as e:
                raise DockerOpsError(f"启动已有容器失败: {e}") from e
            return self.resolve_adb_endpoint(name)
        return self.create_or_replace_slot(name=name, volume=volume, image=image)

    def create_or_replace_slot(self, *, name: str, volume: str, image: str) -> str:
        """创建槽位容器，返回宿主机/Worker 可连的 ADB endpoint。"""
        self.ensure_network()
        ok, binder_msg = self.check_binder_support()
        if not ok:
            raise DockerOpsError(binder_msg)

        if self.container_exists(name):
            self.remove_container(name)
        try:
            self.client.images.get(image)
        except ImageNotFound:
            LOG.info("pulling image %s", image)
            self.client.images.pull(image)
        try:
            self.client.volumes.get(volume)
        except NotFound:
            self.client.volumes.create(name=volume, labels={MANAGED_LABEL: "1"})

        # 宿主机跑 Worker 时必须映射端口；compose 内 Worker 可用容器名
        publish_adb = os.environ.get("MAA_PUBLISH_ADB", "").strip()
        if publish_adb == "1":
            use_host_port = True
        elif publish_adb == "0":
            use_host_port = False
        else:
            use_host_port = not _running_in_container()

        run_kwargs: dict[str, Any] = {
            "image": image,
            "name": name,
            "detach": True,
            "privileged": True,
            "network": self.network,
            "volumes": {volume: {"bind": "/data", "mode": "rw"}},
            "labels": {MANAGED_LABEL: "1", "zhange.maa.slot": name},
            "command": [
                "androidboot.redroid_width=720",
                "androidboot.redroid_height=1280",
                "androidboot.redroid_dpi=320",
                "androidboot.redroid_gpu_mode=guest",
                "androidboot.redroid_fps=30",
                "ro.product.cpu.abilist=x86_64,arm64-v8a,x86,armeabi-v7a,armeabi",
                "ro.product.cpu.abilist64=x86_64,arm64-v8a",
                "ro.product.cpu.abilist32=x86,armeabi-v7a,armeabi",
                "ro.dalvik.vm.isa.arm=x86",
                "ro.dalvik.vm.isa.arm64=x86_64",
                "ro.enable.native.bridge.exec=1",
                "ro.dalvik.vm.native.bridge=libndk_translation.so",
            ],
            "restart_policy": {"Name": "unless-stopped"},
        }
        if use_host_port:
            run_kwargs["ports"] = {"5555/tcp": None}

        try:
            container = self.client.containers.run(**run_kwargs)
        except APIError as e:
            raise DockerOpsError(f"创建容器失败: {e}") from e

        return self.resolve_adb_endpoint(container.name)

    def resolve_adb_endpoint(self, name: str) -> str:
        """解析可从当前 Worker 进程连通的 ADB 地址。"""
        try:
            c = self.client.containers.get(name)
            c.reload()
        except NotFound as e:
            raise DockerOpsError(f"容器不存在: {name}") from e

        # 优先已发布的宿主机端口（本机 Worker）
        ports = (c.attrs.get("NetworkSettings") or {}).get("Ports") or {}
        bindings = ports.get("5555/tcp") or []
        if bindings:
            host_ip = bindings[0].get("HostIp") or "127.0.0.1"
            if host_ip in ("", "0.0.0.0", "::"):
                host_ip = "127.0.0.1"
            host_port = bindings[0].get("HostPort")
            if host_port:
                return f"{host_ip}:{host_port}"

        # compose 内：同网络容器名
        if _running_in_container():
            return f"{name}:5555"

        # 回退容器网桥 IP
        networks = (c.attrs.get("NetworkSettings") or {}).get("Networks") or {}
        net = networks.get(self.network) or next(iter(networks.values()), None)
        if net and net.get("IPAddress"):
            return f"{net['IPAddress']}:5555"
        return f"{name}:5555"

    def android_boot_hint(self, name: str) -> str:
        """读取 boot_completed 等，便于供给等待诊断。"""
        try:
            c = self.client.containers.get(name)
            if c.status != "running":
                return f"container={c.status}"
            code, out = c.exec_run(
                ["sh", "-c", "echo boot=$(getprop sys.boot_completed); echo adbd=$(getprop init.svc.adbd)"],
            )
            text = (out or b"").decode("utf-8", errors="replace").strip()
            return text or f"exec_code={code}"
        except (NotFound, APIError, OSError) as e:
            return f"boot_hint_err={e}"

    def container_logs(self, name: str, *, tail: int = 80) -> str:
        try:
            c = self.client.containers.get(name)
            raw = c.logs(tail=tail, timestamps=True)
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="replace")
            return str(raw)
        except NotFound:
            return f"(容器不存在: {name})"
        except APIError as e:
            return f"(读取容器日志失败: {e})"

    def container_screencap(self, name: str) -> bytes | None:
        """在 Android 容器内执行 screencap（ADB 未通时的回退）。"""
        try:
            c = self.client.containers.get(name)
            if c.status != "running":
                return None
            code, out = c.exec_run(["sh", "-c", "screencap -p 2>/dev/null"])
            if code != 0 or not out:
                return None
            data = out if isinstance(out, (bytes, bytearray)) else bytes(out)
            if data.startswith(b"\x89PNG") or b"PNG" in data[:20]:
                return bytes(data)
            data = data.replace(b"\r\n", b"\n")
            if data.startswith(b"\x89PNG"):
                return data
            return None
        except (NotFound, APIError, OSError) as e:
            LOG.warning("container screencap failed %s: %s", name, e)
            return None

    def container_stats(self, name: str | None) -> dict[str, Any]:
        if not name:
            return {}
        try:
            c = self.client.containers.get(name)
            if c.status != "running":
                return {}
            s = c.stats(stream=False)
            cpu = _calc_cpu_percent(s)
            mem = s.get("memory_stats", {}).get("usage") or 0
            return {
                "cpu_percent": f"{cpu:.1f}",
                "memory_usage_mb": f"{mem / (1024 * 1024):.1f}",
            }
        except (NotFound, APIError, KeyError, TypeError):
            return {}

    def start_container(self, name: str) -> str:
        try:
            c = self.client.containers.get(name)
            if c.status != "running":
                c.start()
            return self.resolve_adb_endpoint(name)
        except NotFound as e:
            raise DockerOpsError(f"容器不存在: {name}") from e
        except APIError as e:
            raise DockerOpsError(f"启动失败: {e}") from e

    def stop_container(self, name: str) -> None:
        try:
            c = self.client.containers.get(name)
            if c.status == "running":
                c.stop(timeout=20)
        except NotFound:
            return
        except APIError as e:
            raise DockerOpsError(f"停止失败: {e}") from e

    def remove_container(self, name: str) -> None:
        try:
            c = self.client.containers.get(name)
            c.remove(force=True)
        except NotFound:
            return
        except APIError as e:
            raise DockerOpsError(f"删除容器失败: {e}") from e

    def remove_volume(self, volume: str) -> None:
        try:
            v = self.client.volumes.get(volume)
            v.remove(force=True)
        except NotFound:
            return
        except APIError as e:
            raise DockerOpsError(f"删除卷失败: {e}") from e

    def list_managed_containers(self) -> list[str]:
        containers = self.client.containers.list(
            all=True, filters={"label": f"{MANAGED_LABEL}=1"}
        )
        return [c.name for c in containers]


def _calc_cpu_percent(stats: dict) -> float:
    """容器占用整机 CPU 的比例（约 0–100%），非「一核=100%」的多核累加。"""
    try:
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"]
            - stats["precpu_stats"]["system_cpu_usage"]
        )
        if system_delta > 0 and cpu_delta > 0:
            return (cpu_delta / system_delta) * 100.0
    except (KeyError, TypeError, ZeroDivisionError):
        pass
    return 0.0
