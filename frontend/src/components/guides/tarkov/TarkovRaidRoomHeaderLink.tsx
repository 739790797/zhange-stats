import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovRaidRoomMine } from "@/api/guidesApi";
import { isTarkovHomePath } from "@/lib/tarkovHomeNav";
import { raidRoomReturnHref } from "@/lib/tarkovRaidRooms";
import { useDocumentHidden, visibleRefetchInterval } from "@/lib/visibleRefetchInterval";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovRaidRoomHeaderLink.module.css";

export function TarkovRaidRoomHeaderLink() {
  const { pathname } = useLocation();
  const loggedIn = Boolean(useAuthStore((s) => s.token));
  const onHome = isTarkovHomePath(pathname);
  const hidden = useDocumentHidden();
  const pollMine = loggedIn && !onHome;
  const mineQuery = useQuery({
    queryKey: ["guides-tarkov-raid-rooms", "mine"],
    queryFn: fetchTarkovRaidRoomMine,
    enabled: loggedIn,
    staleTime: 15_000,
    refetchInterval: pollMine ? visibleRefetchInterval(15_000, hidden) : false,
    refetchOnWindowFocus: pollMine,
    retry: 1,
  });
  const href = raidRoomReturnHref(
    mineQuery.data?.item ? [mineQuery.data.item] : [],
    pathname,
  );
  if (!href) return null;

  return (
    <Link to={href} className={styles.link}>
      回到房间
    </Link>
  );
}
