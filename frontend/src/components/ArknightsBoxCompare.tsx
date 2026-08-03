import { useEffect, useMemo, useState, Fragment } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Empty,
  Input,
  Modal,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { CloseOutlined, PlusOutlined } from "@ant-design/icons";
import {
  fetchArknightsBoxCompare,
  fetchArknightsCompareCandidates,
} from "@/api/client";
import type {
  ArknightsOperator,
  ArknightsOwnedChar,
  ArknightsCompareCandidate,
  ArknightsCompareRow,
} from "@/api/types";

/** 稀有度底栏 / 描边色（贴近游戏卡面） */
const RARITY_ACCENT: Record<number, string> = {
  6: "#f5a623",
  5: "#9b59d0",
  4: "#49b3e6",
  3: "#7dce82",
  2: "#9aa0a6",
  1: "#9aa0a6",
};

const GAME_RES =
  "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main";

const PROFESSION_CLASS_FILE: Record<string, string> = {
  PIONEER: "class_vanguard.png",
  WARRIOR: "class_guard.png",
  TANK: "class_defender.png",
  SNIPER: "class_sniper.png",
  CASTER: "class_caster.png",
  MEDIC: "class_medic.png",
  SUPPORT: "class_supporter.png",
  SPECIAL: "class_specialist.png",
};

const COMPARE_MAX = 5;
/** 更接近游戏编队卡比例 */
const CARD_W = 120;
const CARD_H = 156;
const CARD_GAP = 6;
const LABEL_W = 176;
const ROLE_UID_STORAGE_KEY = "zhange.arknights.roleUidByMember";

function loadRoleUidByMember(): Record<number, string> {
  try {
    const raw = localStorage.getItem(ROLE_UID_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const out: Record<number, string> = {};
    for (const [key, value] of Object.entries(parsed)) {
      const id = Number(key);
      if (!Number.isFinite(id) || typeof value !== "string" || !value.trim()) {
        continue;
      }
      out[id] = value.trim();
    }
    return out;
  } catch {
    return {};
  }
}

function saveRoleUidByMember(map: Record<number, string>) {
  try {
    localStorage.setItem(ROLE_UID_STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore quota / private mode */
  }
}

type SortMode = "catalog" | "level";

type RarityProgress = {
  rarity: number;
  owned: number;
  total: number;
};

const RARITY_CN: Record<number, string> = {
  6: "六星",
  5: "五星",
  4: "四星",
  3: "三星",
  2: "二星",
  1: "一星",
};

function apiError(e: unknown, fallback: string) {
  const detail =
    e &&
    typeof e === "object" &&
    "response" in e &&
    (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return String(detail || (e as Error)?.message || fallback);
}

function computeRarityProgress(
  row: ArknightsCompareRow,
  catalog: ArknightsOperator[],
): RarityProgress[] {
  const totalBy: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0 };
  const ownedBy: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0 };
  for (const op of catalog) {
    const r = op.rarity;
    if (r < 1 || r > 6) continue;
    totalBy[r] += 1;
    if (row.owned[op.char_id]) ownedBy[r] += 1;
  }
  return [6, 5, 4, 3, 2, 1].map((rarity) => ({
    rarity,
    owned: ownedBy[rarity],
    total: totalBy[rarity],
  }));
}

function formatProgressPct(owned: number, total: number) {
  if (total <= 0) return "0.0%";
  return `${((owned / total) * 100).toFixed(1)}%`;
}

function eliteIconSrc(phase: number) {
  const p = Math.max(0, Math.min(2, phase | 0));
  return `/arknights/elite_${p}.png`;
}

function professionIconSrc(profession: string) {
  const file = PROFESSION_CLASS_FILE[profession] || "class_caster.png";
  return `/arknights/${file}`;
}

function portraitSrc(charId: string, evolvePhase: number) {
  const stage = evolvePhase >= 2 ? 2 : 1;
  return `${GAME_RES}/portrait/${charId}_${stage}.png`;
}

const POTENTIAL_ROMAN = ["", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"];

function evolveLabel(phase: number) {
  if (phase >= 2) return "精二";
  if (phase >= 1) return "精一";
  return "精零";
}

function moduleEquips(owned: ArknightsOwnedChar) {
  return (owned.equips || []).filter(
    (e) => !e.locked && e.type_icon && e.type_icon !== "original",
  );
}

function OwnedDetailTooltip({
  ownerName,
  channelName,
  roleName,
  op,
  owned,
}: {
  ownerName: string;
  channelName?: string | null;
  roleName?: string | null;
  op: ArknightsOperator;
  owned: ArknightsOwnedChar;
}) {
  const potential = Math.max(0, Math.min(5, owned.potential_rank | 0));
  const mods = moduleEquips(owned);
  const skills = owned.skills || [];
  return (
    <div style={{ maxWidth: 260, lineHeight: 1.55 }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>
        {ownerName}
        {channelName ? (
          <span style={{ fontWeight: 400, opacity: 0.85 }}> · {channelName}</span>
        ) : null}
      </div>
      {roleName ? (
        <div style={{ opacity: 0.85, marginBottom: 6 }}>{roleName}</div>
      ) : null}
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{op.name}</div>
      <div>
        {evolveLabel(owned.evolve_phase)} Lv.{owned.level}
        {potential > 0 ? ` · 潜能${POTENTIAL_ROMAN[potential]}` : ""}
        {owned.favor_percent != null ? ` · 信赖 ${owned.favor_percent}%` : ""}
      </div>
      {skills.length > 0 ? (
        <div style={{ marginTop: 6 }}>
          <div style={{ opacity: 0.75, fontSize: 12 }}>技能</div>
          {skills.map((s) => (
            <div key={s.skill_id}>{s.label}</div>
          ))}
        </div>
      ) : null}
      {mods.length > 0 ? (
        <div style={{ marginTop: 6 }}>
          <div style={{ opacity: 0.75, fontSize: 12 }}>模组</div>
          {mods.map((e) => (
            <div key={e.equip_id}>
              {e.name}
              {e.type_icon ? `（${e.type_icon.split("-").pop()?.toUpperCase() || e.type_icon}）` : ""}
              {` Lv.${e.level}`}
            </div>
          ))}
        </div>
      ) : (
        <div style={{ marginTop: 6, opacity: 0.7 }}>暂无已解锁模组</div>
      )}
    </div>
  );
}

function StarRow({
  rarity,
  light = true,
}: {
  rarity: number;
  light?: boolean;
}) {
  const n = Math.max(0, Math.min(6, rarity));
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        gap: 1,
        height: 11,
      }}
    >
      {Array.from({ length: n }, (_, i) => (
        <span
          key={i}
          style={{
            color: light ? "#ffe9a8" : "#d4b84a",
            fontSize: 10,
            lineHeight: 1,
            textShadow: light
              ? "0 0 3px rgba(0,0,0,0.9)"
              : "0 0 1px rgba(0,0,0,0.35)",
            fontWeight: 700,
          }}
        >
          ★
        </span>
      ))}
    </div>
  );
}

function OwnedCard({
  op,
  owned,
  ownerName,
  channelName,
  roleName,
}: {
  op: ArknightsOperator;
  owned: ArknightsOwnedChar;
  ownerName: string;
  channelName?: string | null;
  roleName?: string | null;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const [useAvatar, setUseAvatar] = useState(false);
  const accent = RARITY_ACCENT[op.rarity] || "#888";
  const phase = owned.evolve_phase ?? 0;
  const potential = Math.max(0, Math.min(5, owned.potential_rank | 0));
  const avatar = owned.avatar_url || op.avatar_url;
  const src = useAvatar
    ? avatar || undefined
    : portraitSrc(op.char_id, phase);
  const eliteLabel = evolveLabel(phase);

  const card = (
    <div
      style={{
        width: CARD_W,
        height: CARD_H,
        flex: "0 0 auto",
        position: "relative",
        overflow: "hidden",
        background: "#1c1c1c",
        boxShadow: `inset 0 0 0 1.5px ${accent}`,
        cursor: "default",
      }}
    >
      <div style={{ position: "absolute", inset: 0 }}>
        {!imgFailed && src ? (
          <img
            src={src}
            alt={op.name}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center top",
            }}
            onError={() => {
              if (!useAvatar && avatar) {
                setUseAvatar(true);
                return;
              }
              setImgFailed(true);
            }}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#666",
              background: `linear-gradient(180deg, ${accent}44, #222)`,
            }}
          >
            {op.rarity}★
          </div>
        )}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 0,
            height: 64,
            background:
              "linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.55) 35%, rgba(0,0,0,0.88) 100%)",
            pointerEvents: "none",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 0,
            height: 36,
            background:
              "linear-gradient(180deg, rgba(0,0,0,0.45) 0%, transparent 100%)",
            pointerEvents: "none",
          }}
        />
      </div>

      <div
        style={{
          position: "absolute",
          top: 5,
          left: 0,
          right: 0,
          zIndex: 2,
          padding: "0 6px",
        }}
      >
        <StarRow rarity={op.rarity} />
      </div>
      <img
        src={professionIconSrc(op.profession)}
        alt={op.profession_label}
        width={22}
        height={22}
        style={{
          position: "absolute",
          top: 4,
          left: 4,
          zIndex: 3,
          objectFit: "contain",
          filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.85))",
        }}
        loading="lazy"
      />

      <div
        style={{
          position: "absolute",
          left: 4,
          bottom: 4,
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 0,
        }}
      >
        <img
          src={eliteIconSrc(phase)}
          alt={eliteLabel}
          width={22}
          height={22}
          style={{
            objectFit: "contain",
            filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.8))",
            marginBottom: -2,
          }}
          loading="lazy"
        />
        <div
          style={{
            minWidth: 28,
            height: 28,
            borderRadius: "50%",
            background: "rgba(0,0,0,0.72)",
            border: "1px solid rgba(255,255,255,0.18)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontSize: owned.level >= 100 ? 12 : 14,
            fontWeight: 800,
            lineHeight: 1,
            fontVariantNumeric: "tabular-nums",
            textShadow: "0 1px 2px rgba(0,0,0,0.6)",
          }}
        >
          {owned.level}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          right: 5,
          bottom: 5,
          left: 40,
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          gap: 2,
          minWidth: 0,
        }}
      >
        {potential > 0 ? (
          <span
            style={{
              color: "#f3e2b0",
              fontSize: 12,
              fontWeight: 700,
              lineHeight: 1,
              letterSpacing: 0.5,
              textShadow: "0 1px 2px rgba(0,0,0,0.95)",
            }}
          >
            {POTENTIAL_ROMAN[potential]}
          </span>
        ) : (
          <span style={{ height: 12 }} />
        )}
        <div
          style={{
            color: "#fff",
            fontSize: 12,
            fontWeight: 700,
            lineHeight: 1.15,
            maxWidth: "100%",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            textAlign: "right",
            textShadow: "0 1px 2px rgba(0,0,0,0.95)",
          }}
        >
          {op.name}
        </div>
      </div>
    </div>
  );

  return (
    <Tooltip
      mouseEnterDelay={0.25}
      placement="top"
      title={
        <OwnedDetailTooltip
          ownerName={ownerName}
          channelName={channelName}
          roleName={roleName}
          op={op}
          owned={owned}
        />
      }
    >
      {card}
    </Tooltip>
  );
}

function MissingCard({ op }: { op: ArknightsOperator }) {
  const accent = RARITY_ACCENT[op.rarity] || "#888";
  return (
    <div
      title={`${op.name}（未拥有）`}
      style={{
        width: CARD_W,
        height: CARD_H,
        flex: "0 0 auto",
        position: "relative",
        overflow: "hidden",
        background: "#e8e8e8",
        boxShadow: `inset 0 0 0 1.5px ${accent}66`,
        opacity: 0.8,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 5,
          left: 0,
          right: 0,
          padding: "0 6px",
        }}
      >
        <StarRow rarity={op.rarity} light={false} />
      </div>
      <img
        src={professionIconSrc(op.profession)}
        alt=""
        width={22}
        height={22}
        style={{
          position: "absolute",
          top: 4,
          left: 4,
          objectFit: "contain",
          opacity: 0.4,
        }}
        loading="lazy"
      />
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ fontSize: 40, fontWeight: 700, color: "#c4c4c4" }}>?</span>
      </div>
      <div
        style={{
          position: "absolute",
          right: 5,
          bottom: 6,
          left: 8,
          color: "#888",
          fontSize: 12,
          fontWeight: 600,
          textAlign: "right",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {op.name}
      </div>
    </div>
  );
}

function RowLabel({
  row,
  progress,
  selectedUid,
  canRemove,
  onUidChange,
  onRemove,
}: {
  row: ArknightsCompareRow;
  progress: RarityProgress[] | null;
  selectedUid?: string;
  canRemove?: boolean;
  onUidChange?: (uid: string) => void;
  onRemove?: () => void;
}) {
  const roles = row.roles || [];
  const currentUid = selectedUid || row.uid || undefined;
  const selectedRole = roles.find((r) => r.uid === currentUid);
  const gameId = selectedRole?.role_name || row.role_name || null;
  return (
    <div
      style={{
        width: LABEL_W,
        flex: "0 0 auto",
        padding: "10px 10px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 8,
        borderRight: "1px solid rgba(0,0,0,0.06)",
        background: "#fff",
        position: "sticky",
        left: 0,
        zIndex: 8,
        isolation: "isolate",
        boxShadow: "4px 0 10px rgba(0,0,0,0.04)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          minWidth: 0,
        }}
      >
        <Avatar src={row.avatar_url || undefined} size="small">
          {(row.nickname || "?").slice(0, 1)}
        </Avatar>
        <Typography.Text strong ellipsis style={{ flex: 1, minWidth: 0 }}>
          {row.nickname}
        </Typography.Text>
        {canRemove ? (
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={onRemove}
            style={{ color: "#999", flex: "0 0 auto" }}
            aria-label="移除对比"
          />
        ) : null}
      </div>

      {roles.length > 0 ? (
        <Select
          size="small"
          style={{ width: "100%" }}
          value={currentUid}
          placeholder="渠道服"
          options={roles.map((r) => ({
            value: r.uid,
            label: r.channel_name || r.role_name,
            title: `${r.role_name} · ${r.channel_name}`,
          }))}
          onChange={(uid: string) => onUidChange?.(uid)}
          popupMatchSelectWidth={false}
        />
      ) : null}

      {row.status === "ok" ? (
        <>
          <Typography.Text
            type="secondary"
            style={{ fontSize: 12 }}
            ellipsis
            title={
              gameId && row.player_level != null
                ? `${gameId} Lv.${row.player_level}`
                : gameId || undefined
            }
          >
            {gameId
              ? row.player_level != null
                ? `${gameId} Lv.${row.player_level}`
                : gameId
              : row.player_level != null
                ? `Lv.${row.player_level}`
                : "已绑定"}
          </Typography.Text>
          {progress ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "32px minmax(0, 1fr) 52px",
                columnGap: 4,
                rowGap: 3,
                fontSize: 12,
                lineHeight: 1.35,
                color: "#444",
                alignItems: "baseline",
              }}
            >
              {progress.map((p) => (
                <Fragment key={p.rarity}>
                  <span
                    style={{
                      color: RARITY_ACCENT[p.rarity] || "#888",
                      fontWeight: 700,
                    }}
                  >
                    {RARITY_CN[p.rarity]}
                  </span>
                  <span
                    style={{
                      fontVariantNumeric: "tabular-nums",
                      textAlign: "right",
                    }}
                  >
                    {p.owned}/{p.total}
                  </span>
                  <span
                    style={{
                      color: "#999",
                      fontSize: 11,
                      fontVariantNumeric: "tabular-nums",
                      textAlign: "right",
                    }}
                  >
                    {formatProgressPct(p.owned, p.total)}
                  </span>
                </Fragment>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <Tag
          color={row.status === "unbound" ? "default" : "warning"}
          style={{ margin: 0, width: "fit-content" }}
        >
          {row.message || row.status}
        </Tag>
      )}
    </div>
  );
}

function SyncCompareBoard({
  rows,
  orderedOps,
  catalog,
  selfId,
  roleUidByMember,
  onRoleUidChange,
  onRemoveMember,
}: {
  rows: ArknightsCompareRow[];
  orderedOps: ArknightsOperator[];
  catalog: ArknightsOperator[];
  selfId?: number;
  roleUidByMember: Record<number, string>;
  onRoleUidChange: (memberId: number, uid: string) => void;
  onRemoveMember: (memberId: number) => void;
}) {
  return (
    <div
      style={{
        overflowX: "auto",
        overflowY: "hidden",
        WebkitOverflowScrolling: "touch",
        border: "1px solid rgba(0,0,0,0.06)",
        borderRadius: 10,
        background: "#f0f0f0",
      }}
    >
      {rows.map((row, idx) => {
        const progress =
          row.status === "ok" ? computeRarityProgress(row, catalog) : null;
        return (
          <div
            key={row.member_id}
            style={{
              display: "flex",
              alignItems: "stretch",
              minHeight: CARD_H * 2 + CARD_GAP + 24,
              borderBottom:
                idx === rows.length - 1
                  ? "none"
                  : "1px solid rgba(0,0,0,0.06)",
              background: idx % 2 ? "#f7f7f7" : "#fafafa",
            }}
          >
            <RowLabel
              row={row}
              progress={progress}
              selectedUid={roleUidByMember[row.member_id]}
              canRemove={row.member_id !== selfId}
              onUidChange={(uid) => onRoleUidChange(row.member_id, uid)}
              onRemove={() => onRemoveMember(row.member_id)}
            />
            <div
              style={{
                display: "grid",
                gridTemplateRows: `${CARD_H}px ${CARD_H}px`,
                gridAutoFlow: "column",
                gridAutoColumns: CARD_W,
                gap: CARD_GAP,
                padding: "10px 12px",
                alignItems: "start",
              }}
            >
              {row.status !== "ok" ? (
                <Typography.Text
                  type="secondary"
                  style={{ padding: "0 8px", gridRow: "1 / span 2" }}
                >
                  {row.message || "无法读取盒子"}
                </Typography.Text>
              ) : (
                orderedOps.map((op) => {
                  const owned = row.owned[op.char_id];
                  return owned ? (
                    <OwnedCard
                      key={op.char_id}
                      op={op}
                      owned={owned}
                      ownerName={row.nickname}
                      channelName={row.channel_name}
                      roleName={row.role_name}
                    />
                  ) : (
                    <MissingCard key={op.char_id} op={op} />
                  );
                })
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AddCompareCard({
  disabled,
  loading,
  candidates,
  onAdd,
}: {
  disabled?: boolean;
  loading?: boolean;
  candidates: ArknightsCompareCandidate[];
  onAdd: (memberId: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<number | null>(null);

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          setPicked(null);
          setOpen(true);
        }}
        style={{
          width: "100%",
          minHeight: 88,
          marginTop: 12,
          border: "1px dashed rgba(0,0,0,0.18)",
          borderRadius: 10,
          background: disabled ? "#f5f5f5" : "#fafafa",
          cursor: disabled ? "not-allowed" : "pointer",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
          color: disabled ? "#bfbfbf" : "#666",
          transition: "border-color 0.2s, background 0.2s, color 0.2s",
        }}
        onMouseEnter={(e) => {
          if (disabled) return;
          e.currentTarget.style.borderColor = "#1677ff";
          e.currentTarget.style.color = "#1677ff";
          e.currentTarget.style.background = "#f0f7ff";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "rgba(0,0,0,0.18)";
          e.currentTarget.style.color = disabled ? "#bfbfbf" : "#666";
          e.currentTarget.style.background = disabled ? "#f5f5f5" : "#fafafa";
        }}
      >
        <PlusOutlined style={{ fontSize: 22 }} />
        <span style={{ fontSize: 14, fontWeight: 500 }}>新增对比</span>
        {disabled ? (
          <span style={{ fontSize: 12 }}>最多 {COMPARE_MAX} 人</span>
        ) : null}
      </button>

      <Modal
        title="新增对比成员"
        open={open}
        onCancel={() => setOpen(false)}
        okText="添加"
        cancelText="取消"
        confirmLoading={loading}
        okButtonProps={{ disabled: picked == null }}
        onOk={() => {
          if (picked == null) return;
          onAdd(picked);
          setOpen(false);
        }}
        destroyOnClose
      >
        <Select
          showSearch
          optionFilterProp="label"
          placeholder="选择 Steam 好友"
          style={{ width: "100%" }}
          loading={loading}
          value={picked ?? undefined}
          onChange={(id: number) => setPicked(id)}
          options={candidates.map((c) => ({
            value: c.member_id,
            label: `${c.nickname}${c.is_self ? "（我）" : ""}${
              c.skland_bound ? "" : " · 未绑森空岛"
            }`,
          }))}
        />
        <Typography.Text
          type="secondary"
          style={{ display: "block", marginTop: 10, fontSize: 12 }}
        >
          需为 Steam 双向好友。添加后可在左侧切换渠道服。
        </Typography.Text>
      </Modal>
    </>
  );
}

/** 明日方舟页：多用户盒子横向对比（共用同一横向滚动） */
export function ArknightsBoxCompare() {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [initialized, setInitialized] = useState(false);
  const [sortMode, setSortMode] = useState<SortMode>("catalog");
  const [keyword, setKeyword] = useState("");
  const [rarityFilter, setRarityFilter] = useState<number | "all">("all");
  const [professionFilter, setProfessionFilter] = useState<string>("all");
  const [roleUidByMember, setRoleUidByMember] = useState<
    Record<number, string>
  >(loadRoleUidByMember);

  const updateRoleUid = (memberId: number, uid: string) => {
    setRoleUidByMember((prev) => {
      const next = { ...prev, [memberId]: uid };
      saveRoleUidByMember(next);
      return next;
    });
  };

  const candidatesQuery = useQuery({
    queryKey: ["arknights-compare-candidates"],
    queryFn: fetchArknightsCompareCandidates,
    retry: false,
  });

  const selfId = useMemo(
    () => candidatesQuery.data?.find((c) => c.is_self)?.member_id,
    [candidatesQuery.data],
  );

  useEffect(() => {
    if (initialized || selfId == null) return;
    setSelectedIds([selfId]);
    setInitialized(true);
  }, [selfId, initialized]);

  const compareIds = useMemo(() => {
    const ids = selectedIds.slice(0, COMPARE_MAX);
    if (selfId == null || !ids.includes(selfId)) return ids;
    return [selfId, ...ids.filter((id) => id !== selfId)];
  }, [selectedIds, selfId]);

  const addableCandidates = useMemo(
    () =>
      (candidatesQuery.data || []).filter(
        (c) => !compareIds.includes(c.member_id),
      ),
    [candidatesQuery.data, compareIds],
  );

  const activeRoleUids = useMemo(() => {
    const next: Record<number, string> = {};
    for (const id of compareIds) {
      const uid = roleUidByMember[id];
      if (uid) next[id] = uid;
    }
    return next;
  }, [compareIds, roleUidByMember]);

  const roleUidKey = useMemo(
    () =>
      Object.entries(activeRoleUids)
        .map(([id, uid]) => `${id}:${uid}`)
        .sort()
        .join(","),
    [activeRoleUids],
  );

  const compareQuery = useQuery({
    queryKey: ["arknights-box-compare", compareIds.join(","), roleUidKey],
    queryFn: () => fetchArknightsBoxCompare(compareIds, activeRoleUids),
    enabled: compareIds.length > 0,
    retry: false,
  });

  const displayRows = useMemo(() => {
    const rows = compareQuery.data?.rows || [];
    if (selfId == null) return rows;
    const selfRow = rows.find((r) => r.member_id === selfId);
    if (!selfRow) return rows;
    return [selfRow, ...rows.filter((r) => r.member_id !== selfId)];
  }, [compareQuery.data?.rows, selfId]);

  // 清理已失效的渠道服记忆（角色列表里已不存在）
  useEffect(() => {
    if (!displayRows.length) return;
    setRoleUidByMember((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const row of displayRows) {
        const saved = next[row.member_id];
        if (!saved) continue;
        const roles = row.roles || [];
        if (roles.length > 0 && !roles.some((r) => r.uid === saved)) {
          delete next[row.member_id];
          changed = true;
        }
      }
      if (!changed) return prev;
      saveRoleUidByMember(next);
      return next;
    });
  }, [displayRows]);

  const professions = useMemo(() => {
    const set = new Set<string>();
    for (const op of compareQuery.data?.catalog || []) {
      if (op.profession_label) set.add(op.profession_label);
    }
    return Array.from(set).sort();
  }, [compareQuery.data?.catalog]);

  const orderedOps = useMemo(() => {
    let catalog = compareQuery.data?.catalog || [];
    const q = keyword.trim().toLowerCase();
    catalog = catalog.filter((op) => {
      if (rarityFilter !== "all" && op.rarity !== rarityFilter) return false;
      if (
        professionFilter !== "all" &&
        op.profession_label !== professionFilter
      ) {
        return false;
      }
      if (
        q &&
        !op.name.toLowerCase().includes(q) &&
        !op.char_id.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });

    if (sortMode !== "level" || !compareQuery.data?.rows.length) {
      return catalog;
    }
    const keyRow =
      compareQuery.data.rows.find((r) => r.member_id === selfId) ||
      compareQuery.data.rows[0];
    return [...catalog].sort((a, b) => {
      const oa = keyRow.owned[a.char_id];
      const ob = keyRow.owned[b.char_id];
      if (!oa && !ob) return 0;
      if (!oa) return 1;
      if (!ob) return -1;
      if (ob.evolve_phase !== oa.evolve_phase) {
        return ob.evolve_phase - oa.evolve_phase;
      }
      if (ob.level !== oa.level) return ob.level - oa.level;
      if (b.rarity !== a.rarity) return b.rarity - a.rarity;
      return a.char_id.localeCompare(b.char_id);
    });
  }, [
    compareQuery.data,
    sortMode,
    selfId,
    keyword,
    rarityFilter,
    professionFilter,
  ]);

  const addMember = (memberId: number) => {
    setSelectedIds((prev) => {
      if (prev.includes(memberId) || prev.length >= COMPARE_MAX) return prev;
      if (selfId != null && (memberId === selfId || prev.includes(selfId))) {
        const rest = prev.filter((id) => id !== selfId && id !== memberId);
        return [selfId, ...rest, memberId].slice(0, COMPARE_MAX);
      }
      return [...prev, memberId].slice(0, COMPARE_MAX);
    });
  };

  const removeMember = (memberId: number) => {
    if (selfId != null && memberId === selfId) return;
    setSelectedIds((prev) => prev.filter((id) => id !== memberId));
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card size="small">
        <Space wrap style={{ width: "100%" }}>
          <Input.Search
            allowClear
            placeholder="搜索干员"
            style={{ width: 160 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <Select
            style={{ width: 110 }}
            value={rarityFilter}
            onChange={setRarityFilter}
            options={[
              { value: "all", label: "全部星级" },
              ...[6, 5, 4, 3, 2, 1].map((n) => ({
                value: n,
                label: `${n}★`,
              })),
            ]}
          />
          <Select
            style={{ width: 120 }}
            value={professionFilter}
            onChange={setProfessionFilter}
            options={[
              { value: "all", label: "全部职业" },
              ...professions.map((p) => ({ value: p, label: p })),
            ]}
          />
          <Select
            value={sortMode}
            style={{ width: 150 }}
            onChange={(v: SortMode) => setSortMode(v)}
            options={[
              { value: "catalog", label: "稀有度排序" },
              { value: "level", label: "等级（以我为准）" },
            ]}
          />
        </Space>
      </Card>

      {candidatesQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="无法加载可选成员"
          description={apiError(candidatesQuery.error, "请稍后重试")}
        />
      ) : null}

      {compareIds.length === 0 ? (
        <Empty description="加载中…" />
      ) : compareQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="加载盒子失败"
          description={apiError(compareQuery.error, "请稍后重试")}
        />
      ) : compareQuery.isLoading ? (
        <Card loading />
      ) : compareQuery.data ? (
        <div>
          <Typography.Text
            type="secondary"
            style={{ display: "block", marginBottom: 8 }}
          >
            展示 {orderedOps.length} / {compareQuery.data.catalog.length} 名干员
            {compareQuery.data.catalog_version
              ? ` · 资源 ${compareQuery.data.catalog_version}`
              : ""}
          </Typography.Text>
          {orderedOps.length ? (
            <SyncCompareBoard
              rows={displayRows}
              orderedOps={orderedOps}
              catalog={compareQuery.data.catalog}
              selfId={selfId}
              roleUidByMember={roleUidByMember}
              onRoleUidChange={updateRoleUid}
              onRemoveMember={removeMember}
            />
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="没有符合筛选的干员"
            />
          )}
          <AddCompareCard
            disabled={
              compareIds.length >= COMPARE_MAX || addableCandidates.length === 0
            }
            loading={candidatesQuery.isLoading}
            candidates={addableCandidates}
            onAdd={addMember}
          />
        </div>
      ) : null}
    </Space>
  );
}
