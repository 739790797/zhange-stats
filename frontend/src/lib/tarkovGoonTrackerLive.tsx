import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovGoons,
  tarkovGoonsWsUrl,
  type TarkovGoonTracker,
} from "@/api/guidesApi";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useAuthStore } from "@/stores/authStore";

type WsBundle = {
  event?: string;
  pvp?: TarkovGoonTracker;
  pve?: TarkovGoonTracker;
};

type LiveValue = {
  live: boolean;
};

const TarkovGoonTrackerLiveContext = createContext<LiveValue>({ live: false });

function goonsQueryKey(mode: string) {
  return ["guides-tarkov-goons", mode] as const;
}

function applyBundle(
  queryClient: ReturnType<typeof useQueryClient>,
  payload: WsBundle,
) {
  if (payload.pvp) {
    queryClient.setQueryData(goonsQueryKey("pvp"), payload.pvp);
  }
  if (payload.pve) {
    queryClient.setQueryData(goonsQueryKey("pve"), payload.pve);
  }
}

export function TarkovGoonTrackerProvider({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();
  const [live, setLive] = useState(false);

  useEffect(() => {
    if (!token) {
      setLive(false);
      return undefined;
    }
    let stopped = false;
    let retry = 0;
    let ws: WebSocket | null = null;
    let ping = 0;
    let retryTimer = 0;

    const connect = () => {
      if (stopped) return;
      ws = new WebSocket(tarkovGoonsWsUrl());
      ws.onopen = () => {
        retry = 0;
        ws?.send(JSON.stringify({ event: "auth", token }));
      };
      ws.onmessage = (event) => {
        let payload: WsBundle;
        try {
          payload = JSON.parse(String(event.data || ""));
        } catch {
          return;
        }
        if (payload.event === "pong") return;
        if (payload.event === "goons" || payload.pvp || payload.pve) {
          setLive(true);
          applyBundle(queryClient, payload);
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ event: "ping" }));
          }
        }
      };
      ws.onclose = () => {
        setLive(false);
        if (stopped) return;
        retry += 1;
        const wait = Math.min(12_000, 800 * 2 ** Math.min(retry, 4));
        retryTimer = window.setTimeout(connect, wait);
      };
      ws.onerror = () => {
        ws?.close();
      };
    };

    connect();
    ping = window.setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ event: "ping" }));
      }
    }, 20_000);

    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      window.clearInterval(ping);
      ws?.close();
    };
  }, [queryClient, token]);

  const value = useMemo(() => ({ live }), [live]);
  return (
    <TarkovGoonTrackerLiveContext.Provider value={value}>
      {children}
    </TarkovGoonTrackerLiveContext.Provider>
  );
}

export function useTarkovGoonTracker() {
  const gameMode = useTarkovGameMode();
  const { live } = useContext(TarkovGoonTrackerLiveContext);
  const query = useQuery({
    queryKey: goonsQueryKey(gameMode),
    queryFn: fetchTarkovGoons,
    staleTime: live ? Infinity : 8_000,
    refetchInterval: live ? false : 8_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
  return {
    status: query.data,
    live,
    isLoading: query.isLoading && !query.data,
    isError: query.isError,
  };
}
