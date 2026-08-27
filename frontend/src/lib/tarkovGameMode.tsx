import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type TarkovGameMode = "pvp" | "pve";

export const TARKOV_GAME_MODE_STORAGE_KEY = "zhange.guides.tarkov.gameMode";

const MODES: TarkovGameMode[] = ["pvp", "pve"];

let runtimeMode: TarkovGameMode = "pvp";
let hydrated = false;

export function parseTarkovGameMode(raw: unknown): TarkovGameMode {
  const text = String(raw || "")
    .trim()
    .toLowerCase();
  if (text === "pve") return "pve";
  return "pvp";
}

export function loadTarkovGameMode(): TarkovGameMode {
  if (typeof window === "undefined") return "pvp";
  try {
    return parseTarkovGameMode(
      window.localStorage.getItem(TARKOV_GAME_MODE_STORAGE_KEY),
    );
  } catch {
    return "pvp";
  }
}

export function saveTarkovGameMode(mode: TarkovGameMode) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TARKOV_GAME_MODE_STORAGE_KEY, mode);
  } catch {
    /* ignore quota / private mode */
  }
}

function applyRuntimeMode(mode: TarkovGameMode): TarkovGameMode {
  runtimeMode = parseTarkovGameMode(mode);
  hydrated = true;
  return runtimeMode;
}

export function getTarkovGameMode(): TarkovGameMode {
  if (!hydrated) applyRuntimeMode(loadTarkovGameMode());
  return runtimeMode;
}

export function setTarkovGameModeRuntime(mode: TarkovGameMode) {
  applyRuntimeMode(mode);
}

/** 写入 localStorage，请求拦截器与顶栏共用这一份。 */
export function persistTarkovGameMode(mode: TarkovGameMode): TarkovGameMode {
  const parsed = applyRuntimeMode(mode);
  saveTarkovGameMode(parsed);
  return parsed;
}

/** 单测重置进程内缓存，下一次 get 会再读 storage。 */
export function resetTarkovGameModeRuntime() {
  runtimeMode = "pvp";
  hydrated = false;
}

if (typeof window !== "undefined") {
  getTarkovGameMode();
}

type TarkovGameModeContextValue = {
  mode: TarkovGameMode;
  setMode: (mode: TarkovGameMode) => void;
};

const TarkovGameModeContext = createContext<TarkovGameModeContextValue>({
  mode: "pvp",
  setMode: () => undefined,
});

export function TarkovGameModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<TarkovGameMode>(() =>
    getTarkovGameMode(),
  );
  const setMode = useCallback((next: TarkovGameMode) => {
    setModeState(persistTarkovGameMode(next));
  }, []);

  useEffect(() => {
    const syncFromStorage = () => {
      const loaded = loadTarkovGameMode();
      applyRuntimeMode(loaded);
      setModeState(loaded);
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key && event.key !== TARKOV_GAME_MODE_STORAGE_KEY) return;
      syncFromStorage();
    };
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) syncFromStorage();
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("pageshow", onPageShow);
    };
  }, []);

  const value = useMemo(() => ({ mode, setMode }), [mode, setMode]);
  return (
    <TarkovGameModeContext.Provider value={value}>
      {children}
    </TarkovGameModeContext.Provider>
  );
}

export function useTarkovGameMode(): TarkovGameMode {
  return useContext(TarkovGameModeContext).mode;
}

export function useTarkovGameModeControls(): TarkovGameModeContextValue {
  return useContext(TarkovGameModeContext);
}

export const TARKOV_GAME_MODES = MODES;
