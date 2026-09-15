import { DatePicker, Modal } from "antd";
import { useEffect, useMemo, useState } from "react";
import type { Dayjs } from "dayjs";
import { datePickerLocale } from "@/locales/zhCN";
import { nowBeijing, parseBeijing } from "@/lib/time";
import type { TarkovLogSessionStub } from "@/lib/tarkovGameLogs";
import {
  collectLogBreakpoints,
  defaultLogBreakpoint,
  formatLogBreakpointLabel,
  latestIdentityForMode,
  sessionStubMatchesBreakpoint,
  type TarkovLogBreakpoint,
} from "@/lib/tarkovLogBreakpoints";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  filterSessionStubsByRange,
  formatCrossWipeHint,
  formatLogSyncRangeDays,
  formatLogSyncSessionCount,
  rangeStartsBeforeCurrentWipe,
  resolveLogSyncRange,
  sessionStubDateBounds,
  wipeStartBeijingClock,
  wipesTouchedBySessions,
  type TarkovLogSyncPreset,
  type TarkovLogSyncRange,
} from "@/lib/tarkovLogSyncRange";
import { currentWipeStart } from "@/lib/tarkovWipeLength";
import styles from "./TarkovLogSyncRangeModal.module.css";

const PRESETS: Array<{ id: TarkovLogSyncPreset; label: string }> = [
  { id: "all", label: "全部" },
  { id: "wipe", label: "本赛季" },
  { id: "7d", label: "近 7 天" },
  { id: "30d", label: "近 30 天" },
  { id: "custom", label: "自定义" },
];

type Props = {
  open: boolean;
  sessions: readonly TarkovLogSessionStub[];
  onCancel: () => void;
  onConfirm: (range: TarkovLogSyncRange) => void;
};

function breakpointValue(row: TarkovLogBreakpoint): string {
  return `${row.version}|${row.profileId}|${row.sessionMode}|${row.at}`;
}

export function TarkovLogSyncRangeModal({
  open,
  sessions,
  onCancel,
  onConfirm,
}: Props) {
  const gameMode = useTarkovGameMode();
  const wipe = useMemo(() => currentWipeStart(), []);
  const bounds = useMemo(() => sessionStubDateBounds(sessions), [sessions]);
  const today = nowBeijing().format("YYYY-MM-DD");
  const [preset, setPreset] = useState<TarkovLogSyncPreset>("all");
  const [customFrom, setCustomFrom] = useState(today);
  const [customTo, setCustomTo] = useState(today);
  const [breakpointKey, setBreakpointKey] = useState("");
  const [lackedDefault, setLackedDefault] = useState(false);

  const identities = useMemo(
    () => sessions.flatMap((stub) => stub.identities || []),
    [sessions],
  );
  const breakpoints = useMemo(
    () => collectLogBreakpoints(identities),
    [identities],
  );

  useEffect(() => {
    if (!open) return;
    setPreset("all");
    setCustomFrom(bounds.min || today);
    setCustomTo(bounds.max || today);
    const picked = defaultLogBreakpoint(breakpoints, {
      gameMode,
      wipeFrom: wipeStartBeijingClock(wipe),
      latest: latestIdentityForMode(identities, gameMode),
    });
    setBreakpointKey(picked ? breakpointValue(picked) : "");
    setLackedDefault(!picked);
  }, [bounds.max, bounds.min, breakpoints, gameMode, identities, open, today, wipe]);

  const range = useMemo(
    () =>
      resolveLogSyncRange({
        preset,
        customFrom,
        customTo,
      }),
    [customFrom, customTo, preset],
  );
  const selectedBreakpoint = useMemo(
    () => breakpoints.find((row) => breakpointValue(row) === breakpointKey) || null,
    [breakpointKey, breakpoints],
  );
  const matched = useMemo(
    () =>
      filterSessionStubsByRange(sessions, range).filter((stub) =>
        sessionStubMatchesBreakpoint(stub, selectedBreakpoint),
      ),
    [range, selectedBreakpoint, sessions],
  );
  const priorWipe = rangeStartsBeforeCurrentWipe(range);
  const crossWipes = useMemo(
    () => wipesTouchedBySessions(matched),
    [matched],
  );
  const crossWipeHint = formatCrossWipeHint(crossWipes);
  const pickerValue = useMemo((): [Dayjs, Dayjs] => {
    return [parseBeijing(customFrom), parseBeijing(customTo)];
  }, [customFrom, customTo]);

  return (
    <Modal
      title="同步日志"
      open={open}
      onCancel={onCancel}
      footer={
        <div className={styles.footer}>
          <button type="button" className={styles.cancel} onClick={onCancel}>
            取消
          </button>
          <button
            type="button"
            className={styles.ok}
            disabled={!matched.length}
            onClick={() =>
              onConfirm({
                ...range,
                breakpoint: selectedBreakpoint
                  ? {
                      version: selectedBreakpoint.version,
                      profileId: selectedBreakpoint.profileId,
                      sessionMode: selectedBreakpoint.sessionMode,
                      at: selectedBreakpoint.at,
                    }
                  : undefined,
              })
            }
          >
            开始同步
          </button>
        </div>
      }
      width={520}
      destroyOnClose
      classNames={{ body: styles.body }}
    >
      <p className={styles.lead}>
        本机解析启动文件夹，只把任务状态回填到账号，不会上传日志原文。默认从当前
        {gameMode === "pve" ? " PvE" : " 正式"}角色在本赛季第一次出现的启动读到现在
        {wipe?.name ? `（${wipe.name}）` : ""}
        。
      </p>
      {breakpoints.length ? (
        <label className={styles.breakLabel}>
          从这次启动起
          <select
            className={styles.breakSelect}
            value={breakpointKey}
            onChange={(event) => setBreakpointKey(event.target.value)}
          >
            <option value="">不按角色过滤</option>
            {breakpoints.map((row) => (
              <option key={breakpointValue(row)} value={breakpointValue(row)}>
                {formatLogBreakpointLabel(row)}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p className={styles.meta}>这些日志里还没有读到 ProfileId / Session mode。</p>
      )}
      <div className={styles.presets} role="radiogroup" aria-label="日期范围">
        {PRESETS.map((row) => (
          <button
            key={row.id}
            type="button"
            role="radio"
            aria-checked={preset === row.id}
            className={`${styles.preset}${preset === row.id ? ` ${styles.presetOn}` : ""}`}
            onClick={() => {
              if (row.id === "custom") {
                setCustomFrom(parseBeijing(range.from).format("YYYY-MM-DD"));
                setCustomTo(parseBeijing(range.to).format("YYYY-MM-DD"));
              }
              setPreset(row.id);
            }}
          >
            {row.id === "wipe" && wipe?.name
              ? `${row.label}（${wipe.name}）`
              : row.label}
          </button>
        ))}
      </div>
      {preset === "custom" ? (
        <DatePicker.RangePicker
          className={styles.picker}
          locale={datePickerLocale}
          allowClear={false}
          value={pickerValue}
          disabledDate={(day) => day.isAfter(nowBeijing(), "day")}
          onChange={(next) => {
            if (!next?.[0] || !next[1]) return;
            setCustomFrom(next[0].format("YYYY-MM-DD"));
            setCustomTo(next[1].format("YYYY-MM-DD"));
          }}
        />
      ) : null}
      <p className={styles.count}>{formatLogSyncSessionCount(matched.length)}</p>
      <p className={styles.meta}>
        范围 {formatLogSyncRangeDays(range)}
        {bounds.min && bounds.max
          ? `。目录最早 ${bounds.min}，最晚 ${bounds.max}`
          : sessions.length
            ? "。这些文件夹没有可识别的启动日期"
            : "。这个目录里没有启动记录"}
      </p>
      {crossWipeHint ? <p className={styles.warn}>{crossWipeHint}</p> : null}
      {lackedDefault && !selectedBreakpoint ? (
        <p className={styles.warn}>
          日志里没有当前模式的角色断点，这次按日期范围读，仍只写入本页正式 / PvE
          账，赛季进度不会并进来。
        </p>
      ) : null}
      {priorWipe ? (
        <p className={styles.warn}>
          自定义范围早于本赛季，会带上旧赛季完成记录。
        </p>
      ) : null}
    </Modal>
  );
}
