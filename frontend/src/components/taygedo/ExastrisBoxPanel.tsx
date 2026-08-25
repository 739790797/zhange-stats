import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Empty, Space, Tabs, Tag, Typography, message } from "antd";
import { fetchExastrisBox } from "@/api/client";
import type { ExastrisChar } from "@/api/types";
import { BoxPanelChrome } from "@/components/BoxPanelChrome";
import { apiError } from "@/lib/apiError";

const EMPTY_CHARS: ExastrisChar[] = [];

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

  const box = boxQuery.data;

  return (
    <BoxPanelChrome
      enabled={enabled}
      disabledDescription="绑定塔吉多后可查看异环角色盒子"
      loading={boxQuery.isLoading}
      loadingTip="加载异环角色…"
      error={boxQuery.error}
      errorTitle="无法加载异环角色盒子"
      empty={!box}
      refreshing={refreshing}
      onRefresh={() => void onRefresh()}
      stale={box?.stale}
      title={box?.role_name || "异环"}
      subtitle={
        box
          ? `${box.char_count} 名角色${box.uid ? ` · UID ${box.uid}` : ""}`
          : undefined
      }
      roles={roles.map((r) => ({ uid: r.uid, label: r.role_name }))}
      selectedUid={uid || box?.uid}
      onSelectUid={setUid}
      syncedAt={box?.synced_at}
    >
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
    </BoxPanelChrome>
  );
}
