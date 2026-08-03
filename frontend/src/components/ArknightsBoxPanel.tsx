import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Card,
  Empty,
  Input,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import { fetchArknightsBox } from "@/api/client";
import type { ArknightsChar, SklandRole } from "@/api/types";

const RARITY_COLOR: Record<number, string> = {
  6: "#f5a623",
  5: "#f0d55c",
  4: "#9b59d0",
  3: "#49b3e6",
  2: "#7dce82",
  1: "#9aa0a6",
};

function evolveLabel(phase: number) {
  if (phase >= 2) return "精二";
  if (phase >= 1) return "精一";
  return "精英0";
}

function CharCard({ char }: { char: ArknightsChar }) {
  const [imgFailed, setImgFailed] = useState(false);
  const border = RARITY_COLOR[char.rarity] || "#d9d9d9";
  return (
    <div
      style={{
        border: `2px solid ${border}`,
        borderRadius: 10,
        overflow: "hidden",
        background: "#fff",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          height: 88,
          background: `linear-gradient(160deg, ${border}33, #f5f5f5)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {!imgFailed && char.avatar_url ? (
          <img
            src={char.avatar_url}
            alt={char.name}
            width={72}
            height={72}
            style={{ objectFit: "contain" }}
            onError={() => setImgFailed(true)}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {char.rarity}★
          </Typography.Text>
        )}
      </div>
      <div style={{ padding: "8px 10px 10px" }}>
        <Typography.Text strong ellipsis style={{ display: "block" }}>
          {char.name}
        </Typography.Text>
        <Space size={4} wrap style={{ marginTop: 4 }}>
          <Tag style={{ margin: 0 }}>{char.rarity}★</Tag>
          <Tag style={{ margin: 0 }}>{char.profession_label}</Tag>
        </Space>
        <Typography.Text
          type="secondary"
          style={{ display: "block", marginTop: 6, fontSize: 12 }}
        >
          {evolveLabel(char.evolve_phase)} Lv.{char.level}
          {char.potential_rank > 0 ? ` · 潜${char.potential_rank}` : ""}
        </Typography.Text>
      </div>
    </div>
  );
}

type Props = {
  enabled: boolean;
  fallbackRoles?: SklandRole[];
};

export function ArknightsBoxPanel({ enabled, fallbackRoles = [] }: Props) {
  const arkRoles = useMemo(
    () => fallbackRoles.filter((r) => r.game_code === "arknights"),
    [fallbackRoles],
  );
  const [uid, setUid] = useState<string | undefined>(undefined);
  const [keyword, setKeyword] = useState("");
  const [rarityFilter, setRarityFilter] = useState<number | "all">("all");
  const [professionFilter, setProfessionFilter] = useState<string>("all");

  const boxQuery = useQuery({
    queryKey: ["skland-arknights-box", uid || "default"],
    queryFn: () => fetchArknightsBox(uid),
    enabled,
    retry: false,
  });

  const roles = boxQuery.data?.roles?.length ? boxQuery.data.roles : arkRoles;
  const activeUid = boxQuery.data?.uid || uid || roles[0]?.uid;

  const professions = useMemo(() => {
    const set = new Set<string>();
    for (const c of boxQuery.data?.chars || []) {
      if (c.profession_label) set.add(c.profession_label);
    }
    return Array.from(set).sort();
  }, [boxQuery.data?.chars]);

  const filtered = useMemo(() => {
    const q = keyword.trim().toLowerCase();
    return (boxQuery.data?.chars || []).filter((c) => {
      if (rarityFilter !== "all" && c.rarity !== rarityFilter) return false;
      if (professionFilter !== "all" && c.profession_label !== professionFilter) {
        return false;
      }
      if (q && !c.name.toLowerCase().includes(q) && !c.char_id.toLowerCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [boxQuery.data?.chars, keyword, rarityFilter, professionFilter]);

  if (!enabled) {
    return <Empty description="绑定森空岛后可查看干员盒子" />;
  }

  const errDetail =
    boxQuery.error &&
    typeof boxQuery.error === "object" &&
    "response" in boxQuery.error
      ? (boxQuery.error as { response?: { data?: { detail?: string } } }).response
          ?.data?.detail
      : null;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card size="small">
        <Space wrap style={{ width: "100%", justifyContent: "space-between" }}>
          <Space wrap>
            <Typography.Text type="secondary">账号</Typography.Text>
            <Select
              style={{ minWidth: 220 }}
              value={activeUid}
              placeholder="选择明日方舟账号"
              options={roles.map((r) => ({
                value: r.uid,
                label: `${r.role_name} · ${r.channel_name}`,
              }))}
              onChange={(v) => setUid(v)}
              loading={boxQuery.isFetching}
            />
            <Input.Search
              allowClear
              placeholder="搜索干员"
              style={{ width: 180 }}
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
          </Space>
          {boxQuery.data ? (
            <Typography.Text type="secondary">
              {boxQuery.data.name} · Lv.{boxQuery.data.level}
              {boxQuery.data.ap_current != null && boxQuery.data.ap_max != null
                ? ` · 理智 ${boxQuery.data.ap_current}/${boxQuery.data.ap_max}`
                : ""}
              {` · ${boxQuery.data.char_count} 名干员`}
              {filtered.length !== boxQuery.data.char_count
                ? `（筛选 ${filtered.length}）`
                : ""}
            </Typography.Text>
          ) : null}
        </Space>
      </Card>

      {boxQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="加载干员盒子失败"
          description={String(errDetail || (boxQuery.error as Error)?.message || "")}
        />
      ) : null}

      <Card loading={boxQuery.isLoading || boxQuery.isFetching}>
        {filtered.length ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(132px, 1fr))",
              gap: 12,
            }}
          >
            {filtered.map((c) => (
              <CharCard key={c.char_id} char={c} />
            ))}
          </div>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              boxQuery.isLoading ? "加载中…" : "没有符合筛选的干员"
            }
          />
        )}
      </Card>
    </Space>
  );
}
