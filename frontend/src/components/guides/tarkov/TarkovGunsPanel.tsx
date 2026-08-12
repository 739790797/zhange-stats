import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Space, Spin, Tag, Typography } from "antd";
import dayjs from "dayjs";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  fetchTarkovAmmo,
  fetchTarkovGuns,
  type TarkovGunItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { formatCaliberLabel } from "@/lib/tarkovGunCategories";
import { TarkovGunsTable } from "@/components/guides/tarkov/TarkovGunsTable";

const EMPTY_ITEMS: TarkovGunItem[] = [];

const GUN_SOURCE_LINKS: Record<string, { label: string; href: string }> = {
  "tarkov.dev": {
    label: "api.tarkov.dev/graphql",
    href: "https://api.tarkov.dev/graphql",
  },
  "json.tarkov.dev": {
    label: "json.tarkov.dev/regular/items",
    href: "https://json.tarkov.dev/regular/items",
  },
};

function formatSyncedAt(value: string | null | undefined): string {
  if (!value) return "—";
  const d = dayjs(value);
  return d.isValid() ? d.format("YYYY-MM-DD HH:mm:ss") : value;
}

function renderGunSource(source: string | null | undefined) {
  const key = (source || "").trim();
  const hit = GUN_SOURCE_LINKS[key];
  if (!hit) {
    return <Typography.Text type="secondary">{key || "未知"}</Typography.Text>;
  }
  return (
    <Typography.Link href={hit.href} target="_blank" rel="noreferrer">
      {hit.label}
    </Typography.Link>
  );
}

export function TarkovGunsPanel() {
  const [searchParams, setSearchParams] = useSearchParams();
  const ammoFilterId = (searchParams.get("ammo") || "").trim() || null;
  const caliberFilterParam =
    (searchParams.get("caliber") || "").trim() || null;

  const gunsQuery = useQuery({
    queryKey: ["guides-tarkov-guns"],
    queryFn: fetchTarkovGuns,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const ammoQuery = useQuery({
    queryKey: ["guides-tarkov-ammo"],
    queryFn: fetchTarkovAmmo,
    enabled: Boolean(ammoFilterId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const items = gunsQuery.data?.items ?? EMPTY_ITEMS;

  const ammoFilterLabel = useMemo(() => {
    if (!ammoFilterId) return null;
    const hit = ammoQuery.data?.items.find((row) => row.id === ammoFilterId);
    if (!hit) return ammoFilterId;
    return hit.name || hit.short_name || ammoFilterId;
  }, [ammoFilterId, ammoQuery.data?.items]);

  const clearAmmoFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("ammo");
    setSearchParams(next, { replace: true });
  };

  const clearCaliberFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("caliber");
    setSearchParams(next, { replace: true });
  };

  if (gunsQuery.isLoading) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin tip="加载枪械数据…" />
      </div>
    );
  }

  if (gunsQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="枪械数据加载失败"
        description={apiError(gunsQuery.error, "枪械数据加载失败")}
      />
    );
  }

  const meta = gunsQuery.data;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Space direction="vertical" size={0}>
        <Typography.Text type="secondary">
          数据来源：{renderGunSource(meta?.source)}
        </Typography.Text>
        <Typography.Text type="secondary">
          更新时间：{formatSyncedAt(meta?.synced_at)}
          {typeof meta?.gun_count === "number"
            ? ` · 共 ${meta.gun_count} 把`
            : null}
        </Typography.Text>
      </Space>

      {ammoFilterId || caliberFilterParam ? (
        <Space wrap size={8} align="center">
          <Typography.Text type="secondary">当前筛选：</Typography.Text>
          {ammoFilterId ? (
            <Tag closable color="blue" onClose={clearAmmoFilter}>
              可用弹药：{ammoFilterLabel}
            </Tag>
          ) : null}
          {caliberFilterParam ? (
            <Tag closable color="blue" onClose={clearCaliberFilter}>
              口径：{formatCaliberLabel(caliberFilterParam)}
            </Tag>
          ) : null}
        </Space>
      ) : null}

      <Card size="small" styles={{ body: { padding: 12 } }}>
        <TarkovGunsTable
          data={items}
          ammoFilterId={ammoFilterId}
          caliberFilterParam={caliberFilterParam}
        />
      </Card>
    </Space>
  );
}
