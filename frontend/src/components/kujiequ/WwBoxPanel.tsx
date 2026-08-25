import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Col,
  Progress,
  Row,
  Space,
  Statistic,
  Tag,
  Typography,
  message,
} from "antd";
import { fetchWwBox } from "@/api/client";
import type { WwBoxItem } from "@/api/types";
import { BoxPanelChrome } from "@/components/BoxPanelChrome";
import { apiError } from "@/lib/apiError";

function ItemChips({ items, title }: { items: WwBoxItem[]; title: string }) {
  if (!items.length) return null;
  return (
    <div style={{ marginTop: 16 }}>
      <Typography.Text strong>{title}</Typography.Text>
      <Space wrap size={[8, 8]} style={{ marginTop: 8, display: "flex" }}>
        {items.map((it) => (
          <Tag key={it.name} style={{ margin: 0 }}>
            {it.name} ×{it.num}
          </Tag>
        ))}
      </Space>
    </div>
  );
}

function StatBlock({
  title,
  value,
  suffix,
  iconUrl,
}: {
  title: string;
  value: string | number;
  suffix?: string;
  iconUrl?: string | null;
}) {
  return (
    <div
      style={{
        border: "1px solid rgba(0,0,0,0.06)",
        borderRadius: 10,
        padding: 12,
        background: "#fff",
        minHeight: 88,
      }}
    >
      <Space size={8} align="start">
        {iconUrl ? (
          <img
            src={iconUrl}
            alt=""
            width={28}
            height={28}
            style={{ objectFit: "contain", borderRadius: 4 }}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : null}
        <Statistic title={title} value={value} suffix={suffix} />
      </Space>
    </div>
  );
}

type Props = {
  enabled: boolean;
};

export function WwBoxPanel({ enabled }: Props) {
  const queryClient = useQueryClient();
  const [uid, setUid] = useState<string | undefined>(undefined);
  const [refreshing, setRefreshing] = useState(false);

  const boxQuery = useQuery({
    queryKey: ["ww-box", uid || "default"],
    queryFn: () => fetchWwBox(uid, false),
    enabled,
    retry: false,
  });

  const roles = boxQuery.data?.roles || [];
  const box = boxQuery.data;

  const calabashPct = useMemo(() => {
    if (!box || !box.calabash_max) return 0;
    return Math.min(100, Math.round((box.calabash_unlock / box.calabash_max) * 100));
  }, [box]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await fetchWwBox(uid, true);
      queryClient.setQueryData(["ww-box", uid || "default"], data);
      message.success("已同步鸣潮资料卡");
    } catch (e: unknown) {
      message.error(apiError(e, "同步失败"));
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <BoxPanelChrome
      enabled={enabled}
      disabledDescription="绑定库街区后可查看鸣潮资料卡"
      loading={boxQuery.isLoading}
      loadingTip="加载鸣潮资料卡…"
      error={boxQuery.error}
      errorTitle="无法加载鸣潮资料卡"
      empty={!box}
      refreshing={refreshing}
      onRefresh={() => void onRefresh()}
      stale={box?.stale}
      title={box?.role_name || "鸣潮"}
      subtitle={
        box
          ? `联觉 ${box.level}${box.world_level ? ` · 索拉 ${box.world_level}` : ""}${box.uid ? ` · UID ${box.uid}` : ""}${box.server_name ? ` · ${box.server_name}` : ""}`
          : undefined
      }
      roles={roles.map((r) => ({ uid: r.uid, label: r.role_name }))}
      selectedUid={uid || box?.uid}
      onSelectUid={setUid}
      syncedAt={box?.synced_at}
    >
      {!box ? null : (
      <>
      <Row gutter={[12, 12]}>
        <Col xs={12} sm={8} md={6}>
          <StatBlock title="活跃天数" value={box.active_days} />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <StatBlock title="解锁角色" value={box.role_num} />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <StatBlock
            title="成就"
            value={box.achievement_count}
            suffix={box.achievement_star ? `星 ${box.achievement_star}` : undefined}
          />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <StatBlock
            title="结晶波片"
            value={`${box.energy}/${box.max_energy || "—"}`}
          />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <StatBlock
            title={box.store_energy_title || "结晶单质"}
            value={`${box.store_energy}/${box.store_energy_limit || "—"}`}
            iconUrl={box.store_energy_icon_url}
          />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <StatBlock
            title="活跃度"
            value={`${box.liveness}/${box.liveness_max || "—"}`}
          />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <StatBlock title="小型信标" value={box.small_count} />
        </Col>
        <Col xs={12} sm={8} md={6}>
          <StatBlock title="中型信标" value={box.big_count} />
        </Col>
        {box.sound_box > 0 ? (
          <Col xs={12} sm={8} md={6}>
            <StatBlock title="声匣" value={box.sound_box} />
          </Col>
        ) : null}
        <Col xs={12} sm={8} md={6}>
          <StatBlock
            title={box.weekly_inst_title || "战歌重奏"}
            value={`${box.weekly_inst_count}/${box.weekly_inst_limit || "—"}`}
            iconUrl={box.weekly_inst_icon_url}
          />
        </Col>
        {(box.rouge_title || box.rouge_score > 0) && (
          <Col xs={12} sm={8} md={6}>
            <StatBlock
              title={box.rouge_title || "肉鸽"}
              value={`${box.rouge_score}/${box.rouge_score_limit || "—"}`}
              iconUrl={box.rouge_icon_url}
            />
          </Col>
        )}
      </Row>

      {(box.calabash_max > 0 || box.calabash_level > 0) && (
        <div style={{ marginTop: 20 }}>
          <Typography.Text strong>
            数据坞 Lv.{box.calabash_level}
            {box.calabash_cost > 0 ? ` · COST ${box.calabash_cost}` : ""}
          </Typography.Text>
          <div style={{ marginTop: 8, maxWidth: 420 }}>
            <Progress
              percent={calabashPct}
              format={() => `${box.calabash_unlock}/${box.calabash_max}`}
            />
          </div>
        </div>
      )}

      <ItemChips items={box.treasure_boxes || []} title="奇藏箱" />
      <ItemChips items={box.phantom_boxes || []} title="潮汐之遗" />
      </>
      )}
    </BoxPanelChrome>
  );
}
