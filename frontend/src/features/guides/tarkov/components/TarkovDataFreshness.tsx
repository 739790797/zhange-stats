type Props = {
  source?: string | null;
  syncedAt?: string | null;
  note?: string | null;
};

export function TarkovDataFreshness({ source, syncedAt, note }: Props) {
  const sourceLabel = (source || "").trim();
  const timestamp = (syncedAt || "").trim();
  const noteText = (note || "").trim();
  if (!sourceLabel && !timestamp && !noteText) return null;

  return (
    <div
      aria-label="数据来源与同步信息"
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "4px 12px",
        color: "var(--hb-muted, #b0ae9a)",
        fontSize: 12,
        lineHeight: 1.5,
      }}
    >
      {sourceLabel ? <span>数据来源：{sourceLabel}</span> : null}
      {timestamp ? (
        <span>同步时间：{timestamp.replace("T", " ")}</span>
      ) : null}
      {noteText ? <span title={noteText}>数据说明：{noteText}</span> : null}
    </div>
  );
}
