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

**新增即自动就绪**：Worker 收到 `provision` 后按步骤创建 Android、等待 ADB，成功则 **`online`（就绪）**。

## 生产一键启用（容器部署 / 仅有旧目录）

Watchtower 只更新 **镜像**，不会改宿主机目录。从 **v0.2.14** 起，`app` 镜像内带 `/app/maa-host/`（`compose.maa.yml`、安装脚本、systemd 单元）。

在宿主机 compose 工程目录（如 `/opt/zhange-stats`）：

```bash
cd /opt/zhange-stats

# 1) 等 Watchtower 拉到新镜像，或手动：
docker pull ghcr.io/739790797/zhange-stats:latest

# 2) 把镜像里的 MAA 宿主机文件导出到当前目录（不碰 .env / data）
docker run --rm -v "$PWD:/host" ghcr.io/739790797/zhange-stats:latest \
  /bin/sh /app/maa-host/scripts/export-to-host.sh

# 3) 一键装 binder + 启 Worker（缺文件时也会再尝试从镜像导出）
sudo bash scripts/install-maa-host.sh
```

若宿主机 `compose.yml` 已更新，也可用：

```bash
docker compose --profile maa-export run --rm maa-host-export
sudo bash scripts/install-maa-host.sh
```

脚本会自动：

1. 安装并 **enable** `maa-binder.service`（开机自动 `modprobe binder_linux`）
2. 补写 `.env`：`COMPOSE_PROFILES=maa`（及镜像名；token 可留空，见下）
3. `docker compose … pull && up -d` 拉起 `maa-worker`

之后日常：

- **重启机器**：binder 由 systemd 自动加载；Worker `restart: unless-stopped`
- **发版**：CI 推送 `zhange-stats` 与 `zhange-stats-maa-worker`；Watchtower 更新容器；宿主机文件可用上面的 `export` 再同步一次
- **开槽**：管理端「新增槽位」→ Worker 自动供给 Android

仅装 binder / 改 env、暂不 `up`：

```bash
sudo bash scripts/install-maa-host.sh --no-up
```

### 鉴权 token（可免手填）

- 显式 `MAA_WORKER_TOKEN` 优先
- 未配置时，**app 与 Worker 用同一 `SECRET_KEY` 派生**（算法见 `maa_token.resolve_maa_worker_token`）
- 安装脚本仅在既无 token 又无 `SECRET_KEY` 时才写入随机 token

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
```

3. 启动：

```bash
docker compose -f compose.yml -f compose.maa.yml --profile maa pull
docker compose -f compose.yml -f compose.maa.yml --profile maa up -d
```

静态服务 `redroid-poc` 仅供手工 ADB 验证；**生产槽位由 Worker 动态创建**（`zhange-maa-slot-{id}`）。

## PoC 验证清单

1. `adb connect` 到动态槽（Worker 网络内 `{container}:5555`）。
2. 安装明日方舟并完成登录（MVP：管理员内网操作）。
3. 管理端新增槽位 → 进度列显示 `[n/5 …]` → **`online`** → 绑定成员。
4. 用户侧明日方舟 → MAA Tab；日常需 Worker 内 `maa-cli`（未装则任务失败并写明原因）。

## 安全

- Worker 调 `/api/internal/maa/*`，凭 `MAA_WORKER_TOKEN` 或派生值。
- ADB **不对公网**映射。
- 截图仅经鉴权 API 返回。
- Watchtower 管理带 `watchtower.enable=true` 的服务（app + maa-worker）；`redroid-poc` 关闭自动更新。

## 容量与审计

- 管理端不配固定配额；用户侧按空闲提示。
- 安全阀：`MAA_MAX_SLOTS`。
- 操作写入 `maa_slot_audits`；Worker 对账孤儿容器。

## 封号与合规

服务器托管模拟器/自动化存在封号与 ToS 风险；产品侧需明确告知用户。
