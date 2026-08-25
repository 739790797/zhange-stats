import { DownOutlined, LeftOutlined, RightOutlined } from "@ant-design/icons";
import { Button, Spin } from "antd";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { formatBeijing } from "@/lib/time";
import {
  DEFAULT_SERVER_ICON,
  MC_ICONS,
  SERVER_KINDS,
  VERSION_CHANNELS,
  classifyMcVersion,
  coresForKind,
  findServerCore,
  findServerKind,
  groupMcVersions,
  setupIcon,
  versionChannelIcon,
  type McGameVersion,
  type MinecraftSetupValue,
  type ServerKind,
} from "./minecraftUi";
import styles from "./MinecraftSetupPicker.module.css";

type Pane = "versions" | "kinds" | "cores";

type Props = {
  versions: McGameVersion[];
  loading?: boolean;
  value: MinecraftSetupValue;
  done?: boolean;
  currentLabel?: string;
  onChange: (next: MinecraftSetupValue) => void;
  onComplete: (next: MinecraftSetupValue) => void;
  onEdit?: () => void;
  onUseCurrent?: () => void;
};

function releasedAt(row: McGameVersion) {
  if (!row.release_time) return "";
  return `发布于 ${formatBeijing(row.release_time, "YYYY/MM/DD HH:mm")}`;
}

function SetupIcon({ src }: { src: string }) {
  return (
    <img className={styles.icon} src={src || DEFAULT_SERVER_ICON} alt="" draggable={false} />
  );
}

function Row({
  title,
  meta,
  hint,
  icon,
  active,
  onClick,
}: {
  title: string;
  meta?: string;
  hint?: string;
  icon: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={active ? `${styles.row} ${styles.rowActive}` : styles.row}
      onClick={onClick}
    >
      <SetupIcon src={icon} />
      <span className={styles.body}>
        <span className={styles.title}>{title}</span>
        {meta ? <span className={styles.meta}>{meta}</span> : null}
      </span>
      {hint ? <span className={styles.hint}>{hint}</span> : null}
      <RightOutlined className={styles.chev} />
    </button>
  );
}

function Group({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section className={styles.card}>
      <button
        type="button"
        className={styles.groupHead}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {title}
        <DownOutlined className={styles.chev} rotate={open ? 180 : 0} />
      </button>
      {open ? <div className={styles.groupList}>{children}</div> : null}
    </section>
  );
}

function DrillHeader({
  version,
  icon,
  onBack,
}: {
  version: string;
  icon?: string;
  onBack: () => void;
}) {
  return (
    <div className={`${styles.card} ${styles.header}`}>
      <button type="button" className={styles.back} onClick={onBack} aria-label="返回">
        <LeftOutlined />
      </button>
      <SetupIcon src={icon || MC_ICONS.vanilla} />
      <div className={styles.versionBox}>{version}</div>
    </div>
  );
}

export function MinecraftSetupPicker({
  versions,
  loading,
  value,
  done,
  currentLabel,
  onChange,
  onComplete,
  onEdit,
  onUseCurrent,
}: Props) {
  const [pane, setPane] = useState<Pane>("versions");
  const grouped = useMemo(() => groupMcVersions(versions), [versions]);

  useEffect(() => {
    if (!done) setPane("versions");
  }, [done]);

  if (done) {
    const kind = findServerKind(value.kind);
    const core = findServerCore(value.kind, value.core);
    return (
      <div className={styles.picker}>
        <div className={`${styles.card} ${styles.summary}`}>
          <SetupIcon src={setupIcon(value)} />
          <div className={styles.summaryBody}>
            <div className={styles.title}>{value.mcVersion || "未选版本"}</div>
            <div className={styles.meta}>
              {[kind?.name, core?.name].filter(Boolean).join(" · ") || "未选核心"}
            </div>
          </div>
          <Button type="link" size="small" onClick={onEdit}>
            更改
          </Button>
        </div>
      </div>
    );
  }

  const pickVersion = (version: string) => {
    onChange({ mcVersion: version, kind: "", core: "" });
    setPane("kinds");
  };

  const pickKind = (kind: ServerKind) => {
    if (kind === "vanilla") {
      const next: MinecraftSetupValue = {
        mcVersion: value.mcVersion,
        kind,
        core: "vanilla",
      };
      onChange(next);
      onComplete(next);
      return;
    }
    onChange({ mcVersion: value.mcVersion, kind, core: "" });
    setPane("cores");
  };

  const pickCore = (core: string) => {
    const next: MinecraftSetupValue = {
      mcVersion: value.mcVersion,
      kind: value.kind,
      core,
    };
    onChange(next);
    onComplete(next);
  };

  if (pane === "kinds" && value.mcVersion) {
    return (
      <div className={styles.picker}>
        <DrillHeader
          version={value.mcVersion}
          icon={MC_ICONS.vanilla}
          onBack={() => setPane("versions")}
        />
        <div className={styles.card}>
          <div className={styles.coreList}>
            {SERVER_KINDS.map((row) => (
              <Row
                key={row.key}
                title={row.name}
                meta={row.hint}
                icon={row.icon}
                active={value.kind === row.key}
                onClick={() => pickKind(row.key)}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (pane === "cores" && value.mcVersion && value.kind) {
    const kind = findServerKind(value.kind);
    return (
      <div className={styles.picker}>
        <DrillHeader
          version={`${value.mcVersion}${kind ? ` · ${kind.name}` : ""}`}
          icon={kind?.icon || MC_ICONS.vanilla}
          onBack={() => setPane("kinds")}
        />
        <div className={styles.card}>
          <div className={styles.coreList}>
            {coresForKind(value.kind).map((row) => (
              <Row
                key={row.key}
                title={row.name}
                hint={row.hint}
                icon={row.icon}
                active={value.core === row.key}
                onClick={() => pickCore(row.key)}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.picker}>
      {currentLabel && onUseCurrent ? (
        <button type="button" className={styles.skip} onClick={onUseCurrent}>
          <span className={styles.skipLabel}>继续当前草稿</span>
          <span className={styles.skipValue}>{currentLabel}</span>
          <RightOutlined className={styles.chev} />
        </button>
      ) : null}

      <section className={`${styles.card} ${styles.latest}`}>
        <div className={styles.latestTitle}>最新版本</div>
        {loading && !versions.length ? (
          <div className={styles.empty}>
            <Spin size="small" /> 正在拉取版本列表…
          </div>
        ) : null}
        {grouped.latestRelease ? (
          <Row
            title={grouped.latestRelease.version}
            meta={["最新正式版", releasedAt(grouped.latestRelease)]
              .filter(Boolean)
              .join("，")}
            icon={MC_ICONS.vanilla}
            active={value.mcVersion === grouped.latestRelease.version}
            onClick={() => pickVersion(grouped.latestRelease!.version)}
          />
        ) : null}
        {grouped.latestSnapshot &&
        grouped.latestSnapshot.version !== grouped.latestRelease?.version ? (
          <Row
            title={grouped.latestSnapshot.version}
            meta={["最新预览版", releasedAt(grouped.latestSnapshot)]
              .filter(Boolean)
              .join("，")}
            icon={versionChannelIcon(classifyMcVersion(grouped.latestSnapshot))}
            active={value.mcVersion === grouped.latestSnapshot.version}
            onClick={() => pickVersion(grouped.latestSnapshot!.version)}
          />
        ) : null}
        {!loading && !grouped.latestRelease && !grouped.latestSnapshot ? (
          <div className={styles.empty}>暂时拉不到版本列表</div>
        ) : null}
      </section>

      {VERSION_CHANNELS.map((channel) => {
        const rows = grouped.groups[channel.key];
        if (!rows.length) return null;
        return (
          <Group key={channel.key} title={channel.title}>
            {rows.map((row) => (
              <Row
                key={row.version}
                title={row.version}
                meta={releasedAt(row)}
                icon={versionChannelIcon(classifyMcVersion(row))}
                active={value.mcVersion === row.version}
                onClick={() => pickVersion(row.version)}
              />
            ))}
          </Group>
        );
      })}
    </div>
  );
}
