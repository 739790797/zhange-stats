import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ReloadOutlined } from "@ant-design/icons";
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
import { fetchExastrisBox } from "@/api/client";
import type { ExastrisChar } from "@/api/types";
import { apiError } from "@/lib/apiError";

const EMPTY_CHARS: ExastrisChar[] = [];

function formatSyncedAt(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}

function qualityColor(quality: string): string {
  const q = quality.toUpperCase();
  if (q === "S") return "gold";
  if (q === "A") return "purple";
  return "default";
}

function Portrait({
  src,
  alt,
}: {
  src?: string | null;
  alt: string;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div
        style={{
          width: "100%",
          aspectRatio: "3 / 4",
          borderRadius: 8,
          background: "rgba(0,0,0,0.06)",
        }}
      />
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      style={{
        width: "100%",
        aspectRatio: "3 / 4",
        objectFit: "cover",
        borderRadius: 8,
        display: "block",
        background: "rgba(0,0,0,0.04)",
      }}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}

function CharCard({ char }: { char: ExastrisChar }) {
  const meta = [char.element_type, char.group_type].filter(Boolean).join(" · ");
  return (
    <div
      style={{
        border: "1px solid rgba(0,0,0,0.06)",
        borderRadius: 10,
        padding: 10,
        background: "#fff",
        minWidth: 0,
      }}
    >
      <Portrait src={char.portrait_url} alt={char.name} />
      <div style={{ marginTop: 8, minWidth: 0 }}>
        <Typography.Text ellipsis strong style={{ display: "block" }}>
          {char.name}
        </Typography.Text>
        <Space size={4} wrap style={{ marginTop: 4 }}>
          {char.quality ? (
            <Tag color={qualityColor(char.quality)} style={{ margin: 0 }}>
              {char.quality}
            </Tag>
          ) : null}
          {char.awaken_lev > 0 ? (
            <Tag style={{ margin: 0 }}>觉醒 {char.awaken_lev}</Tag>
          ) : null}
        </Space>
        {meta ? (
          <Typography.Text
            type="secondary"
            style={{ fontSize: 12, display: "block", marginTop: 4 }}
            ellipsis
          >
            {meta}
          </Typography.Text>
        ) : null}
      </div>
    </div>
  );
}

type Props = {
  enabled: boolean;
};

export function ExastrisBoxPanel({ enabled }: Props) {
  const queryClient = useQueryClient();
  const [uid, setUid] = useState<string | undefined>(undefined);
  const [qualityTab, setQualityTab] = useState<string>("all");
  const [refreshing, setRefreshing] = useState(false);

  const boxQuery = useQuery({
    queryKey: ["exastris-box", uid || "default"],
    queryFn: () => fetchExastrisBox(uid, false),
    enabled,
    retry: false,
  });

  const roles = boxQuery.data?.roles || [];
  const chars = boxQuery.data?.chars ?? EMPTY_CHARS;

  const filtered = useMemo(() => {
    if (qualityTab === "all") return chars;
    return chars.filter(
      (c) => (c.quality || "").toUpperCase() === qualityTab.toUpperCase(),
    );
  }, [chars, qualityTab]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await fetchExastrisBox(uid, true);
      queryClient.setQueryData(["exastris-box", uid || "default"], data);
      message.success("已同步异环角色盒子");
    } catch (e: unknown) {
      message.error(apiError(e, "同步失败"));
    } finally {
      setRefreshing(false);
    }
  };

  if (!enabled) {
    return <Empty description="绑定塔吉多后可查看异环角色盒子" />;
  }

  if (boxQuery.isLoading) {
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <Spin tip="加载异环角色…" />
      </div>
    );
  }

  if (boxQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="无法加载异环角色盒子"
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
              {box.role_name || "异环"}
            </Typography.Title>
            <Typography.Text type="secondary">
              {box.char_count} 名角色
              {box.uid ? ` · UID ${box.uid}` : ""}
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

      <Tabs
        size="small"
        activeKey={qualityTab}
        onChange={setQualityTab}
        items={[
          { key: "all", label: `全部 (${chars.length})` },
          {
            key: "S",
            label: `S (${chars.filter((c) => c.quality.toUpperCase() === "S").length})`,
          },
          {
            key: "A",
            label: `A (${chars.filter((c) => c.quality.toUpperCase() === "A").length})`,
          },
        ]}
        style={{ marginBottom: 12 }}
      />

      {filtered.length === 0 ? (
        <Empty description="暂无角色" />
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: 12,
          }}
        >
          {filtered.map((c) => (
            <CharCard key={c.char_id} char={c} />
          ))}
        </div>
      )}
    </div>
  );
}
