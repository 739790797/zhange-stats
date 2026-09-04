import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovRaidRooms,
  joinTarkovRaidRoom,
  type TarkovRaidRoomLobbyItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { TARKOV_HOME_PATH, tarkovRaidRoomHref } from "@/lib/tarkovHomeNav";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import { colorForUserId, raidPrepMapOptions } from "@/lib/tarkovRaidPrep";
import { raidRoomIsFull } from "@/lib/tarkovRaidRooms";
import { useDocumentHidden, visibleRefetchInterval } from "@/lib/visibleRefetchInterval";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovRaidSeatBoard.module.css";

const THUMB_W = 36;
const THUMB_H = 24;
const PAGE_SIZE = 10;

function SeatThumb({ slug }: { slug: string }) {
  const [broken, setBroken] = useState(false);
  const src = tarkovMapThumbUrl(slug);
  if (!src || broken) {
    return <span className={styles.thumb} aria-hidden />;
  }
  return (
    <img
      className={styles.thumb}
      src={src}
      alt=""
      width={THUMB_W}
      height={THUMB_H}
      onError={() => setBroken(true)}
    />
  );
}

type Props = {
  onEntered?: () => void;
  loginFrom?: string;
};

export function TarkovRaidSeatBoard({
  onEntered,
  loginFrom = TARKOV_HOME_PATH,
}: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const gameMode = useTarkovGameMode();
  const loggedIn = Boolean(useAuthStore((s) => s.token));
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);
  const labelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const option of mapOptions) map.set(option.id, option.label);
    return map;
  }, [mapOptions]);
  const [page, setPage] = useState(1);
  const hidden = useDocumentHidden();

  useEffect(() => {
    setPage(1);
  }, [gameMode]);

  const roomsQuery = useQuery({
    queryKey: ["guides-tarkov-raid-rooms", "lobby", gameMode, page],
    queryFn: async () => {
      const data = await fetchTarkovRaidRooms(gameMode, {
        page,
        pageSize: PAGE_SIZE,
      });
      queryClient.setQueryData(["guides-tarkov-raid-rooms", "mine"], {
        item: data.mine ?? null,
      });
      return data;
    },
    enabled: loggedIn,
    refetchInterval: loggedIn ? visibleRefetchInterval(15_000, hidden) : false,
    retry: 1,
  });

  const joinMut = useMutation({
    mutationFn: (args: { publicId: string }) =>
      joinTarkovRaidRoom(args.publicId, { gameMode }),
    onSuccess: (room) => {
      void queryClient.invalidateQueries({
        queryKey: ["guides-tarkov-raid-rooms"],
      });
      onEntered?.();
      navigate(tarkovRaidRoomHref(room.public_id));
    },
  });

  const items = roomsQuery.data?.items || [];
  const total = roomsQuery.data?.total || 0;
  const pageSize = roomsQuery.data?.page_size || PAGE_SIZE;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const enterRoom = (publicId: string) => {
    onEntered?.();
    navigate(tarkovRaidRoomHref(publicId));
  };

  const requireAuth = () => {
    onEntered?.();
    navigate("/login", {
      state: { from: { pathname: loginFrom } },
    });
  };

  const clickRoom = (room: TarkovRaidRoomLobbyItem) => {
    if (!loggedIn) {
      requireAuth();
      return;
    }
    if (room.is_member) {
      enterRoom(room.public_id);
      return;
    }
    joinMut.mutate({ publicId: room.public_id });
  };

  return (
    <div className={styles.board}>
      {joinMut.isError ? (
        <p className={styles.error}>{apiError(joinMut.error, "加入失败")}</p>
      ) : null}
      {roomsQuery.isError ? (
        <p className={styles.error}>
          {apiError(roomsQuery.error, "房间列表加载失败")}
        </p>
      ) : null}
      {!roomsQuery.isLoading && loggedIn && items.length === 0 ? (
        <p className={styles.empty}>暂无公开房间，用房间码加入或自己创建一个</p>
      ) : null}
      {!loggedIn ? (
        <p className={styles.empty}>登录后可查看公开房间</p>
      ) : null}
      <div className={styles.list}>
        {items.map((room) => {
          const full = raidRoomIsFull(room) && !room.is_member;
          const joining =
            joinMut.isPending && joinMut.variables?.publicId === room.public_id;
          const mapLabel = labelById.get(room.map_slug) || "";
          const mine = Boolean(room.is_member);
          const occupants = room.occupants || [];
          const max = Number(room.max_members) || 8;
          const count = Number(room.member_count) || occupants.length;
          return (
            <button
              key={room.public_id}
              type="button"
              className={`${styles.seat} ${mine ? styles.seatMine : ""}`}
              disabled={full || joinMut.isPending}
              onClick={() => {
                if (full || joinMut.isPending) return;
                clickRoom(room);
              }}
            >
              <SeatThumb slug={room.map_slug} />
              <span className={styles.identity}>
                <span className={styles.name}>
                  {room.title || room.host_display_name || "房间"}
                </span>
                <span className={styles.map}>
                  {mapLabel || "未选地图"}
                  {room.game_mode
                    ? ` · ${String(room.game_mode).toUpperCase()}`
                    : ""}
                  {joining ? " · 加入中…" : full ? " · 已满" : ""}
                </span>
              </span>
              <span className={styles.tags}>
                {occupants.map((row) => (
                  <span key={row.user_id} className={styles.tag}>
                    <span
                      className={styles.tagDot}
                      style={{ background: colorForUserId(row.user_id) }}
                    />
                    {row.display_name}
                  </span>
                ))}
              </span>
              <span className={styles.count}>
                {count}/{max}
              </span>
            </button>
          );
        })}
      </div>
      {loggedIn && total > pageSize ? (
        <div className={styles.pager}>
          <button
            type="button"
            className={styles.pagerBtn}
            disabled={page <= 1 || joinMut.isPending}
            onClick={() => setPage((n) => Math.max(1, n - 1))}
          >
            上一页
          </button>
          <span className={styles.pagerMeta}>
            {page}/{pageCount}
          </span>
          <button
            type="button"
            className={styles.pagerBtn}
            disabled={page >= pageCount || joinMut.isPending}
            onClick={() => setPage((n) => n + 1)}
          >
            下一页
          </button>
        </div>
      ) : null}
    </div>
  );
}
