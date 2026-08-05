import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import {
  Alert,
  Button,
  Empty,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { fetchEndfieldBox } from "@/api/client";
import type {
  EndfieldChar,
  EndfieldEquip,
  EndfieldSkill,
} from "@/api/types";
import {
  EQUIP_SLOTS,
  RARITY_COLOR,
  ROW_GRID,
  SKILL_COLS,
} from "./endfield/constants";
import {
  formatOwnTs,
  formatSyncedAt,
  isLimited,
  skillBgForChar,
  skillByType,
} from "./endfield/helpers";

function IconImg({
  src,
  alt,
  size = 36,
}: {
  src?: string | null;
  alt: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: 6,
          background: "rgba(255,255,255,0.12)",
          flexShrink: 0,
        }}
      />
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      style={{ objectFit: "contain", borderRadius: 6, flexShrink: 0 }}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}

function SkillCell({
  skill,
  bg,
}: {
  skill: EndfieldSkill | null;
  bg: string;
}) {
  if (!skill) {
    return (
      <div style={{ minWidth: 0, opacity: 0.35 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 8,
            background: "#f0f0f0",
          }}
        />
        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
          —
        </Typography.Text>
      </div>
    );
  }
  return (
    <div style={{ minWidth: 0 }}>
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: 8,
          background: bg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <IconImg src={skill.icon_url} alt={skill.name} size={28} />
      </div>
      <Typography.Text
        ellipsis
        title={skill.name}
        style={{
          display: "block",
          fontSize: 11,
          marginTop: 4,
          maxWidth: "100%",
        }}
      >
        {skill.name || "技能"}
      </Typography.Text>
      <Typography.Text type="secondary" style={{ fontSize: 11 }}>
        {skill.level}
        {skill.max_level ? `/${skill.max_level}` : ""}
      </Typography.Text>
    </div>
  );
}

function EquipCell({
  label,
  equip,
  size = 72,
}: {
  label: string;
  equip: EndfieldEquip | null;
  size?: number;
}) {
  return (
    <div style={{ textAlign: "center", width: size + 16, flexShrink: 0 }}>
      {equip ? (
        <IconImg src={equip.icon_url} alt={equip.name} size={size} />
      ) : (
        <div
          style={{
            width: size,
            height: size,
            margin: "0 auto",
            borderRadius: 8,
            border: "1px dashed #d9d9d9",
            background: "#fafafa",
          }}
        />
      )}
      <Typography.Text
        type="secondary"
        style={{ display: "block", fontSize: 11, marginTop: 6 }}
      >
        {label}
      </Typography.Text>
      <Typography.Text
        ellipsis
        title={equip?.name}
        style={{ display: "block", fontSize: 12, maxWidth: size + 16 }}
      >
        {equip?.name || "—"}
      </Typography.Text>
    </div>
  );
}

function CharExpanded({ char }: { char: EndfieldChar }) {
  const own = formatOwnTs(char.own_ts);
  const equipMap = useMemo(() => {
    const m = new Map<string, EndfieldEquip>();
    for (const e of char.equips || []) m.set(e.slot, e);
    return m;
  }, [char.equips]);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(140px, 200px) 1fr",
        gap: 20,
        padding: "16px 12px",
        background: "#fafafa",
        borderTop: "1px solid #f0f0f0",
      }}
    >
      <div>
        {char.illustration_url ? (
          <img
            src={char.illustration_url}
            alt={char.name}
            style={{
              width: "100%",
              maxHeight: 280,
              objectFit: "contain",
              borderRadius: 8,
              background: "#fff",
            }}
            referrerPolicy="no-referrer"
          />
        ) : (
          <IconImg src={char.avatar_url} alt={char.name} size={140} />
        )}
      </div>

      <div style={{ minWidth: 0 }}>
        <Space wrap size={[8, 8]} style={{ marginBottom: 8 }}>
          <Tag color={RARITY_COLOR[char.rarity] || "default"}>
            {char.rarity}★
          </Tag>
          {char.property_name ? (
            <Tag>
              <Space size={4}>
                {char.property_icon_url ? (
                  <IconImg
                    src={char.property_icon_url}
                    alt={char.property_name}
                    size={14}
                  />
                ) : null}
                {char.property_name}
              </Space>
            </Tag>
          ) : null}
          {char.profession ? <Tag>{char.profession}</Tag> : null}
          {char.weapon_type ? <Tag>{char.weapon_type}</Tag> : null}
          {isLimited(char.label_type) ? <Tag color="magenta">限定</Tag> : null}
        </Space>

        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
          Lv.{char.level}
          {char.evolve_phase > 0 ? ` · 精英${char.evolve_phase}` : ""}
          {char.potential_level > 0 ? ` · 潜能${char.potential_level}` : ""}
          {own ? ` · 获得 ${own}` : ""}
        </Typography.Text>

        <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
          武器 / 装备
        </Typography.Text>
        <div
          style={{
            display: "flex",
            flexWrap: "nowrap",
            alignItems: "flex-start",
            gap: 20,
            overflowX: "auto",
            paddingBottom: 4,
          }}
        >
          <div style={{ textAlign: "center", width: 96, flexShrink: 0 }}>
            {char.weapon ? (
              <IconImg
                src={char.weapon.icon_url}
                alt={char.weapon.name}
                size={80}
              />
            ) : (
              <div
                style={{
                  width: 80,
                  height: 80,
                  margin: "0 auto",
                  borderRadius: 8,
                  border: "1px dashed #d9d9d9",
                  background: "#fff",
                }}
              />
            )}
            <Typography.Text
              type="secondary"
              style={{ display: "block", fontSize: 11, marginTop: 6 }}
            >
              武器
            </Typography.Text>
            <Typography.Text
              ellipsis
              title={char.weapon?.name}
              style={{ display: "block", fontSize: 12, maxWidth: 96 }}
            >
              {char.weapon?.name || "未装备"}
            </Typography.Text>
            {char.weapon ? (
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                {char.weapon.rarity}★ · Lv.{char.weapon.level}
                {char.weapon.refine_level > 0
                  ? ` · 潜能${char.weapon.refine_level}`
                  : ""}
                {char.weapon.breakthrough_level > 0
                  ? ` · 突破${char.weapon.breakthrough_level}`
                  : ""}
              </Typography.Text>
            ) : null}
            {char.weapon && (char.weapon.gem_name || char.weapon.gem_icon_url) ? (
              <Space size={4} style={{ marginTop: 4, justifyContent: "center" }}>
                <IconImg
                  src={char.weapon.gem_icon_url}
                  alt={char.weapon.gem_name || "宝石"}
                  size={18}
                />
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  {char.weapon.gem_name || "宝石"}
                </Typography.Text>
              </Space>
            ) : null}
          </div>

          {EQUIP_SLOTS.map((s) => (
            <EquipCell
              key={s.slot}
              label={s.label}
              equip={equipMap.get(s.slot) || null}
              size={80}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function CharRow({
  char,
  expanded,
  onToggle,
}: {
  char: EndfieldChar;
  expanded: boolean;
  onToggle: () => void;
}) {
  const border = RARITY_COLOR[char.rarity] || "#d9d9d9";
  const skillBg = skillBgForChar(char);
  return (
    <div style={{ borderBottom: "1px solid #f0f0f0" }}>
      <button
        type="button"
        onClick={onToggle}
        style={{
          display: "grid",
          gridTemplateColumns: ROW_GRID,
          columnGap: 10,
          alignItems: "center",
          width: "100%",
          boxSizing: "border-box",
          padding: "10px 12px",
          border: "none",
          background: expanded ? "#fafafa" : "#fff",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: 10,
            alignItems: "center",
            minWidth: 0,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              border: `2px solid ${border}`,
              borderRadius: 8,
              padding: 2,
              lineHeight: 0,
              flexShrink: 0,
            }}
          >
            <IconImg src={char.avatar_url} alt={char.name} size={48} />
          </div>
          <div style={{ minWidth: 0, overflow: "hidden" }}>
            <div style={{ display: "flex", gap: 6, alignItems: "baseline" }}>
              <Typography.Text strong ellipsis style={{ margin: 0 }}>
                {char.name}
              </Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12, flexShrink: 0 }}>
                {char.rarity}★
              </Typography.Text>
            </div>
            <Typography.Text
              type="secondary"
              style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}
            >
              {char.property_icon_url ? (
                <IconImg
                  src={char.property_icon_url}
                  alt={char.property_name || ""}
                  size={14}
                />
              ) : null}
              Lv.{char.level}
              {char.property_name ? ` · ${char.property_name}` : ""}
            </Typography.Text>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            minWidth: 0,
            overflow: "hidden",
          }}
        >
          {char.weapon ? (
            <>
              <IconImg
                src={char.weapon.icon_url}
                alt={char.weapon.name}
                size={40}
              />
              <div style={{ minWidth: 0, overflow: "hidden" }}>
                <Typography.Text ellipsis style={{ display: "block" }}>
                  {char.weapon.name}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Lv.{char.weapon.level}
                </Typography.Text>
              </div>
            </>
          ) : (
            <Typography.Text type="secondary">—</Typography.Text>
          )}
        </div>

        {SKILL_COLS.map((col) => (
          <SkillCell
            key={col.key}
            skill={skillByType(char.skills || [], col.match)}
            bg={skillBg}
          />
        ))}

        <Typography.Text type="secondary" style={{ textAlign: "center" }}>
          {expanded ? "∨" : "›"}
        </Typography.Text>
      </button>
      {expanded ? <CharExpanded char={char} /> : null}
    </div>
  );
}

type Props = {
  enabled: boolean;
};

export function EndfieldBoxPanel({ enabled }: Props) {
  const queryClient = useQueryClient();
  const [uid, setUid] = useState<string | undefined>(undefined);
  const [rarityTab, setRarityTab] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const boxQuery = useQuery({
    queryKey: ["endfield-box", uid || "default"],
    queryFn: () => fetchEndfieldBox(uid),
    enabled,
    retry: false,
  });

  const roles = boxQuery.data?.roles || [];
  const chars = boxQuery.data?.chars || [];

  const filtered = useMemo(() => {
    if (rarityTab === "all") return chars;
    const n = Number(rarityTab);
    return chars.filter((c) => c.rarity === n);
  }, [chars, rarityTab]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await fetchEndfieldBox(uid, true);
      queryClient.setQueryData(["endfield-box", uid || "default"], data);
      message.success("已同步终末地养成数据");
    } catch (e: unknown) {
      message.error(apiError(e, "同步失败"));
    } finally {
      setRefreshing(false);
    }
  };

  if (!enabled) {
    return <Empty description="绑定森空岛后可查看终末地养成" />;
  }

  if (boxQuery.isLoading) {
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <Spin tip="加载养成数据…" />
      </div>
    );
  }

  if (boxQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="无法加载终末地养成"
        description={apiError(boxQuery.error, "请稍后重试或点击刷新")}
        action={
          <Button size="small" onClick={() => onRefresh()} loading={refreshing}>
            刷新
          </Button>
        }
      />
    );
  }

  const box = boxQuery.data;
  if (!box) {
    return <Empty description="暂无数据" />;
  }

  return (
    <div>
      {box.stale ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="展示的是本地缓存，上游刷新失败"
          action={
            <Button size="small" onClick={() => onRefresh()} loading={refreshing}>
              重试
            </Button>
          }
        />
      ) : null}

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <Space wrap size={12}>
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {box.name}
            </Typography.Title>
            <Typography.Text type="secondary">
              权限等阶 Lv.{box.level}
              {box.server_name ? ` · ${box.server_name}` : ""}
              {box.uid ? ` · UID ${box.uid}` : ""}
            </Typography.Text>
          </div>
          {roles.length > 1 ? (
            <Select
              style={{ minWidth: 180 }}
              value={uid || box.uid}
              options={roles.map((r) => ({
                value: r.uid,
                label: `${r.role_name} · ${r.channel_name}`,
              }))}
              onChange={(v) => {
                setUid(v);
                setExpandedId(null);
              }}
            />
          ) : null}
        </Space>
        <Space>
          {box.synced_at ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              同步于 {formatSyncedAt(box.synced_at)}
            </Typography.Text>
          ) : null}
          <Button
            icon={<ReloadOutlined />}
            loading={refreshing}
            onClick={() => onRefresh()}
          >
            刷新
          </Button>
        </Space>
      </div>

      <Tabs
        activeKey={rarityTab}
        onChange={(k) => {
          setRarityTab(k);
          setExpandedId(null);
        }}
        items={[
          { key: "all", label: `全部 (${chars.length})` },
          {
            key: "6",
            label: `六星 (${chars.filter((c) => c.rarity === 6).length})`,
          },
          {
            key: "5",
            label: `五星 (${chars.filter((c) => c.rarity === 5).length})`,
          },
          {
            key: "4",
            label: `四星 (${chars.filter((c) => c.rarity === 4).length})`,
          },
        ]}
      />

      {filtered.length ? (
        <div
          style={{
            border: "1px solid #f0f0f0",
            borderRadius: 8,
            overflow: "hidden",
            background: "#fff",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: ROW_GRID,
              columnGap: 10,
              boxSizing: "border-box",
              padding: "10px 12px 8px",
              color: "#888",
              fontSize: 12,
              borderBottom: "1px solid #f0f0f0",
              background: "#fafafa",
            }}
          >
            <span>干员 / 等级</span>
            <span>武器</span>
            {SKILL_COLS.map((c) => (
              <span key={c.key}>{c.label}</span>
            ))}
            <span />
          </div>
          {filtered.map((c) => (
            <CharRow
              key={c.char_id}
              char={c}
              expanded={expandedId === c.char_id}
              onToggle={() =>
                setExpandedId((id) => (id === c.char_id ? null : c.char_id))
              }
            />
          ))}
        </div>
      ) : (
        <Empty description="该筛选下无干员" style={{ marginTop: 24 }} />
      )}
    </div>
  );
}
