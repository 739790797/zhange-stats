import { Alert, Modal } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  TARKOV_HOME_PATH,
  TARKOV_RAID_PREP_PATH,
  tarkovRaidRoomHref,
} from "@/lib/tarkovHomeNav";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import { parseRaidRoomPublicId } from "@/lib/tarkovRaidRooms";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  raidPrepMapOptions,
  type RaidPrepMapOption,
} from "@/lib/tarkovRaidPrep";
import { useAuthStore } from "@/stores/authStore";
import { TarkovRaidSeatBoard } from "@/components/guides/tarkov/TarkovRaidSeatBoard";
import mapStyles from "./TarkovMapsPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

export type RaidPrepEntryStep = "mode" | "solo" | "join";

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
  if (step === "join") return "选择房间";
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
  const gameMode = useTarkovGameMode();
  const loggedIn = Boolean(useAuthStore((s) => s.token));
  const [step, setStep] = useState<RaidPrepEntryStep>(stepProp);
  const [joinText, setJoinText] = useState("");
  const [joinError, setJoinError] = useState("");
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);

  useEffect(() => {
    if (!open) return;
    setStep(stepProp);
    setJoinText("");
    setJoinError("");
  }, [open, stepProp]);

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
              setStep("join");
            }}
          >
            <span className={styles.entryModeTitle}>加入房间</span>
            <span className={styles.entryModeHint}>
              当前模式五张公开桌（PVP / PVE 各一套）；房主可设密码，空桌第一人当房主
            </span>
          </button>
        </div>
      ) : null}

      {step === "solo" ? (
        <MapPickGrid
          options={mapOptions}
          selectedId={currentMapId || undefined}
          onPick={pickSolo}
        />
      ) : null}

      {step === "join" ? (
        <div className={styles.lobby}>
          <form
            className={styles.joinForm}
            onSubmit={(event) => {
              event.preventDefault();
              const parsed = parseRaidRoomPublicId(joinText, gameMode);
              if (!parsed) {
                setJoinError("粘贴房间链接或当前模式 1～5 号");
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
              placeholder="粘贴房间链接或当前模式 1～5 号"
              aria-label="房间链接或房间号"
            />
            <button type="submit" className={styles.dockChip}>
              打开
            </button>
          </form>
          {joinError ? (
            <Alert type="error" showIcon message={joinError} />
          ) : null}
          <TarkovRaidSeatBoard
            onEntered={onClose}
            loginFrom={TARKOV_RAID_PREP_PATH}
          />
        </div>
      ) : null}
    </Modal>
  );
}

/** 关闭入口弹窗时回到塔科夫首页。 */
export function raidPrepEntryFallbackPath(): string {
  return TARKOV_HOME_PATH;
}
