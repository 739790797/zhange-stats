import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ReloadOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Col,
  Empty,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
  message,
} from "antd";
import { fetchWwBox } from "@/api/client";
import type { WwBoxItem } from "@/api/types";
import { apiError } from "@/lib/apiError";

function formatSyncedAt(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}

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

  if (!enabled) {
    return <Empty description="绑定库街区后可查看鸣潮资料卡" />;
  }

  if (boxQuery.isLoading) {
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <Spin tip="加载鸣潮资料卡…" />
      </div>
    );
  }

  if (boxQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="无法加载鸣潮资料卡"
        description={apiError(boxQuery.error, "请稍后重试或点击刷新")}
        action={
          <Button size="small" onClick={() => onRefresh()} loading={refreshing}>
            刷新
          </Button>
        }
      />
    );
  }

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
              {box.role_name || "鸣潮"}
            </Typography.Title>
            <Typography.Text type="secondary">
              联觉 {box.level}
              {box.world_level ? ` · 索拉 ${box.world_level}` : ""}
              {box.uid ? ` · UID ${box.uid}` : ""}
              {box.server_name ? ` · ${box.server_name}` : ""}
            </Typography.Text>
          </div>
          {roles.length > 1 ? (
            <Select
              style={{ minWidth: 180 }}
              value={uid || box.uid}
              options={roles.map((r) => ({
                value: r.uid,
                label: r.role_name,
              }))}
              onChange={(v) => setUid(v)}
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
    </div>
  );
}
