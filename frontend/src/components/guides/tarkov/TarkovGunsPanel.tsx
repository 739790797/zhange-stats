import { useQuery } from "@tanstack/react-query";
import { Alert, Spin, Tag } from "antd";
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
import styles from "./TarkovGunsPanel.module.css";

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
    return <span>{key || "未知"}</span>;
  }
  return (
    <a href={hit.href} target="_blank" rel="noreferrer">
      {hit.label}
    </a>
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
      <div className={styles.status}>
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
    <div className={styles.stack}>
      <div className={styles.meta}>
        <div>数据来源：{renderGunSource(meta?.source)}</div>
        <div>
          更新时间：{formatSyncedAt(meta?.synced_at)}
          {typeof meta?.gun_count === "number"
            ? ` · 共 ${meta.gun_count} 把`
            : null}
        </div>
      </div>

      {ammoFilterId || caliberFilterParam ? (
        <div className={styles.filters}>
          <span className={styles.filterLabel}>当前筛选：</span>
          {ammoFilterId ? (
            <Tag closable color="orange" onClose={clearAmmoFilter}>
              可用弹药：{ammoFilterLabel}
            </Tag>
          ) : null}
          {caliberFilterParam ? (
            <Tag closable color="orange" onClose={clearCaliberFilter}>
              口径：{formatCaliberLabel(caliberFilterParam)}
            </Tag>
          ) : null}
        </div>
      ) : null}

      <div className={styles.panel}>
        <TarkovGunsTable
          data={items}
          ammoFilterId={ammoFilterId}
          caliberFilterParam={caliberFilterParam}
        />
      </div>
    </div>
  );
}
