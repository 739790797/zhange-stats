import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { minecraftConsoleWsUrl } from "@/api/minecraftApi";
import { useAuthStore } from "@/stores/authStore";

const MAX_CHARS = 400_000;
const MAX_POINTS = 90;
const ESC = String.fromCharCode(27);
const BEL = String.fromCharCode(7);
const ANSI_RE = new RegExp(`${ESC}\\[[0-9;?]*[A-Za-z]`, "g");
const OSC_RE = new RegExp(`${ESC}\\][^${BEL}]*${BEL}`, "g");

export type ConsoleStats = {
  cpu: number;
  memory_bytes: number;
  memory_limit_bytes: number;
  disk_bytes: number;
  disk_limit_bytes: number;
  network_rx_bytes: number;
  network_tx_bytes: number;
  uptime_ms: number;
  state: string;
};

export type ConsoleMeta = {
  name: string;
  address: string;
  memory_limit_mb: number;
  cpu_limit: number;
  disk_limit_mb: number;
};

export type ConsoleHistoryPoint = {
  t: number;
  cpu: number;
  memory: number;
  rx: number;
  tx: number;
};

function stripAnsi(text: string) {
  let out = text.replace(ANSI_RE, "").replace(OSC_RE, "");
  if (out.includes("\r")) {
    out = out.replace(/\r\n/g, "\n");
    const parts = out.split("\r");
    out = parts[parts.length - 1] || "";
  }
  return out.replace(/\n+$/, "");
}

function closeReason(code: number) {
  switch (code) {
    case 4401:
      return "未登录或令牌无效";
    case 4403:
      return "需要管理员权限";
    case 4000:
      return "未配置 Pelican";
    default:
      return "控制台已断开";
  }
}

export function useMinecraftConsole(enabled: boolean) {
  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.token);
  const preRef = useRef<HTMLPreElement>(null);
  const textRef = useRef("");
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number | null>(null);
  const prevNet = useRef<{ rx: number; tx: number; t: number } | null>(null);
  const [command, setCommand] = useState("");
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [stats, setStats] = useState<ConsoleStats | null>(null);
  const [meta, setMeta] = useState<ConsoleMeta | null>(null);
  const [history, setHistory] = useState<ConsoleHistoryPoint[]>([]);
  const [error, setError] = useState("");
  const [hasOutput, setHasOutput] = useState(false);

  const append = useCallback((line: string) => {
    const cleaned = stripAnsi(line);
    if (!cleaned) return;
    let next = textRef.current ? `${textRef.current}\n${cleaned}` : cleaned;
    if (next.length > MAX_CHARS) next = next.slice(-Math.floor(MAX_CHARS * 0.8));
    textRef.current = next;
    setHasOutput(true);
    const el = preRef.current;
    if (!el) return;
    const stick = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    el.textContent = next;
    if (stick) el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    if (!enabled || !token) {
      setReady(false);
      setError(enabled ? "未登录" : "");
      return;
    }

    let stopped = false;
    let attempt = 0;

    const connect = () => {
      if (stopped) return;
      setError("");
      setReady(false);
      const ws = new WebSocket(minecraftConsoleWsUrl());
      wsRef.current = ws;
      ws.onopen = () => {
        attempt = 0;
        prevNet.current = null;
        setHistory([]);
        ws.send(JSON.stringify({ event: "auth", token }));
      };
      ws.onmessage = (ev) => {
        let data: Record<string, unknown>;
        try {
          data = JSON.parse(String(ev.data || ""));
        } catch {
          return;
        }
        const event = String(data.event || "");
        if (event === "ready") {
          setReady(true);
          setMeta({
            name: String(data.name || ""),
            address: String(data.address || ""),
            memory_limit_mb: Number(data.memory_limit_mb || 0),
            cpu_limit: Number(data.cpu_limit || 0),
            disk_limit_mb: Number(data.disk_limit_mb || 0),
          });
          return;
        }
        if (event === "error") {
          setError(String(data.message || "控制台出错"));
          return;
        }
        if (event === "status") {
          setStatus(String(data.state || "") || null);
          queryClient.invalidateQueries({ queryKey: ["minecraft-status"] });
          return;
        }
        if (event === "stats") {
          const next: ConsoleStats = {
            cpu: Number(data.cpu || 0),
            memory_bytes: Number(data.memory_bytes || 0),
            memory_limit_bytes: Number(data.memory_limit_bytes || 0),
            disk_bytes: Number(data.disk_bytes || 0),
            disk_limit_bytes: Number(data.disk_limit_bytes || 0),
            network_rx_bytes: Number(data.network_rx_bytes || 0),
            network_tx_bytes: Number(data.network_tx_bytes || 0),
            uptime_ms: Number(data.uptime_ms || 0),
            state: String(data.state || ""),
          };
          setStats(next);
          if (next.state) setStatus(next.state);
          const now = Date.now();
          const prev = prevNet.current;
          const dt = prev ? Math.max((now - prev.t) / 1000, 0.2) : 0;
          const rxRate =
            prev && dt && next.network_rx_bytes >= prev.rx
              ? (next.network_rx_bytes - prev.rx) / dt
              : 0;
          const txRate =
            prev && dt && next.network_tx_bytes >= prev.tx
              ? (next.network_tx_bytes - prev.tx) / dt
              : 0;
          prevNet.current = {
            rx: next.network_rx_bytes,
            tx: next.network_tx_bytes,
            t: now,
          };
          setHistory((rows) => {
            const point: ConsoleHistoryPoint = {
              t: now,
              cpu: next.cpu,
              memory: next.memory_bytes,
              rx: rxRate,
              tx: txRate,
            };
            const out = [...rows, point];
            return out.length > MAX_POINTS ? out.slice(-MAX_POINTS) : out;
          });
          return;
        }
        if (typeof data.line === "string") append(data.line);
      };
      ws.onclose = (ev) => {
        setReady(false);
        if (stopped) return;
        if (ev.code === 4401 || ev.code === 4403 || ev.code === 4000) {
          setError(closeReason(ev.code));
          return;
        }
        attempt += 1;
        if (attempt > 8) {
          setError(closeReason(ev.code));
          return;
        }
        const delay = Math.min(1000 * 2 ** (attempt - 1), 8000);
        setError(`控制台断开，${Math.round(delay / 1000)} 秒后重连`);
        retryRef.current = window.setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      stopped = true;
      if (retryRef.current != null) window.clearTimeout(retryRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [enabled, token, queryClient, append]);

  const sendCommand = () => {
    const line = command.trim();
    if (!line || !ready || wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ event: "command", command: line }));
    setCommand("");
  };

  return {
    preRef,
    ready,
    error,
    hasOutput,
    command,
    setCommand,
    sendCommand,
    status,
    stats,
    meta,
    history,
  };
}
