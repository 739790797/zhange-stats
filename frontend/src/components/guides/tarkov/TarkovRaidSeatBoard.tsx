import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovRaidRooms,
  joinTarkovRaidRoom,
  type TarkovRaidRoomLobbyItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { tarkovRaidRoomHref } from "@/lib/tarkovHomeNav";
import { logMapLabel } from "@/lib/tarkovGameLogs";
import { raidRoomIsFull } from "@/lib/tarkovRaidRooms";
import { useDocumentHidden, visibleRefetchInterval } from "@/lib/visibleRefetchInterval";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovRaidSeatBoard.module.css";

const PAGE_SIZE = 10;
const RAID_PHASE = new Set(["match_found", "raid_starting", "raid_started"]);
const MATCH_PHASE = new Set(["map_loading", "matching"]);

type Seat = {
  userId: number;
  name: string;
  host: boolean;
  mapLabel: string;
  status: string;
};

type Props = {
  onEntered?: () => void;
};

function memberStatus(kind: string, mapSlug: string) {
  if (RAID_PHASE.has(kind)) return "战局中";
  if (MATCH_PHASE.has(kind)) return "匹配中";
  if (mapSlug) return "观战中";
  return "大厅中";
}

function memberMapLabel(slug: string) {
  const id = slug.trim();
  if (!id) return "未选地图";
  const label = logMapLabel(id);
  return label === "未知地图" ? "未选地图" : label;
}

function seatsOf(room: TarkovRaidRoomLobbyItem): Seat[] {
  const people = room.occupants || [];
  if (!people.length) {
    return [{ userId: 0, name: "—", host: false, mapLabel: "未选地图", status: "大厅中" }];
  }
  return people.map((row) => {
    const mapSlug = (row.map_slug || "").trim();
    const kind = (row.phase_kind || "").trim();
    return {
      userId: row.user_id,
      name: (row.display_name || "").trim() || `用户${row.user_id}`,
      host: Boolean(row.is_host),
      mapLabel: memberMapLabel(mapSlug),
      status: memberStatus(kind, mapSlug),
    };
  });
}

function statusClass(status: string) {
  if (status === "战局中") return styles.statusRaid;
  if (status === "观战中") return styles.statusWatch;
  if (status === "匹配中") return styles.statusMatch;
  return styles.statusLobby;
}

export function TarkovRaidSeatBoard({
  onEntered,
}: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const gameMode = useTarkovGameMode();
  const loggedIn = Boolean(useAuthStore((s) => s.user));
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
    refetchInterval: visibleRefetchInterval(15_000, hidden),
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

  const clickRoom = (room: TarkovRaidRoomLobbyItem) => {
    if (!loggedIn || room.is_member) {
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
      {!roomsQuery.isLoading && items.length === 0 ? (
        <p className={styles.empty}>暂无公开房间，用房间码加入或自己创建一个</p>
      ) : null}
      {items.length ? (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>房间标题</th>
              <th>地图名称</th>
              <th>成员</th>
              <th>状态</th>
              <th className={styles.num}>人数</th>
              <th className={styles.act}>加入</th>
            </tr>
          </thead>
          {items.map((room) => {
            const full = raidRoomIsFull(room) && !room.is_member;
            const joining =
              joinMut.isPending && joinMut.variables?.publicId === room.public_id;
            const mine = Boolean(room.is_member);
            const seats = seatsOf(room);
            const span = seats.length;
            const max = Number(room.max_members) || 8;
            const count = Number(room.member_count) || (room.occupants || []).length;
            const title = room.title || room.host_display_name || "房间";
            const open = () => {
              if (full || joinMut.isPending) return;
              clickRoom(room);
            };
            return (
              // oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions -- 整组行只是扩大鼠标点击区，键盘走「加入」按钮
              <tbody
                key={room.public_id}
                className={`${styles.room}${mine ? ` ${styles.roomMine}` : ""}`}
                onClick={open}
              >
                {seats.map((seat, index) => (
                  <tr key={seat.userId || `empty-${index}`}>
                    {index === 0 ? (
                      <td className={styles.merge} rowSpan={span}>
                        {title}
                      </td>
                    ) : null}
                    <td>{seat.mapLabel}</td>
                    <td>
                      {seat.host ? <span className={styles.host} aria-hidden>⭐</span> : null}
                      {seat.name}
                    </td>
                    <td className={statusClass(seat.status)}>{seat.status}</td>
                    {index === 0 ? (
                      <>
                        <td className={`${styles.num} ${styles.merge}`} rowSpan={span}>
                          {count}/{max}
                        </td>
                        <td className={`${styles.act} ${styles.merge}`} rowSpan={span}>
                          <button
                            type="button"
                            className={styles.join}
                            disabled={full || joinMut.isPending}
                            onClick={(event) => {
                              event.stopPropagation();
                              open();
                            }}
                          >
                            {joining ? "加入中…" : mine ? "进入" : "加入"}
                          </button>
                        </td>
                      </>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            );
          })}
        </table>
      ) : null}
      {total > pageSize ? (
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
