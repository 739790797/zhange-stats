import { Alert, Modal, Spin } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTarkovRaidRoom,
  fetchTarkovRaidRooms,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  TARKOV_HOME_PATH,
  TARKOV_RAID_PREP_PATH,
  tarkovRaidRoomHref,
} from "@/lib/tarkovHomeNav";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import {
  formatRoomRemain,
  remainMs,
  roomDisplayTitle,
} from "@/lib/tarkovRaidRooms";
import {
  raidPrepMapOptions,
  type RaidPrepMapOption,
} from "@/lib/tarkovRaidPrep";
import { parseRaidRoomPublicId } from "@/lib/tarkovRaidRooms";
import { useAuthStore } from "@/stores/authStore";
import mapStyles from "./TarkovMapsPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

export type RaidPrepEntryStep = "mode" | "solo" | "create" | "join";

type Props = {
  open: boolean;
  /** 打开时的起始步骤；更换地图时用 solo */
  step?: RaidPrepEntryStep;
  /** 更换地图时预选当前图 */
  currentMapId?: string;
  onClose: () => void;
  /** 单人选图后回调；不传则默认跳转 `/raid-prep?map=` */
  onSoloMap?: (mapId: string) => void;
};

function MapThumb({
  slug,
  icon,
}: {
  slug: string;
  icon: string;
}) {
  const [broken, setBroken] = useState(false);
  const src = tarkovMapThumbUrl(slug);
  if (!src || broken) {
    return (
      <svg className={mapStyles.thumbFallback} viewBox="0 0 24 24" aria-hidden>
        <path fill="currentColor" d={icon} />
      </svg>
    );
  }
  return (
    <img
      className={mapStyles.thumb}
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setBroken(true)}
    />
  );
}

function MapPickGrid({
  options,
  selectedId,
  onPick,
}: {
  options: RaidPrepMapOption[];
  selectedId?: string;
  onPick: (id: string) => void;
}) {
  return (
    <div className={`${mapStyles.grid} ${styles.entryMapGrid}`}>
      {options.map((option) => {
        const on = option.id === selectedId;
        return (
          <button
            key={option.id}
            type="button"
            className={`${mapStyles.card} ${styles.pickCard} ${
              on ? styles.entryMapOn : ""
            }`}
            onClick={() => onPick(option.id)}
          >
            <div className={mapStyles.thumbWrap}>
              <MapThumb slug={option.id} icon={option.icon} />
            </div>
            <div className={mapStyles.body}>
              <div className={mapStyles.name}>{option.label}</div>
              <div className={mapStyles.english}>{option.english}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function modalTitle(step: RaidPrepEntryStep): string {
  if (step === "solo") return "选择地图";
  if (step === "create") return "创建房间";
  if (step === "join") return "加入房间";
  return "战局准备";
}

export function TarkovRaidPrepEntryModal({
  open,
  step: stepProp = "mode",
  currentMapId = "",
  onClose,
  onSoloMap,
}: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const loggedIn = Boolean(useAuthStore((s) => s.token));
  const me = useAuthStore((s) => s.user);
  const [step, setStep] = useState<RaidPrepEntryStep>(stepProp);
  const [now, setNow] = useState(() => Date.now());
  const [joinText, setJoinText] = useState("");
  const [joinError, setJoinError] = useState("");
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);
  const defaultRoomTitle = useMemo(() => {
    const name = (me?.display_name || me?.username || "").trim() || "玩家";
    return `${name}的房间`;
  }, [me?.display_name, me?.username]);

  useEffect(() => {
    if (!open) return;
    setStep(stepProp);
    setJoinText("");
    setJoinError("");
  }, [open, stepProp]);
  const labelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const option of mapOptions) map.set(option.id, option.label);
    return map;
  }, [mapOptions]);

  const roomsQuery = useQuery({
    queryKey: ["guides-tarkov-raid-rooms", "mine"],
    queryFn: () => fetchTarkovRaidRooms(undefined, true),
    enabled: open && loggedIn,
    refetchInterval:
      open && (step === "join" || step === "mode") ? 15_000 : false,
    retry: 1,
  });

  const createMut = useMutation({
    mutationFn: (mapId: string) =>
      createTarkovRaidRoom({
        map: mapId,
        title: defaultRoomTitle,
      }),
    onSuccess: (room) => {
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-raid-rooms"] });
      onClose();
      navigate(tarkovRaidRoomHref(room.public_id));
    },
  });

  const pickCreate = (mapId: string) => {
    if (createMut.isPending) return;
    createMut.mutate(mapId);
  };

  const requireAuth = () => {
    onClose();
    navigate("/login", {
      state: { from: { pathname: TARKOV_RAID_PREP_PATH } },
    });
  };

  const pickSolo = (mapId: string) => {
    if (onSoloMap) {
      onSoloMap(mapId);
      onClose();
      return;
    }
    onClose();
    navigate(`${TARKOV_RAID_PREP_PATH}?map=${encodeURIComponent(mapId)}`);
  };

  const enterRoom = (publicId: string) => {
    onClose();
    navigate(tarkovRaidRoomHref(publicId));
  };

  const items = roomsQuery.data?.items ?? [];
  const myRooms = useMemo(
    () => items.filter((room) => room.is_member),
    [items],
  );
  const hostedRooms = useMemo(
    () => items.filter((room) => room.host_user_id === me?.id),
    [items, me?.id],
  );

  const handleCancel = () => {
    if (step !== "mode" && stepProp === "mode") {
      setStep("mode");
      return;
    }
    onClose();
  };

  return (
    <Modal
      title={modalTitle(step)}
      open={open}
      onCancel={handleCancel}
      footer={null}
      width={step === "mode" ? 440 : 960}
      destroyOnClose
      classNames={{ body: styles.entryModalBody }}
    >
      {step === "mode" ? (
        <div className={styles.entryModeList}>
          <button
            type="button"
            className={styles.entryModeBtn}
            onClick={() => {
              if (!loggedIn) {
                requireAuth();
                return;
              }
              setStep("solo");
            }}
          >
            <span className={styles.entryModeTitle}>单人准备</span>
            <span className={styles.entryModeHint}>选图后勾选任务，叠点位到地图</span>
          </button>
          <button
            type="button"
            className={styles.entryModeBtn}
            onClick={() => {
              if (!loggedIn) {
                requireAuth();
                return;
              }
              setStep("create");
            }}
          >
            <span className={styles.entryModeTitle}>创建房间</span>
            <span className={styles.entryModeHint}>点选地图创建房间，邀请队友一起准备</span>
          </button>
          <button
            type="button"
            className={styles.entryModeBtn}
            onClick={() => {
              if (!loggedIn) {
                requireAuth();
                return;
              }
              setStep("join");
            }}
          >
            <span className={styles.entryModeTitle}>加入房间</span>
            <span className={styles.entryModeHint}>粘贴链接，或进入自己的房间</span>
          </button>
          {loggedIn && myRooms.length ? (
            <div className={styles.entryMyRooms}>
              <span className={styles.entryMyRoomsLabel}>我的进行中房间</span>
              {myRooms.map((room) => {
                const mapLabel = labelById.get(room.map_slug) || room.map_slug;
                const thumb = tarkovMapThumbUrl(room.map_slug);
                const remain = formatRoomRemain(remainMs(room.expire_at, now));
                return (
                  <button
                    key={room.public_id}
                    type="button"
                    className={styles.lobbyRow}
                    onClick={() => enterRoom(room.public_id)}
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
                        {room.max_members}
                      </div>
                      <div className={styles.lobbySub}>{remain}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}

      {step === "solo" ? (
        <MapPickGrid
          options={mapOptions}
          selectedId={currentMapId || undefined}
          onPick={pickSolo}
        />
      ) : null}

      {step === "create" ? (
        <div className={styles.entryCreate}>
          {roomsQuery.isLoading && !roomsQuery.data ? (
            <div className={styles.empty}>
              <Spin />
            </div>
          ) : hostedRooms.length ? (
            <>
              <p className={styles.hint}>
                同时只能主持一个进行中的房间，先进入已有房间。关闭后再创建新的。
              </p>
              <div className={styles.lobbyList}>
                {hostedRooms.map((room) => {
                  const mapLabel = labelById.get(room.map_slug) || room.map_slug;
                  const thumb = tarkovMapThumbUrl(room.map_slug);
                  const remain = formatRoomRemain(remainMs(room.expire_at, now));
                  return (
                    <button
                      key={room.public_id}
                      type="button"
                      className={styles.lobbyRow}
                      onClick={() => enterRoom(room.public_id)}
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
                          {mapLabel} · {room.member_count}/{room.max_members}
                        </div>
                        <div className={styles.lobbySub}>{remain}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </>
          ) : (
            <>
              <p className={styles.hint}>
                将创建为「{defaultRoomTitle}」，点选地图即可进入
                {createMut.isPending ? "（创建中…）" : ""}
              </p>
              {createMut.isError ? (
                <Alert
                  type="error"
                  showIcon
                  message="创建失败"
                  description={apiError(createMut.error, "创建失败")}
                />
              ) : null}
              <MapPickGrid
                options={mapOptions}
                selectedId={createMut.isPending ? createMut.variables : undefined}
                onPick={pickCreate}
              />
            </>
          )}
        </div>
      ) : null}

      {step === "join" ? (
        <div className={styles.lobby}>
          <form
            className={styles.joinForm}
            onSubmit={(event) => {
              event.preventDefault();
              const parsed = parseRaidRoomPublicId(joinText);
              if (!parsed) {
                setJoinError("粘贴房间链接或 12 位房间号");
                return;
              }
              setJoinError("");
              enterRoom(parsed);
            }}
          >
            <input
              className={styles.dockSearch}
              value={joinText}
              onChange={(event) => {
                setJoinText(event.target.value);
                if (joinError) setJoinError("");
              }}
              placeholder="粘贴房间链接或房间号"
              aria-label="房间链接或房间号"
            />
            <button type="submit" className={styles.dockChip}>
              加入
            </button>
          </form>
          {joinError ? (
            <Alert type="error" showIcon message={joinError} />
          ) : null}
          <div className={styles.lobbyHead}>
            <span className={styles.lobbyTitle}>
              我的房间
              {myRooms.length ? ` · ${myRooms.length}` : ""}
            </span>
            <button
              type="button"
              className={styles.dockChip}
              onClick={() => {
                setNow(Date.now());
                void roomsQuery.refetch();
              }}
            >
              刷新
            </button>
          </div>
          {roomsQuery.isLoading && !roomsQuery.data ? (
            <div className={styles.empty}>
              <Spin />
            </div>
          ) : null}
          {roomsQuery.isError ? (
            <Alert
              type="error"
              showIcon
              message="房间列表加载失败"
              description={apiError(roomsQuery.error, "房间列表加载失败")}
            />
          ) : null}
          {myRooms.length ? (
            <div className={styles.lobbyList}>
              {myRooms.map((room) => {
                const mapLabel = labelById.get(room.map_slug) || room.map_slug;
                const thumb = tarkovMapThumbUrl(room.map_slug);
                const remain = formatRoomRemain(remainMs(room.expire_at, now));
                return (
                  <button
                    key={room.public_id}
                    type="button"
                    className={styles.lobbyRow}
                    onClick={() => enterRoom(room.public_id)}
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
                        {room.max_members}
                      </div>
                      <div className={styles.lobbySub}>{remain}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : roomsQuery.isSuccess ? (
            <div className={styles.lobbySub}>
              还没有自己的房间，让队友分享链接即可加入
            </div>
          ) : null}
        </div>
      ) : null}
    </Modal>
  );
}

/** 关闭入口弹窗时回到塔科夫首页。 */
export function raidPrepEntryFallbackPath(): string {
  return TARKOV_HOME_PATH;
}
