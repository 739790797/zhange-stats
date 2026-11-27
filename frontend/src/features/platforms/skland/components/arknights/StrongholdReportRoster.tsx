import {
  AppstoreOutlined,
  LeftOutlined,
  LinkOutlined,
  RightOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from "@ant-design/icons";
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type {
  StrongholdBond,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";
import { professionIconSrc } from "./assets";
import { GAME_RES, PROFESSION_CLASS_FILE } from "./constants";
import { BattleIcon, EffectPopup } from "./StrongholdBattleUI";
import { ReportBondEffect, ReportBondIcon, ReportEffect } from "./StrongholdReportEffects";
import { belongsToBond, bondStatus, reportPortraits } from "./strongholdReportModel";
import styles from "./StrongholdReport.module.css";
import tile from "./StrongholdReportRoster.module.css";

type Roster = StrongholdRecordDetail["roster"];
type Operator = NonNullable<Roster>[number];
type PopupChange = (open: boolean) => void;
const pageSize = 10;
const phaseNames = ["未精英化", "精一", "精二"];
const occupationNames: Readonly<Record<string, string>> = {
  PIONEER: "先锋",
  WARRIOR: "近卫",
  TANK: "重装",
  SNIPER: "狙击",
  CASTER: "术师",
  MEDIC: "医疗",
  SUPPORT: "辅助",
  SPECIAL: "特种",
};
const decals = import.meta.glob<string>("../../assets/stronghold/*.png", {
  eager: true,
  import: "default",
  query: "?url",
});
const decal = (file: string) => decals[`../../assets/stronghold/${file}.png`];

function validPhase(phase?: number | null) {
  return phase === 0 || phase === 1 || phase === 2 ? phase : null;
}

function Insignia({ operator }: { operator: Operator }) {
  const phase = validPhase(operator.phase);
  const tone = operator.is_elite === true ? "gold" : "base";
  const rarityLabel = operator.is_elite === true ? "精锐，" : "";
  const rank = operator.tier == null ? null : decal(`outer_img_chess_level_${operator.tier}`);
  return (
    <div className={tile.insignia}>
      {rank ? <img className={tile.rank} src={rank} alt={`${operator.tier} 阶`} /> : null}
      {phase != null || operator.level != null ? (
        <span
          className={tile.promotion}
          role="img"
          data-tone={phase != null ? tone : undefined}
          aria-label={`${rarityLabel}${phase == null ? "精英化未记录" : phaseNames[phase]}，等级 ${operator.level ?? "未记录"}`}
        >
          {phase != null ? (
            <img className={tile.promotionIcon} src={decal(`char_elite_${tone}_${phase}`)} alt="" />
          ) : null}
          <span className={tile.level}>{operator.level ?? "—"}</span>
        </span>
      ) : null}
    </div>
  );
}

function Portrait({ operator }: { operator: Operator }) {
  const candidates = reportPortraits(operator.char_id, operator.phase);
  const [attempt, setAttempt] = useState(0);
  const src = candidates[attempt];
  return (
    <div className={tile.art} aria-hidden="true">
      {src ? (
        <img
          src={src}
          alt=""
          key={src}
          loading="lazy"
          decoding="async"
          onError={() => setAttempt((current) => Math.max(current, attempt + 1))}
        />
      ) : (
        <UserOutlined />
      )}
    </div>
  );
}

function KitItem({
  kind,
  icon,
  name,
  description,
  caption,
  fallback,
  onOpenChange,
}: {
  kind: "特质" | "技能" | "模组" | "装备";
  icon?: string | null;
  name: string;
  description?: string | null;
  caption?: string;
  fallback: ReactNode;
  onOpenChange: PopupChange;
}) {
  const mark = <BattleIcon className={styles.reportIcon} src={icon} fallback={fallback} />;
  return (
    <EffectPopup
      tone="paper"
      className={tile.kitItem}
      label={`${kind}：${name}`}
      onOpenChange={onOpenChange}
      content={
        <ReportEffect
          icon={mark}
          name={name}
          eyebrow={caption ? `${kind} · ${caption}` : kind}
          description={description || "同版本效果说明未收录"}
        />
      }
    >
      {mark}
      <span className={tile.ellipsis}>{name}</span>
    </EffectPopup>
  );
}

function KitRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={tile.kitRow}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function effectLevel(effect?: Operator["skill"]) {
  if (effect?.reference_level != null) return `Lv.${effect.reference_level} 效果`;
  if (effect?.config_level != null && effect.config_level > 0)
    return `配置 Lv.${effect.config_level}`;
  return undefined;
}

function OperatorKit({
  operator,
  onOpenChange,
}: {
  operator: Operator;
  onOpenChange: PopupChange;
}) {
  const {
    traits,
    skill,
    skill_id: skillId,
    module: mod,
    module_id: moduleId,
    equipment,
  } = operator;
  return (
    <dl className={tile.kit}>
      <KitRow label="特质">
        {traits?.length ? (
          traits.map((trait, i) => (
            <KitItem
              kind="特质"
              key={`${trait.id}-${i}`}
              name={trait.name ?? "特质名称未收录"}
              icon={trait.icon_url}
              description={trait.description}
              fallback={<LinkOutlined />}
              onOpenChange={onOpenChange}
            />
          ))
        ) : (
          <span className={tile.unavailable}>{traits ? "无特质" : "未记录"}</span>
        )}
      </KitRow>
      <KitRow label="技能">
        {skillId ? (
          <KitItem
            kind="技能"
            name={skill?.name ?? "技能名称未收录"}
            icon={
              skill?.icon_url ?? `${GAME_RES}/skill/skill_icon_${encodeURIComponent(skillId)}.png`
            }
            description={skill?.description}
            caption={effectLevel(skill)}
            fallback={<ThunderboltOutlined />}
            onOpenChange={onOpenChange}
          />
        ) : (
          <span className={tile.unavailable}>未记录</span>
        )}
      </KitRow>
      <KitRow label="模组">
        {moduleId ? (
          <KitItem
            kind="模组"
            name={mod?.name ?? "模组名称未收录"}
            icon={mod?.icon_url}
            description={
              mod?.description ?? (mod?.config_level === 0 ? "该棋子未启用模组效果" : null)
            }
            caption={effectLevel(mod)}
            fallback={<AppstoreOutlined />}
            onOpenChange={onOpenChange}
          />
        ) : (
          <span className={tile.unavailable}>未装备</span>
        )}
      </KitRow>
      <KitRow label="装备">
        {equipment?.length ? (
          <div className={tile.equipment}>
            {equipment.map((item, i) => (
              <KitItem
                kind="装备"
                key={`${item.id}-${i}`}
                name={item.name ?? "装备名称未收录"}
                icon={item.icon_url}
                description={item.description}
                caption={item.tier ? `${item.tier} 阶` : undefined}
                fallback={<AppstoreOutlined />}
                onOpenChange={onOpenChange}
              />
            ))}
          </div>
        ) : (
          <span className={tile.unavailable}>{equipment ? "未装备" : "未记录"}</span>
        )}
      </KitRow>
    </dl>
  );
}

function OperatorCard({
  operator,
  bonds,
  roster,
}: {
  operator: Operator;
  bonds: StrongholdBond[];
  roster: Roster;
}) {
  const card = useRef<HTMLElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLDivElement>(null);
  const drawerId = useId();
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [openPopups, setOpenPopups] = useState(0);
  const trackPopup = useCallback(
    (open: boolean) => setOpenPopups((count) => count + (open ? 1 : -1)),
    [],
  );
  const open = !dismissed && (hovered || focused || pinned || openPopups > 0);
  const dismiss = useCallback(() => {
    setPinned(false);
    setDismissed(true);
  }, []);
  useLayoutEffect(() => {
    if (drawer.current) drawer.current.inert = !open;
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (
        pinned &&
        event.target instanceof Element &&
        !card.current?.contains(event.target) &&
        !event.target.closest(`.${styles.paperPopover}`)
      )
        dismiss();
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || openPopups) return;
      if (drawer.current?.contains(document.activeElement))
        trigger.current?.focus({ preventScroll: true });
      dismiss();
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open, openPopups, pinned, dismiss]);

  const name = operator.name ?? "干员名未收录";
  const profession =
    operator.profession &&
    Object.prototype.hasOwnProperty.call(PROFESSION_CLASS_FILE, operator.profession)
      ? professionIconSrc(operator.profession)
      : undefined;
  const occupation = operator.profession ? occupationNames[operator.profession] : undefined;
  const branch =
    operator.branch_id && operator.branch_name ? decal(`branch_${operator.branch_id}`) : undefined;
  const phase = validPhase(operator.phase);
  const operatorBonds = bonds.filter((bond) => belongsToBond(operator, bond));
  return (
    <li>
      <article
        ref={card}
        className={tile.card}
        data-open={open}
        onPointerEnter={(event) => {
          if (event.pointerType !== "mouse" || !event.currentTarget.contains(event.target as Node))
            return;
          setHovered(true);
          setDismissed(false);
        }}
        onPointerLeave={(event) => {
          if (event.pointerType === "mouse") setHovered(false);
        }}
        onFocusCapture={(event) => {
          if (
            event.target.matches(":focus-visible") &&
            event.currentTarget.contains(event.target)
          ) {
            setFocused(true);
            if (!event.currentTarget.contains(event.relatedTarget)) setDismissed(false);
          }
        }}
        onBlurCapture={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false);
        }}
      >
        <Portrait key={`${operator.char_id}-${operator.phase}`} operator={operator} />
        <button
          ref={trigger}
          className={tile.trigger}
          type="button"
          aria-label={`查看${name}的出战详情`}
          aria-expanded={open}
          aria-controls={drawerId}
          onClick={() => {
            if (pinned) dismiss();
            else {
              setDismissed(false);
              setPinned(true);
            }
          }}
        >
          <span className={tile.namePlate}>
            <span className={tile.ellipsis}>{name}</span>
            {profession ? (
              <img src={profession} className={tile.profession} alt={occupation ?? ""} />
            ) : null}
          </span>
        </button>
        <Insignia operator={operator} />
        {operatorBonds.length ? (
          <div className={tile.bonds} aria-label={`${name}的盟约`}>
            {operatorBonds.map((bond) => (
              <EffectPopup
                key={bond.bond_id}
                tone="paper"
                className={tile.bondButton}
                label={`${bond.name ?? bond.bond_id}，${bondStatus(bond.active)}`}
                content={<ReportBondEffect bond={bond} roster={roster} />}
                onOpenChange={trackPopup}
              >
                <ReportBondIcon bond={bond} />
              </EffectPopup>
            ))}
          </div>
        ) : null}
        <div id={drawerId} ref={drawer} className={tile.drawer} aria-hidden={!open}>
          <div className={tile.bio}>
            <strong className={tile.ellipsis}>{name}</strong>
            {branch || profession || operator.branch_name || occupation ? (
              <span className={tile.branch}>
                {branch || profession ? <img src={branch ?? profession} alt="" /> : null}
                {operator.branch_name ?? occupation}
              </span>
            ) : null}
          </div>
          {phase != null || operator.level != null ? (
            <p className={tile.cardLevel}>
              {phase != null ? phaseNames[phase] : null}
              {operator.level != null ? ` Lv.${operator.level}` : null}
            </p>
          ) : null}
          <OperatorKit operator={operator} onOpenChange={trackPopup} />
        </div>
      </article>
    </li>
  );
}

export function ReportRoster({
  id,
  record,
  selection,
}: {
  id: string;
  record: StrongholdRecordDetail;
  selection?: ReactNode;
}) {
  const [page, setPage] = useState(0);
  const roster = record.roster;
  const bonds = [...(record.bonds ?? []), ...(record.available_bonds ?? [])];
  const pages = Math.max(1, Math.ceil((roster?.length ?? 0) / pageSize));
  const current = Math.min(page, pages - 1);
  const operators = roster?.slice(current * pageSize, (current + 1) * pageSize) ?? [];
  return (
    <section id={id} className={tile.section} aria-label="出战干员">
      <header className={`${styles.sectionHeading} ${tile.heading}`}>
        <h4>出战干员 {roster ? <small>{roster.length} 名</small> : null}</h4>
        <div className={tile.tools}>
          {selection}
          {pages > 1 ? (
            <div className={styles.seatPager} aria-label="干员分页">
              <button
                type="button"
                aria-label="上一组干员"
                disabled={current === 0}
                onClick={() => setPage(current - 1)}
              >
                <LeftOutlined />
              </button>
              <span>
                {current + 1} / {pages}
              </span>
              <button
                type="button"
                aria-label="下一组干员"
                disabled={current + 1 === pages}
                onClick={() => setPage(current + 1)}
              >
                <RightOutlined />
              </button>
            </div>
          ) : null}
        </div>
      </header>
      {roster?.length ? (
        <>
          {bonds.length ? (
            <div className={tile.legend} aria-label="干员盟约图例">
              <span data-state="true">本局已点亮</span>
              <span data-state="false">本局未点亮</span>
              {bonds.some(({ active }) => active == null) ? (
                <span data-state="unknown">状态未知</span>
              ) : null}
            </div>
          ) : null}
          <p className={tile.scrollHint}>横滑查看干员</p>
          <div className={tile.scroll}>
            <ul className={tile.grid}>
              {Array.from({ length: pageSize }, (_, i) => {
                const operator = operators[i];
                return operator ? (
                  <OperatorCard
                    key={`${current}-${operator.id}-${i}`}
                    operator={operator}
                    roster={roster}
                    bonds={bonds}
                  />
                ) : (
                  <li key={`empty-${i}`} className={tile.empty}>
                    <span>空位</span>
                  </li>
                );
              })}
            </ul>
          </div>
        </>
      ) : (
        <p className={styles.emptyLine}>{roster ? "该视角没有出战干员" : "阵容数据暂不可用"}</p>
      )}
    </section>
  );
}
