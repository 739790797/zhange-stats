import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  TARKOV_GAME_MODE_STORAGE_KEY,
  TarkovGameModeContext,
  applyRuntimeMode,
  getTarkovGameMode,
  loadTarkovGameMode,
  persistTarkovGameMode,
  type TarkovGameMode,
} from "@/lib/tarkovGameMode";

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
