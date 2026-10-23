import { useContext } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovGoons } from "@/features/guides/tarkov/api/guidesApi";
import { useTarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import {
  TarkovGoonTrackerLiveContext,
  goonsQueryKey,
} from "@/features/guides/tarkov/providers/tarkovGoonTrackerLiveShared";

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
