import {
  CaretRightOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  StopOutlined,
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
  runMinecraftChunkyCommand,
  type MinecraftChunkyAction,
  type MinecraftModTools,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import styles from "./MinecraftChunkyWorkspace.module.css";

const SHAPE_OPTIONS = [
  { value: "square", label: "正方形" },
  { value: "circle", label: "圆形" },
  { value: "diamond", label: "菱形" },
  { value: "ellipse", label: "椭圆" },
  { value: "rectangle", label: "矩形" },
  { value: "hexagon", label: "六边形" },
  { value: "star", label: "星形" },
];

const PATTERN_OPTIONS = [
  { value: "concentric", label: "由内向外" },
  { value: "loop", label: "逐行" },
  { value: "spiral", label: "螺旋" },
];

const RADIUS_PRESETS = [500, 1000, 2000, 5000, 10000];

const STATE_TAG: Record<string, { color: string; label: string }> = {
  running: { color: "green", label: "生成中" },
  paused: { color: "orange", label: "已暂停" },
  idle: { color: "default", label: "空闲" },
};

function formatCount(n?: number | null) {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toLocaleString("zh-CN");
}

export function MinecraftChunkyWorkspace({
  data,
  canCommand,
}: {
  data: MinecraftModTools;
  canCommand: boolean;
}) {
  const queryClient = useQueryClient();
  const status = data.chunky;
  const [world, setWorld] = useState(status?.world || "world");
  const [shape, setShape] = useState(status?.shape || "square");
  const [pattern, setPattern] = useState(status?.pattern || "concentric");
  const [centerX, setCenterX] = useState<number | null>(status?.center_x ?? 0);
  const [centerZ, setCenterZ] = useState<number | null>(status?.center_z ?? 0);
  const [radius, setRadius] = useState<number | null>(status?.radius ?? 500);
  const [log, setLog] = useState(status?.raw || "");
  const [didSeed, setDidSeed] = useState(false);

  useEffect(() => {
    if (!status) return;
    if (status.raw) setLog(status.raw);
    if (didSeed) return;
    if (status.world) setWorld(status.world);
    if (status.shape) setShape(status.shape);
    if (status.pattern) setPattern(status.pattern);
    if (status.center_x != null) setCenterX(status.center_x);
    if (status.center_z != null) setCenterZ(status.center_z);
    if (status.radius != null) setRadius(status.radius);
    setDidSeed(true);
  }, [status, didSeed]);

  const payload = useMemo(
    () => ({
      world: world.trim(),
      shape,
      pattern,
      center_x: centerX,
      center_z: centerZ,
      radius,
    }),
    [world, shape, pattern, centerX, centerZ, radius],
  );

  const run = useMutation({
    mutationFn: (action: MinecraftChunkyAction) =>
      runMinecraftChunkyCommand({ action, ...payload }),
    onSuccess: (res) => {
      if (res.message) message.success(res.message);
      if (res.raw) setLog(res.raw);
      const next = res.status;
      if (next?.world) setWorld(next.world);
      if (next?.shape) setShape(next.shape);
      if (next?.pattern) setPattern(next.pattern);
      if (next?.center_x != null) setCenterX(next.center_x);
      if (next?.center_z != null) setCenterZ(next.center_z);
      if (next?.radius != null) setRadius(next.radius);
      queryClient.invalidateQueries({ queryKey: ["minecraft-mod-tools"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "Chunky 指令失败")),
  });

  const busy = run.isPending;
  const state = status?.state || "idle";
  const tag = STATE_TAG[state] || STATE_TAG.idle;
  const percent =
    status?.percent != null && Number.isFinite(status.percent)
      ? Math.max(0, Math.min(100, status.percent))
      : null;
  const worlds = useMemo(() => {
    const extra = [
      "minecraft:overworld",
      "minecraft:the_nether",
      "minecraft:the_end",
    ];
    const names = [...(data.worlds || []), ...extra, world || "world"];
    return [...new Set(names.filter(Boolean))];
  }, [data.worlds, world]);

  return (
    <>
      <div className={styles.workspace}>
        <section>
          <div className={styles.paneTitle}>生成范围</div>
          <p className={styles.hint}>
            半径按方块计。500 大约覆盖 1000×1000 区域，过程可随时暂停，进度会保留。
          </p>
          <div className={styles.grid}>
            <div className={styles.field}>
              <label>世界</label>
              <Select
                showSearch
                value={world}
                onChange={setWorld}
                options={worlds.map((name) => ({ value: name, label: name }))}
                style={{ width: "100%" }}
              />
            </div>
            <div className={styles.field}>
              <label>形状</label>
              <Select
                value={shape}
                onChange={setShape}
                options={SHAPE_OPTIONS}
                style={{ width: "100%" }}
              />
            </div>
            <div className={styles.field}>
              <label>模式</label>
              <Select
                value={pattern}
                onChange={setPattern}
                options={PATTERN_OPTIONS}
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
              <label>半径（方块）</label>
              <InputNumber
                min={1}
                max={1_000_000}
                value={radius}
                onChange={setRadius}
                style={{ width: "100%" }}
              />
            </div>
          </div>
          <div className={styles.presets}>
            <span className={styles.presetLabel}>常用半径</span>
            {RADIUS_PRESETS.map((value) => (
              <Button
                key={value}
                size="small"
                type={radius === value ? "primary" : "default"}
                onClick={() => setRadius(value)}
              >
                {value.toLocaleString("zh-CN")}
              </Button>
            ))}
          </div>
          <div className={styles.secondaryActions}>
            <Button
              disabled={!canCommand || busy}
              onClick={() => run.mutate("apply")}
            >
              应用到选择
            </Button>
          </div>
        </section>

        <section className={styles.progressPane}>
          <div className={styles.paneTitle}>
            <span>进度</span>
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
              <span className={styles.statLabel}>区块</span>
              <span className={styles.statValue}>
                {formatCount(status?.chunks)}
                {status?.chunks_total != null
                  ? ` / ${formatCount(status.chunks_total)}`
                  : ""}
              </span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>速率</span>
              <span className={styles.statValue}>
                {status?.rate != null ? `${status.rate.toFixed(1)} cps` : "—"}
              </span>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>剩余</span>
              <span className={styles.statValue}>{status?.eta || "—"}</span>
            </div>
            {status?.chunk_x != null && status?.chunk_z != null ? (
              <div className={styles.stat}>
                <span className={styles.statLabel}>当前区块</span>
                <span className={styles.statValue}>
                  {status.chunk_x}, {status.chunk_z}
                </span>
              </div>
            ) : null}
          </div>
          <div className={styles.controls}>
            {status?.needs_confirm ? (
              <Button
                type="primary"
                danger
                loading={busy && run.variables === "confirm"}
                disabled={!canCommand || busy}
                onClick={() => run.mutate("confirm")}
              >
                确认继续
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<CaretRightOutlined />}
                loading={busy && run.variables === "start"}
                disabled={!canCommand || busy || state === "running"}
                onClick={() => run.mutate("start")}
              >
                开始生成
              </Button>
            )}
            <div className={styles.controlRow}>
              <Button
                icon={<PauseOutlined />}
                loading={busy && run.variables === "pause"}
                disabled={!canCommand || busy || state !== "running"}
                onClick={() => run.mutate("pause")}
              >
                暂停
              </Button>
              <Button
                icon={<PlayCircleOutlined />}
                loading={busy && run.variables === "continue"}
                disabled={!canCommand || busy || state === "running"}
                onClick={() => run.mutate("continue")}
              >
                继续
              </Button>
              <Popconfirm
                title="取消会丢掉未完成的生成进度（已写出的区块仍在）。确定取消？"
                okText="取消任务"
                cancelText="返回"
                okButtonProps={{ danger: true }}
                disabled={!canCommand || busy}
                onConfirm={() => run.mutate("cancel")}
              >
                <Button
                  danger
                  icon={<StopOutlined />}
                  loading={busy && run.variables === "cancel"}
                  disabled={!canCommand || busy || state === "idle"}
                >
                  取消
                </Button>
              </Popconfirm>
              <Button
                icon={<ReloadOutlined />}
                loading={busy && run.variables === "progress"}
                disabled={!canCommand || busy}
                onClick={() => run.mutate("progress")}
              >
                刷新进度
              </Button>
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
