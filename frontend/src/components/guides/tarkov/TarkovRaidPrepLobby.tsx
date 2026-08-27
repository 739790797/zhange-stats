import { Alert } from "antd";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTarkovRaidRoom,
  fetchTarkovRaidRooms,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { tarkovRaidRoomHref } from "@/lib/tarkovHomeNav";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import {
  formatRoomRemain,
  remainMs,
  roomDisplayTitle,
} from "@/lib/tarkovRaidRooms";
import { raidPrepMapOptions } from "@/lib/tarkovRaidPrep";
import styles from "./TarkovRaidPrepPanel.module.css";
import taskStyles from "./TarkovTasksPanel.module.css";

export function TarkovRaidPrepLobby({ mapId }: { mapId: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);
  const labelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const option of mapOptions) map.set(option.id, option.label);
    return map;
  }, [mapOptions]);

  const roomsQuery = useQuery({
    queryKey: ["guides-tarkov-raid-rooms", mapId],
    queryFn: () => fetchTarkovRaidRooms(mapId || undefined),
    refetchInterval: 15_000,
    retry: 1,
  });

  const createMut = useMutation({
    mutationFn: () =>
      createTarkovRaidRoom({
        map: mapId,
        title: title.trim() || undefined,
      }),
    onSuccess: (room) => {
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-raid-rooms"] });
      navigate(tarkovRaidRoomHref(room.public_id));
    },
  });

  const items = roomsQuery.data?.items ?? [];

  return (
    <div className={styles.lobby}>
      <div className={styles.lobbyHead}>
        <span className={styles.lobbyTitle}>
          进行中的房间
          {typeof items.length === "number" ? ` · ${items.length}` : ""}
        </span>
        <button
          type="button"
          className={taskStyles.chip}
          onClick={() => setNow(Date.now())}
        >
          刷新
        </button>
      </div>
      {roomsQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="房间列表加载失败"
          description={apiError(roomsQuery.error, "房间列表加载失败")}
        />
      ) : null}
      {items.length ? (
        <div className={styles.lobbyList}>
          {items.map((room) => {
            const mapLabel = labelById.get(room.map_slug) || room.map_slug;
            const thumb = tarkovMapThumbUrl(room.map_slug);
            const remain = formatRoomRemain(remainMs(room.expire_at, now));
            return (
              <Link
                key={room.public_id}
                className={styles.lobbyRow}
                to={tarkovRaidRoomHref(room.public_id)}
              >
                {thumb ? (
                  <img
                    className={styles.chipThumb}
                    src={thumb}
                    alt=""
                    width={36}
                    height={24}
                  />
                ) : null}
                <div className={styles.lobbyMeta}>
                  <div className={styles.lobbyName}>
                    {roomDisplayTitle(room, mapLabel)}
                  </div>
                  <div className={styles.lobbySub}>
                    {mapLabel} · {room.host_display_name} · {room.member_count}/
                    {room.max_members} · {remain}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      ) : (
        <div className={styles.lobbySub}>还没有进行中的房间</div>
      )}
      <div className={styles.lobbyCreate}>
        <input
          className={styles.lobbyInput}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="可选房间名"
          maxLength={40}
          disabled={!mapId || createMut.isPending}
        />
        <button
          type="button"
          className={taskStyles.chip}
          disabled={!mapId || createMut.isPending}
          onClick={() => createMut.mutate()}
        >
          {mapId ? "创建房间" : "先选地图再创建"}
        </button>
      </div>
      {createMut.isError ? (
        <Alert
          type="error"
          showIcon
          message="创建失败"
          description={apiError(createMut.error, "创建失败")}
        />
      ) : null}
    </div>
  );
}
