# MAA 服务器全托管运维说明

战鸽 **控制面**（LXC 上的 `uvicorn` / systemd）与 **执行面**（`maa-worker` + Redroid）分离。不要把 Redroid / MaaCore 打进控制面进程。

> **与 LXC 主路径的关系（v0.2.15+）**  
> 控制面：`scripts/install.sh` + 管理端「系统更新」（GitHub Release）。  
> 执行面：可选 Docker，需自行 `docker compose -f compose.maa.yml build`；LXC 内嵌套 Docker 常见受限，**默认可不启用 MAA**。

## 架构摘要

| 服务 | 职责 | 权限 |
|------|------|------|
| 控制面 `app` | 台账、审计、用户/管理 API、截图只读 | 不挂 `docker.sock` |
| `maa-worker` | 供给/上下线/销毁、对账、ADB 截图、调用 maa-cli | 挂 `docker.sock` |
| `redroid-*` | 每槽一台 Android + 数据卷 | privileged；ADB 仅内网 |

槽位由**管理员**在「设置 → MAA 资源」新增；用户不可自助开槽。状态机：

`provisioning → online ⇄ offline → destroying → destroyed`（失败 → `error`）

**新增即自动就绪**：Worker 收到 `provision` 后按步骤创建 Android、等待 ADB，成功则 **`online`（就绪）**。

## 启用执行面（可选）

仓库根目录（如 `/opt/zhange-stats`）已含 `compose.maa.yml` 与脚本时：

```bash
cd /opt/zhange-stats
# 确保控制面已在跑，且 .env 中 SECRET_KEY / 派生 token 与 Worker 一致
sudo bash scripts/install-maa-host.sh
```

脚本会：

1. 安装并 **enable** `maa-binder.service`（开机自动 `modprobe binder_linux`）
2. 补写 `.env`：`COMPOSE_PROFILES=maa`、`MAA_APP_BASE_URL=http://host.docker.internal:8000` 等
3. `docker compose -f compose.maa.yml --profile maa build && up -d`

之后日常：

- **重启机器**：binder 由 systemd 自动加载；Worker `restart: unless-stopped`
- **Worker 镜像**：自行 `docker compose -f compose.maa.yml --profile maa build`（预装 `maa-cli`；MaaCore 首次启动时拉取到卷 `maa-cli-data`）
- **开槽**：管理端「新增槽位」→ Worker 自动供给 Android

仅装 binder / 改 env、暂不 `up`：

```bash
sudo bash scripts/install-maa-host.sh --no-up
```

### 鉴权 token（可免手填）

- 显式 `MAA_WORKER_TOKEN` 优先
- 未配置时，**控制面与 Worker 用同一 `SECRET_KEY` 派生**（算法见 `maa_token.resolve_maa_worker_token`）
- 安装脚本仅在既无 token 又无 `SECRET_KEY` 时才写入随机 token

## Proxmox LXC（生产常见）

Redroid 需要 **privileged LXC**（或独立 VM）。非特权 LXC 即使能 `modprobe binder` / binder 探测通过，Redroid 也可能瞬间退出（常见 exit 129、无日志）。

在 **PVE 宿主机**上：

1. 加载并持久化 binder：`modprobe binder_linux devices=binder,hwbinder,vndbinder`，挂载 `/dev/binderfs`，并写入 `modules-load.d` / systemd（见上文一键脚本在 CT 内会失败——模块只在宿主机存在）。
2. CT 配置示例：`unprivileged: 0`，`lxc.mount.entry: /dev/binderfs ...`，`lxc.apparmor.profile: unconfined`。
3. 若从非特权改为特权，必须把 rootfs 内 `100000+` UID/GID 映射回真实 UID（否则 Docker/权限会坏）。

## Windows / Docker Desktop

**Docker Desktop（默认内核）不支持 Redroid**：缺少 `binderfs`。Windows 只跑控制面即可。

本机开发可选（有风险）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\maa-wsl-binder-kernel.ps1
```

## 手动步骤（不使用一键脚本时）

1. 加载 binder：

```bash
sudo apt install -y linux-modules-extra-$(uname -r)
sudo modprobe binder_linux devices="binder,hwbinder,vndbinder"
# 或安装 deploy/systemd/maa-binder.service
```

2. `.env`：

```bash
COMPOSE_PROFILES=maa
# MAA_WORKER_TOKEN=...  # 可选；有 SECRET_KEY 可省略
MAA_MAX_SLOTS=4
MAA_APP_BASE_URL=http://host.docker.internal:8000
```

3. 启动：

```bash
docker compose -f compose.maa.yml --profile maa build
docker compose -f compose.maa.yml --profile maa up -d
```

静态服务 `redroid-poc` 仅供手工 ADB 验证；**生产槽位由 Worker 动态创建**（`zhange-maa-slot-{id}`）。

## PoC 验证清单

1. `adb connect` 到动态槽（Worker 网络内 `{container}:5555`）。
2. 安装明日方舟并完成登录（MVP：管理员内网操作）。
3. 管理端新增槽位 → 进度列显示 `[n/5 …]` → **`online`** → 绑定成员。
4. 用户侧明日方舟 → MAA Tab；日常由 Worker 内预装的 `maa-cli` + MaaCore 执行（`maa run daily -a <adb>`）。

## 安全

- Worker 调 `/api/internal/maa/*`，凭 `MAA_WORKER_TOKEN` 或派生值。
- ADB **不对公网**映射。
- 截图仅经鉴权 API 返回。

## 容量与审计

- 管理端不配固定配额；用户侧按空闲提示。
- 安全阀：`MAA_MAX_SLOTS`。
- 操作写入 `maa_slot_audits`；Worker 对账孤儿容器。

## 封号与合规

服务器托管模拟器/自动化存在封号与 ToS 风险；产品侧需明确告知用户。
