export function StarRow({
  rarity,
  light = true,
}: {
  rarity: number;
  light?: boolean;
}) {
  const n = Math.max(0, Math.min(6, rarity));
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        gap: 1,
        height: 11,
      }}
    >
      {Array.from({ length: n }, (_, i) => (
        <span
          key={i}
          style={{
            color: light ? "#ffe9a8" : "#d4b84a",
            fontSize: 10,
            lineHeight: 1,
            textShadow: light
              ? "0 0 3px rgba(0,0,0,0.9)"
              : "0 0 1px rgba(0,0,0,0.35)",
            fontWeight: 700,
          }}
        >
          ★
        </span>
      ))}
    </div>
  );
}
