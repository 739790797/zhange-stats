import { Input, Modal } from "antd";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovRaidRooms,
  joinTarkovRaidRoom,
  type TarkovRaidRoomLobbyItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_HOME_PATH,
  tarkovRaidRoomHref,
} from "@/lib/tarkovHomeNav";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import { colorForUserId, raidPrepMapOptions } from "@/lib/tarkovRaidPrep";
import {
  mergeRaidLobbySeats,
  raidRoomSlotIdsForMode,
  raidRoomIsFull,
} from "@/lib/tarkovRaidRooms";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovRaidSeatBoard.module.css";

const THUMB_W = 36;
const THUMB_H = 24;

function emptySeats(gameMode: string): TarkovRaidRoomLobbyItem[] {
  const mode = gameMode === "pve" ? "pve" : "pvp";
  return raidRoomSlotIdsForMode(mode).map((id, index) => ({
    public_id: id,
    title: `${index + 1}号房`,
    map_slug: "",
    game_mode: mode,
    listed: true,
    has_password: false,
    host_user_id: null,
    host_display_name: "",
    member_count: 0,
    max_members: 8,
    is_member: false,
    occupants: [],
  }));
}

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
  const [lockTarget, setLockTarget] = useState<TarkovRaidRoomLobbyItem | null>(
    null,
  );
  const [lockPassword, setLockPassword] = useState("");

  const roomsQuery = useQuery({
    queryKey: ["guides-tarkov-raid-rooms", "seats", gameMode],
    queryFn: () => fetchTarkovRaidRooms(gameMode),
    enabled: loggedIn,
    refetchInterval: loggedIn ? 15_000 : false,
    retry: 1,
  });

  const joinMut = useMutation({
    mutationFn: (args: { publicId: string; password?: string }) =>
      joinTarkovRaidRoom(args.publicId, {
        gameMode,
        password: args.password,
      }),
    onSuccess: (room) => {
      setLockTarget(null);
      setLockPassword("");
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-raid-rooms"] });
      onEntered?.();
      navigate(tarkovRaidRoomHref(room.public_id));
    },
  });

  const items = useMemo(
    () => mergeRaidLobbySeats(roomsQuery.data?.items, emptySeats(gameMode)),
    [gameMode, roomsQuery.data?.items],
  );

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

  const closeLock = () => {
    setLockTarget(null);
    setLockPassword("");
  };

  const submitLock = () => {
    if (!lockTarget || !lockPassword.trim()) return;
    return joinMut.mutateAsync({
      publicId: lockTarget.public_id,
      password: lockPassword.trim(),
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
            joinMut.isPending && joinMut.variables?.publicId === room.public_id;
          const mapLabel = labelById.get(room.map_slug) || "";
          const mine = Boolean(room.is_member);
          const occupants = room.occupants || [];
          const max = Number(room.max_members) || 8;
          const count = Number(room.member_count) || occupants.length;
          const locked = Boolean(room.has_password) && !mine;
          return (
            <button
              key={room.public_id}
              type="button"
              className={`${styles.seat} ${mine ? styles.seatMine : ""} ${
                room.has_password ? styles.seatLocked : ""
              }`}
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
                if (room.has_password) {
                  setLockTarget(room);
                  setLockPassword("");
                  return;
                }
                joinMut.mutate({ publicId: room.public_id });
              }}
            >
              <SeatThumb slug={room.map_slug} />
              <span className={styles.identity}>
                <span className={styles.name}>
                  {room.title || `${room.public_id}号房`}
                  {room.has_password ? (
                    <span className={styles.lockMark}>锁</span>
                  ) : null}
                </span>
                <span className={styles.map}>
                  {mapLabel || "未选地图"}
                  {room.game_mode
                    ? ` · ${String(room.game_mode).toUpperCase()}`
                    : ""}
                  {joining ? " · 加入中…" : full ? " · 已满" : ""}
                  {locked && !joining && !full ? " · 需密码" : ""}
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
      <Modal
        title={lockTarget ? `加入 ${lockTarget.title || "房间"}` : "输入房间密码"}
        open={Boolean(lockTarget)}
        onCancel={closeLock}
        onOk={submitLock}
        okText="加入"
        cancelText="取消"
        confirmLoading={joinMut.isPending}
        okButtonProps={{ disabled: !lockPassword.trim() }}
        destroyOnClose
      >
        <Input.Password
          value={lockPassword}
          onChange={(event) => setLockPassword(event.target.value)}
          placeholder="房间密码"
          maxLength={32}
          autoFocus
          onPressEnter={submitLock}
        />
      </Modal>
    </div>
  );
}
