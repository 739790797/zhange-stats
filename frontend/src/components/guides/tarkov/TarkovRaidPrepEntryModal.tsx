import { Alert, Input, Modal } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createTarkovRaidRoom, joinTarkovRaidRoom } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  TARKOV_HOME_PATH,
  TARKOV_RAID_PREP_PATH,
  tarkovRaidRoomHref,
} from "@/lib/tarkovHomeNav";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import {
  defaultRaidRoomTitle,
  parseRaidRoomPublicId,
  RAID_ROOM_TITLE_MAX,
  raidRoomJoinNeedsPassword,
} from "@/lib/tarkovRaidRooms";
import { RAID_ROOM_TITLE_POLICY } from "@/lib/legalDocs";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  raidPrepMapOptions,
  type RaidPrepMapOption,
} from "@/lib/tarkovRaidPrep";
import { useAuthStore } from "@/stores/authStore";
import { TarkovRaidSeatBoard } from "@/components/guides/tarkov/TarkovRaidSeatBoard";
import { TarkovGoonSightingHint } from "@/components/guides/tarkov/TarkovGoonTrackerBanner";
import { useTarkovGoonTracker } from "@/lib/useTarkovGoonTracker";
import mapStyles from "./TarkovMapsPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

export type RaidPrepEntryStep = "create" | "join" | "solo";

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

export function MapPickGrid({
  options,
  selectedId,
  goonMapSlug,
  onPick,
}: {
  options: RaidPrepMapOption[];
  selectedId?: string;
  goonMapSlug?: string;
  onPick: (id: string) => void;
}) {
  return (
    <div className={`${mapStyles.grid} ${styles.entryMapGrid}`}>
      {options.map((option) => {
        const on = option.id === selectedId;
        const goon = Boolean(goonMapSlug && option.id === goonMapSlug);
        return (
          <button
            key={option.id}
            type="button"
            className={`${mapStyles.card} ${styles.pickCard} ${
              on ? styles.entryMapOn : ""
            } ${goon ? styles.entryMapGoon : ""}`}
            onClick={() => onPick(option.id)}
          >
            <div className={mapStyles.thumbWrap}>
              <MapThumb slug={option.id} icon={option.icon} />
            </div>
            <div className={mapStyles.body}>
              <div className={`${mapStyles.name} ${styles.pickName}`}>
                {option.label}
              </div>
              <div className={mapStyles.english}>{option.english}</div>
              {goon ? <TarkovGoonSightingHint mapId={option.id} /> : null}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function modalTitle(step: RaidPrepEntryStep): string {
  if (step === "solo") return "选择地图";
  if (step === "join") return "加入房间";
  return "创建房间";
}

export function TarkovRaidPrepEntryModal({
  open,
  step: stepProp = "create",
  currentMapId = "",
  onClose,
  onSoloMap,
}: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const gameMode = useTarkovGameMode();
  const loggedIn = Boolean(useAuthStore((s) => s.token));
  const displayName = useAuthStore((s) => s.user?.display_name);
  const [step, setStep] = useState<RaidPrepEntryStep>(stepProp);
  const [joinText, setJoinText] = useState("");
  const [joinError, setJoinError] = useState("");
  const [listed, setListed] = useState(true);
  const [title, setTitle] = useState("");
  const [password, setPassword] = useState("");
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);
  const { status: goonStatus } = useTarkovGoonTracker();

  useEffect(() => {
    if (!open) return;
    setStep(stepProp);
    setJoinText("");
    setJoinError("");
    setListed(true);
    setTitle(defaultRaidRoomTitle(displayName));
    setPassword("");
  }, [open, stepProp, displayName]);

  const requireAuth = () => {
    onClose();
    navigate("/login", {
      state: { from: { pathname: TARKOV_HOME_PATH } },
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

  const createMut = useMutation({
    mutationFn: () =>
      createTarkovRaidRoom({
        gameMode,
        title: title.trim() || undefined,
        listed,
        password: listed ? undefined : password.trim(),
      }),
    onSuccess: (room) => {
      void queryClient.invalidateQueries({
        queryKey: ["guides-tarkov-raid-rooms"],
      });
      enterRoom(room.public_id);
    },
  });

  const joinByCodeMut = useMutation({
    mutationFn: (publicId: string) =>
      joinTarkovRaidRoom(publicId, { gameMode }),
    onSuccess: (room) => {
      void queryClient.invalidateQueries({
        queryKey: ["guides-tarkov-raid-rooms"],
      });
      enterRoom(room.public_id);
    },
    onError: (error, publicId) => {
      if (raidRoomJoinNeedsPassword(error)) {
        enterRoom(publicId);
        return;
      }
      setJoinError(apiError(error, "加入失败"));
    },
  });

  const createBlocked =
    createMut.isPending || (!listed && !password.trim());

  return (
    <Modal
      title={modalTitle(step)}
      open={open}
      onCancel={onClose}
      footer={null}
      width={step === "create" ? 440 : 960}
      destroyOnClose
      classNames={{ body: styles.entryModalBody }}
    >
      {step === "create" ? (
        <form
          className={styles.entryCreate}
          onSubmit={(event) => {
            event.preventDefault();
            if (!loggedIn) {
              requireAuth();
              return;
            }
            if (createBlocked) return;
            createMut.mutate();
          }}
        >
          <div>
            <div className={styles.entryFieldLabel}>房间性质</div>
            <div className={styles.entryKind}>
              <label className={styles.entryKindLabel}>
                <input
                  type="radio"
                  name="raid-room-listed"
                  checked={listed}
                  onChange={() => {
                    setListed(true);
                    setPassword("");
                  }}
                />
                公开
              </label>
              <label className={styles.entryKindLabel}>
                <input
                  type="radio"
                  name="raid-room-listed"
                  checked={!listed}
                  onChange={() => setListed(false)}
                />
                私密
              </label>
            </div>
          </div>
          <label>
            <div className={styles.entryFieldLabel}>房间名称</div>
            <input
              className={styles.dockSearch}
              value={title}
              maxLength={RAID_ROOM_TITLE_MAX}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={defaultRaidRoomTitle(displayName)}
              aria-label="房间名称"
            />
          </label>
          {listed ? null : (
            <label>
              <div className={styles.entryFieldLabel}>房间密码</div>
              <Input.Password
                value={password}
                maxLength={32}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="加入时需要"
                autoComplete="new-password"
              />
            </label>
          )}
          <p className={styles.entryHint}>
            {RAID_ROOM_TITLE_POLICY}{" "}
            若你已在其他房间，创建后会自动离开。地图进房后再选。
          </p>
          {createMut.isError ? (
            <Alert
              type="error"
              showIcon
              message={apiError(createMut.error, "创建房间失败")}
            />
          ) : null}
          <button
            type="submit"
            className={styles.dockChip}
            disabled={createBlocked}
          >
            {createMut.isPending ? "创建中…" : "创建房间"}
          </button>
        </form>
      ) : null}

      {step === "solo" ? (
        <MapPickGrid
          options={mapOptions}
          selectedId={currentMapId || undefined}
          goonMapSlug={goonStatus?.map_slug || undefined}
          onPick={pickSolo}
        />
      ) : null}

      {step === "join" ? (
        <div className={styles.lobby}>
          <form
            className={styles.joinForm}
            onSubmit={(event) => {
              event.preventDefault();
              if (!loggedIn) {
                requireAuth();
                return;
              }
              const parsed = parseRaidRoomPublicId(joinText, gameMode);
              if (!parsed) {
                setJoinError("填写房间码或粘贴房间链接");
                return;
              }
              setJoinError("");
              joinByCodeMut.mutate(parsed);
            }}
          >
            <input
              className={styles.dockSearch}
              value={joinText}
              onChange={(event) => {
                setJoinText(event.target.value);
                if (joinError) setJoinError("");
              }}
              placeholder="填写房间码"
              aria-label="房间码"
            />
            <button
              type="submit"
              className={styles.dockChip}
              disabled={joinByCodeMut.isPending}
            >
              {joinByCodeMut.isPending ? "加入中…" : "加入"}
            </button>
          </form>
          {joinError ? (
            <Alert type="error" showIcon message={joinError} />
          ) : null}
          <TarkovRaidSeatBoard
            onEntered={onClose}
            loginFrom={TARKOV_HOME_PATH}
          />
        </div>
      ) : null}
    </Modal>
  );
}
