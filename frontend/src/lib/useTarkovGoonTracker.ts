import { useContext } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovGoons } from "@/api/guidesApi";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TarkovGoonTrackerLiveContext,
  goonsQueryKey,
} from "@/lib/tarkovGoonTrackerLiveShared";

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
