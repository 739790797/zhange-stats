import { Link, useLocation } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { fetchTarkovRaidRooms } from "@/api/guidesApi";
import { TARKOV_GAME_MODES } from "@/lib/tarkovGameMode";
import { raidRoomReturnHref } from "@/lib/tarkovRaidRooms";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovRaidRoomHeaderLink.module.css";

export function TarkovRaidRoomHeaderLink() {
  const { pathname } = useLocation();
  const loggedIn = Boolean(useAuthStore((s) => s.token));
  const rooms = useQueries({
    queries: TARKOV_GAME_MODES.map((mode) => ({
      queryKey: ["guides-tarkov-raid-rooms", "seats", mode],
      queryFn: () => fetchTarkovRaidRooms(mode),
      enabled: loggedIn,
      staleTime: 15_000,
      refetchInterval: loggedIn ? 15_000 : false,
      retry: 1,
    })),
  });
  const href = raidRoomReturnHref(
    rooms.flatMap((row) => row.data?.items || []),
    pathname,
  );
  if (!href) return null;

  return (
    <Link to={href} className={styles.link}>
      回到房间
    </Link>
  );
}
