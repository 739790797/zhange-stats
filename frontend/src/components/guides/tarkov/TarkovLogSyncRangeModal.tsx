import { DatePicker, Modal } from "antd";
import { useEffect, useMemo, useState } from "react";
import type { Dayjs } from "dayjs";
import { datePickerLocale } from "@/locales/zhCN";
import { nowBeijing, parseBeijing } from "@/lib/time";
import type { TarkovLogSessionStub } from "@/lib/tarkovGameLogs";
import {
  filterSessionStubsByRange,
  formatLogSyncRangeDays,
  formatLogSyncSessionCount,
  rangeStartsBeforeCurrentWipe,
  resolveLogSyncRange,
  sessionStubDateBounds,
  type TarkovLogSyncPreset,
  type TarkovLogSyncRange,
} from "@/lib/tarkovLogSyncRange";
import { currentWipeStart } from "@/lib/tarkovWipeLength";
import styles from "./TarkovLogSyncRangeModal.module.css";

const PRESETS: Array<{ id: TarkovLogSyncPreset; label: string }> = [
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

export function TarkovLogSyncRangeModal({
  open,
  sessions,
  onCancel,
  onConfirm,
}: Props) {
  const wipe = useMemo(() => currentWipeStart(), []);
  const bounds = useMemo(() => sessionStubDateBounds(sessions), [sessions]);
  const today = nowBeijing().format("YYYY-MM-DD");
  const [preset, setPreset] = useState<TarkovLogSyncPreset>("wipe");
  const [customFrom, setCustomFrom] = useState(today);
  const [customTo, setCustomTo] = useState(today);

  useEffect(() => {
    if (!open) return;
    setPreset("wipe");
    const wipeRange = resolveLogSyncRange({ preset: "wipe" });
    setCustomFrom(parseBeijing(wipeRange.from).format("YYYY-MM-DD"));
    setCustomTo(bounds.max || parseBeijing(wipeRange.to).format("YYYY-MM-DD"));
  }, [open, bounds.max]);

  const range = useMemo(
    () =>
      resolveLogSyncRange({
        preset,
        customFrom,
        customTo,
      }),
    [customFrom, customTo, preset],
  );
  const matched = useMemo(
    () => filterSessionStubsByRange(sessions, range),
    [range, sessions],
  );
  const priorWipe = rangeStartsBeforeCurrentWipe(range);
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
            onClick={() => onConfirm(range)}
          >
            开始同步
          </button>
        </div>
      }
      width={440}
      destroyOnClose
      classNames={{ body: styles.body }}
    >
      <p className={styles.lead}>
        本机解析启动文件夹，只把任务状态回填到账号，不会上传日志原文。默认只读本赛季
        {wipe?.name ? `（${wipe.name}）` : ""}
        ，避免上个 wipe 的完成记录污染当前进度。
      </p>
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
      {priorWipe ? (
        <p className={styles.warn}>
          自定义范围早于本赛季，会带上旧赛季完成记录。
        </p>
      ) : null}
    </Modal>
  );
}
