import {
  CaretRightOutlined,
  PauseOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  InputNumber,
  Popconfirm,
  Progress,
  Select,
  Tag,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  runMinecraftModToolCommand,
  type MinecraftModFeature,
  type MinecraftModTools,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import styles from "./MinecraftModFeature.module.css";

const STATE_TAG: Record<string, { color: string; label: string }> = {
  running: { color: "green", label: "渲染中" },
  paused: { color: "orange", label: "因人数暂停" },
  stopped: { color: "red", label: "已停止" },
  idle: { color: "default", label: "空闲" },
};

const DEFAULT_MAPS = ["world", "world_nether", "world_the_end"];

function taskLabel(task: string) {
  if (task === "purged") return "正在清空";
  if (task === "updated") return "正在更新";
  return task || "—";
}

export function MinecraftBluemapWorkspace({
  data,
  canCommand,
  feature,
}: {
  data: MinecraftModTools;
  canCommand: boolean;
  feature?: MinecraftModFeature;
}) {
  const queryClient = useQueryClient();
  const status = data.bluemap;
  const maps = useMemo(() => {
    return [
      ...new Set(
        [...(status?.maps || []), ...(data.worlds || []), ...DEFAULT_MAPS].filter(
          Boolean,
        ),
      ),
    ];
  }, [status?.maps, data.worlds]);
  const [mapId, setMapId] = useState(status?.current_map || maps[0] || "world");
  const [centerX, setCenterX] = useState<number | null>(0);
  const [centerZ, setCenterZ] = useState<number | null>(0);
  const [radius, setRadius] = useState<number | null>(null);
  const [log, setLog] = useState(status?.raw || "");
  const [didSeed, setDidSeed] = useState(false);

  useEffect(() => {
    if (!status) return;
    if (status.raw) setLog(status.raw);
    if (didSeed) return;
    if (status.current_map) setMapId(status.current_map);
    setDidSeed(true);
  }, [status, didSeed]);

  const argsFor = (commandId: string) => {
    if (["start", "stop", "status"].includes(commandId)) return {};
    const payload: Record<string, string | number> = { map: mapId.trim() };
    if (
      ["update", "force-update", "fix-edges"].includes(commandId) &&
      radius != null
    ) {
      payload.x = centerX ?? 0;
      payload.z = centerZ ?? 0;
      payload.radius = radius;
    }
    return payload;
  };

  const run = useMutation({
    mutationFn: (commandId: string) =>
      runMinecraftModToolCommand("bluemap", {
        command_id: commandId,
        args: argsFor(commandId),
      }),
    onSuccess: (res) => {
      if (res.message) message.success(res.message);
      else message.success("已发送");
      if (res.raw) setLog(res.raw);
      const nextMap = res.bluemap?.current_map;
      if (nextMap) setMapId(nextMap);
      queryClient.invalidateQueries({ queryKey: ["minecraft-mod-tools"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "BlueMap 指令失败")),
  });

  const busy = run.isPending;
  const state = status?.state || "idle";
  const tag = STATE_TAG[state] || STATE_TAG.idle;
  const percent =
    status?.percent != null && Number.isFinite(status.percent)
      ? Math.max(0, Math.min(100, status.percent))
      : null;
  const frozen = status?.frozen_maps || [];

  return (
    <>
      <div className={styles.workspace}>
        <section>
          <div className={styles.paneTitle}>
            {feature?.title || "更新范围"}
          </div>
          <p className={styles.hint}>
            {feature?.summary ||
              "不填半径则更新整张图。BlueMap 平时会自动增量更新，改过配置或漏渲时才需要手动触发。"}
          </p>
          <div className={styles.grid}>
            <div className={styles.field}>
              <label>地图</label>
              <Select
                showSearch
                value={mapId}
                onChange={setMapId}
                options={maps.map((name) => ({ value: name, label: name }))}
                style={{ width: "100%" }}
              />
            </div>
            <div className={styles.field}>
              <label>中心 X</label>
              <InputNumber
                value={centerX}
                onChange={setCenterX}
                style={{ width: "100%" }}
              />
            </div>
            <div className={styles.field}>
              <label>中心 Z</label>
              <InputNumber
                value={centerZ}
                onChange={setCenterZ}
                style={{ width: "100%" }}
              />
            </div>
            <div className={styles.field}>
              <label>半径（方块，可空）</label>
              <InputNumber
                min={1}
                max={1_000_000}
                value={radius}
                onChange={setRadius}
                placeholder="整张图"
                style={{ width: "100%" }}
              />
            </div>
          </div>
        </section>

        <section className={styles.progressPane}>
          <div className={styles.paneTitle}>
            <span>渲染状态</span>
            <Tag color={tag.color}>{tag.label}</Tag>
          </div>
          <div className={styles.percentRow}>
            <span className={styles.percent}>
              {percent == null ? "0" : percent.toFixed(percent < 10 ? 1 : 0)}
            </span>
            <span className={styles.percentUnit}>%</span>
          </div>
          <Progress
            percent={percent == null ? 0 : Number(percent.toFixed(2))}
            status={state === "running" ? "active" : "normal"}
            showInfo={false}
          />
          <div className={styles.stats}>
            <div className={styles.stat}>
              <span className={styles.statLabel}>线程</span>
              <span className={styles.statValue}>
                {status?.threads != null ? status.threads : "—"}
              </span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>当前地图</span>
              <span className={styles.statValue}>
                {status?.current_map || "—"}
              </span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>当前任务</span>
              <span className={styles.statValue}>
                {taskLabel(status?.current_task || "")}
              </span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>剩余</span>
              <span className={styles.statValue}>{status?.eta || "—"}</span>
            </div>
          </div>
          {frozen.length ? (
            <div className={styles.tags}>
              {frozen.map((name) => (
                <Tag key={name} color="blue">
                  已冻结 {name}
                </Tag>
              ))}
            </div>
          ) : null}
          <div className={styles.controls}>
            <Button
              type="primary"
              icon={<CaretRightOutlined />}
              loading={busy && run.variables === "start"}
              disabled={!canCommand || busy || state === "running"}
              onClick={() => run.mutate("start")}
            >
              开始渲染
            </Button>
            <div className={styles.controlRow}>
              <Button
                icon={<PauseOutlined />}
                loading={busy && run.variables === "stop"}
                disabled={!canCommand || busy || state === "stopped"}
                onClick={() => run.mutate("stop")}
              >
                停止渲染
              </Button>
              <Button
                icon={<ReloadOutlined />}
                loading={busy && run.variables === "status"}
                disabled={!canCommand || busy}
                onClick={() => run.mutate("status")}
              >
                刷新状态
              </Button>
            </div>
            <div className={styles.controlRow3}>
              <Button
                loading={busy && run.variables === "update"}
                disabled={!canCommand || busy || !mapId.trim()}
                onClick={() => run.mutate("update")}
              >
                增量更新
              </Button>
              <Popconfirm
                title="会无视改动检测、整图重渲，耗时长。确定强制更新？"
                okText="强制重渲"
                cancelText="返回"
                disabled={!canCommand || busy || !mapId.trim()}
                onConfirm={() => run.mutate("force-update")}
              >
                <Button
                  loading={busy && run.variables === "force-update"}
                  disabled={!canCommand || busy || !mapId.trim()}
                >
                  强制重渲
                </Button>
              </Popconfirm>
              <Button
                loading={busy && run.variables === "fix-edges"}
                disabled={!canCommand || busy || !mapId.trim()}
                onClick={() => run.mutate("fix-edges")}
              >
                修边
              </Button>
            </div>
            <div className={styles.controlRow3}>
              <Button
                loading={busy && run.variables === "freeze"}
                disabled={!canCommand || busy || !mapId.trim()}
                onClick={() => run.mutate("freeze")}
              >
                冻结
              </Button>
              <Button
                loading={busy && run.variables === "unfreeze"}
                disabled={!canCommand || busy || !mapId.trim()}
                onClick={() => run.mutate("unfreeze")}
              >
                解冻
              </Button>
              <Popconfirm
                title="会删除该地图已渲数据并重新渲染，期间网页地图不可用。确定清空？"
                okText="清空地图"
                cancelText="返回"
                okButtonProps={{ danger: true }}
                disabled={!canCommand || busy || !mapId.trim()}
                onConfirm={() => run.mutate("purge")}
              >
                <Button
                  danger
                  loading={busy && run.variables === "purge"}
                  disabled={!canCommand || busy || !mapId.trim()}
                >
                  清空地图
                </Button>
              </Popconfirm>
            </div>
          </div>
        </section>
      </div>
      {log ? (
        <details className={styles.logDetails}>
          <summary>RCON 输出</summary>
          <pre className={styles.log}>{log}</pre>
        </details>
      ) : null}
    </>
  );
}
