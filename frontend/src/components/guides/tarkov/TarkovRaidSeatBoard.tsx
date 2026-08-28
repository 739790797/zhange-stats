import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovRaidRooms,
  joinTarkovRaidRoom,
  type TarkovRaidRoomLobbyItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  TARKOV_HOME_PATH,
  tarkovRaidRoomHref,
} from "@/lib/tarkovHomeNav";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import { colorForUserId, raidPrepMapOptions } from "@/lib/tarkovRaidPrep";
import {
  RAID_ROOM_SLOT_IDS,
  raidRoomIsFull,
} from "@/lib/tarkovRaidRooms";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovRaidSeatBoard.module.css";

const THUMB_W = 36;
const THUMB_H = 24;

const EMPTY_SEATS: TarkovRaidRoomLobbyItem[] = RAID_ROOM_SLOT_IDS.map((id) => ({
  public_id: id,
  title: `${id}号房`,
  map_slug: "",
  host_user_id: null,
  host_display_name: "",
  member_count: 0,
  max_members: 5,
  is_member: false,
  occupants: [],
}));

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
  const loggedIn = Boolean(useAuthStore((s) => s.token));
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);
  const labelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const option of mapOptions) map.set(option.id, option.label);
    return map;
  }, [mapOptions]);

  const roomsQuery = useQuery({
    queryKey: ["guides-tarkov-raid-rooms", "seats"],
    queryFn: () => fetchTarkovRaidRooms(),
    enabled: loggedIn,
    refetchInterval: loggedIn ? 15_000 : false,
    retry: 1,
  });

  const joinMut = useMutation({
    mutationFn: (publicId: string) => joinTarkovRaidRoom(publicId),
    onSuccess: (room) => {
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-raid-rooms"] });
      onEntered?.();
      navigate(tarkovRaidRoomHref(room.public_id));
    },
  });

  const items = roomsQuery.data?.items?.length
    ? roomsQuery.data.items
    : EMPTY_SEATS;

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
      <div className={styles.list}>
        {items.map((room) => {
          const full = raidRoomIsFull(room) && !room.is_member;
          const joining =
            joinMut.isPending && joinMut.variables === room.public_id;
          const mapLabel = labelById.get(room.map_slug) || "";
          const mine = Boolean(room.is_member);
          const occupants = room.occupants || [];
          const max = Number(room.max_members) || 5;
          const count = Number(room.member_count) || occupants.length;
          return (
            <button
              key={room.public_id}
              type="button"
              className={`${styles.seat} ${mine ? styles.seatMine : ""}`}
              disabled={full || joinMut.isPending}
              onClick={() => {
                if (full || joinMut.isPending) return;
                if (!loggedIn) {
                  requireAuth();
                  return;
                }
                if (room.is_member) {
                  enterRoom(room.public_id);
                  return;
                }
                joinMut.mutate(room.public_id);
              }}
            >
              <SeatThumb slug={room.map_slug} />
              <span className={styles.identity}>
                <span className={styles.name}>
                  {room.title || `${room.public_id}号房`}
                </span>
                <span className={styles.map}>
                  {mapLabel || "未选地图"}
                  {joining ? " · 加入中…" : full ? " · 已满" : ""}
                </span>
              </span>
              <span className={styles.tags}>
                {occupants.map((row) => (
                  <span
                    key={row.user_id}
                    className={styles.tag}
                    data-host={row.is_host ? "true" : "false"}
                  >
                    <span
                      className={styles.tagDot}
                      style={{ background: colorForUserId(row.user_id) }}
                    />
                    {row.display_name}
                    {row.is_host ? " · 房主" : ""}
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
    </div>
  );
}
