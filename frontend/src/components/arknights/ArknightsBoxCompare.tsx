import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Empty, Space, Typography } from "antd";
import {
  fetchArknightsBoxCompare,
  fetchArknightsCompareCandidates,
} from "@/api/client";
import { apiError } from "@/lib/apiError";
import { AddCompareCard } from "./AddCompareCard";
import { CompareFilterToolbar } from "./CompareFilterToolbar";
import { COMPARE_MAX, type SortMode } from "./constants";
import {
  loadRoleUidByMember,
  saveRoleUidByMember,
} from "./roleUidStorage";
import { SyncCompareBoard } from "./SyncCompareBoard";

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

    if (sortMode !== "level" || !compareQuery.data?.rows?.length) {
      return catalog;
    }
    const rows = compareQuery.data.rows;
    const keyRow =
      rows.find((r) => r.member_id === selfId) || rows[0];
    const ownedMap = keyRow.owned ?? {};
    return [...catalog].sort((a, b) => {
      const oa = ownedMap[a.char_id];
      const ob = ownedMap[b.char_id];
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
      <CompareFilterToolbar
        keyword={keyword}
        onKeywordChange={setKeyword}
        rarityFilter={rarityFilter}
        onRarityFilterChange={setRarityFilter}
        professionFilter={professionFilter}
        onProfessionFilterChange={setProfessionFilter}
        professions={professions}
        sortMode={sortMode}
        onSortModeChange={setSortMode}
      />

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
            展示 {orderedOps.length} / {(compareQuery.data.catalog ?? []).length} 名干员
            {compareQuery.data.catalog_version
              ? ` · 资源 ${compareQuery.data.catalog_version}`
              : ""}
          </Typography.Text>
          {orderedOps.length ? (
            <SyncCompareBoard
              rows={displayRows}
              orderedOps={orderedOps}
              catalog={compareQuery.data.catalog ?? []}
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
