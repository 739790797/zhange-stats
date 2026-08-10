# MAA 服务器全托管运维说明

战鸽 **控制面**（`app`）与 **执行面**（`maa-worker` + Redroid）分离。不要把 Redroid / MaaCore 打进 `app` 镜像。

## 架构摘要

| 服务 | 职责 | 权限 |
|------|------|------|
| `app` | 台账、审计、用户/管理 API、截图只读 | 非 privileged；**不**挂 `docker.sock` |
| `maa-worker` | 供给/上下线/销毁、对账、ADB 截图、调用 maa-cli | 挂 `docker.sock` |
| `redroid-*` | 每槽一台 Android + 数据卷 | privileged；ADB 仅内网 |

槽位由**管理员**在「设置 → MAA 资源」新增；用户不可自助开槽。状态机：

`provisioning → online ⇄ offline → destroying → destroyed`（失败 → `error`）

**新增即自动就绪**：Worker 收到 `provision` 后创建 Android 容器、等待 ADB `device`，成功则直接进入 **`online`（就绪）**；不再默认先下电。

## Windows / Docker Desktop

**Docker Desktop（默认内核）不支持 Redroid**：缺少 `binderfs`，Android 无法完成启动，ADB 长期 `offline` / `供给中`。官方也不计划支持 Desktop 自带 VM。

本机开发可选（有风险）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\maa-wsl-binder-kernel.ps1
```

会安装带 binder 的自定义 WSL2 内核。若 Docker Desktop 起不来，删除 `%USERPROFILE%\.wslconfig` 后执行 `wsl --shutdown` 再开 Docker。

**推荐**：在 Linux 宿主机（R730XD）启用 MAA；Windows 只跑控制面。Worker 在缺少 binder 时会**立即失败**并写明原因，不再无限「供给中」。

## 宿主机准备（R730XD / x86）

1. Linux + Docker，开启 VT-x。
2. 加载 binder（Redroid 需要）：

```bash
sudo apt install -y linux-modules-extra-$(uname -r)
sudo modprobe binder_linux devices="binder,hwbinder,vndbinder"
# 较新内核可能用 binderfs；以 redroid 文档为准
```

3. 建议分辨率 720×1280、软渲染（无独显时 `gpu_mode=guest`）。方舟为 ARM 包，依赖镜像内 libndk；单机预期约 2～4 常驻槽。

## 启用 compose profile

在 `.env`：

```bash
MAA_WORKER_TOKEN=请换成足够长的随机串
MAA_MAX_SLOTS=4
# COMPOSE_PROFILES=maa
```

启动：

```bash
docker compose -f compose.yml -f compose.maa.yml --profile maa up -d --build
```

或设置 `COMPOSE_PROFILES=maa` 后常规 `up -d`。

静态服务 `redroid-poc` 仅供手工 ADB 验证；**生产槽位由 Worker 按台账动态创建**（容器名 `zhange-maa-slot-{id}`）。

## PoC 验证清单

1. `adb connect` 到 poc 或动态槽（Worker 网络内 `{container}:5555`）。
2. 安装明日方舟并完成登录（MVP：管理员内网 scrcpy / 临时投屏；产品文案写明首次登录由管理员完成）。
3. 管理端新增槽位 → Worker 自动创建 Android，等待 ADB `device` 后进入 **`online`（就绪）** → 绑定成员。供给中若 ADB 未就绪会持续重试（见错误列进度），勿误以为卡死。
4. 用户侧明日方舟 → MAA Tab 可见截图；可下发日常（需 Worker 内安装 `maa-cli`，否则任务失败并写明原因）。

> Windows Docker Desktop 上 Redroid 常因缺少 binder 无法完成 `sys.boot_completed`，ADB 会长期 `offline`。生产请用 Linux 宿主机（R730XD）并按上文加载 binder。

## 安全

- `MAA_WORKER_TOKEN` 必填；Worker 调 `/api/internal/maa/*`。
- ADB **不对公网**映射。
- 截图在 `DATA_DIR/maa/{slot_id}/latest.jpg`，仅经鉴权 API 返回，不进公开 StaticFiles。
- Watchtower **不**自动更新 Redroid / maa-worker（label `enable=false`）。

## 容量与审计

- 管理端**不**配置固定配额；用户申请时按实际空闲/占用提示（`/api/maa/me` 的 `availability` / `message`）。
- 可选运维安全阀：环境变量 `MAA_MAX_SLOTS`（防误创过多槽），不在 UI 暴露。
- 每次新增/上线/下线/移除/绑定写入 `maa_slot_audits`。
- Worker 定期对账：台账有容器无 → `error`；带托管标签的孤儿容器 → 删除。

## 封号与合规

云端/模拟器自动化有账号风险；建议白名单内测，并在 UI 明示风险自担。
