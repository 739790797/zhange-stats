import type { RefObject } from "react";

type Props = {
  preRef: RefObject<HTMLPreElement>;
  command: string;
  onCommandChange: (value: string) => void;
  onSend: () => void;
  ready: boolean;
  error: string;
  empty?: boolean;
};

export function MinecraftConsoleView({
  preRef,
  command,
  onCommandChange,
  onSend,
  ready,
  error,
  empty = false,
}: Props) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ position: "relative" }}>
        <pre
          ref={preRef}
          style={{
            margin: 0,
            height: 380,
            overflow: "auto",
            padding: "12px 14px 8px",
            background: "#0b1220",
            color: "#b6e36a",
            fontFamily:
              "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
            fontSize: 12.5,
            lineHeight: 1.5,
            borderRadius: "8px 8px 0 0",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        />
        {empty && !error ? (
          <div
            style={{
              position: "absolute",
              inset: 0,
              padding: "12px 14px",
              color: "#4b5563",
              fontFamily:
                "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
              fontSize: 12.5,
              pointerEvents: "none",
            }}
          >
            {ready ? "等待日志…" : "正在连接控制台…"}
          </div>
        ) : null}
      </div>
      {error ? (
        <div
          style={{
            padding: "6px 12px",
            background: "#0b1220",
            color: "#f87171",
            fontSize: 12,
          }}
        >
          {error}
        </div>
      ) : null}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          background: "#111827",
          borderRadius: "0 0 8px 8px",
        }}
      >
        <span
          style={{
            color: "#6b7280",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
            flexShrink: 0,
            whiteSpace: "nowrap",
            lineHeight: 1,
          }}
        >
          &gt;
        </span>
        <input
          value={command}
          disabled={!ready}
          placeholder={ready ? "输入指令…" : "控制台未就绪"}
          onChange={(e) => onCommandChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onSend();
            }
          }}
          style={{
            flex: 1,
            minWidth: 0,
            width: "auto",
            border: "none",
            outline: "none",
            background: "transparent",
            color: "#e5e7eb",
            fontFamily:
              "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
            fontSize: 13,
            padding: 0,
            lineHeight: 1.4,
          }}
        />
      </div>
    </div>
  );
}
