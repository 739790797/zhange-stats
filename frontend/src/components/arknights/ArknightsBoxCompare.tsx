import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Empty, Space, Tag, Typography } from "antd";
import {
  fetchArknightsBoxCompare,
  fetchArknightsCompareCandidates,
} from "@/api/client";
import type {
  ArknightsCompareRow,
  ArknightsOwnedChar,
  ArknightsOperator,
} from "@/api/types";
import { apiError } from "@/lib/apiError";
import { COMPARE_MAX } from "./constants";
import {
  loadRoleUidByMember,
  saveRoleUidByMember,
} from "./roleUidStorage";
import { OperatorInfoCompareTemplate } from "@/components/operatorInfo/OperatorInfoCompareTemplate";
import { OwnedCard } from "./OwnedCard";
import { MissingCard } from "./MissingCard";
import { OwnedDetailTooltip } from "./OwnedDetailTooltip";
import { RowLabel } from "./RowLabel";
import { computeRarityProgress } from "./progress";
import { AddCompareMemberCard } from "@/components/operatorInfo/AddCompareMemberCard";

/** 明日方舟页：共用干员信息模板的多成员练度对比。 */
export function ArknightsBoxCompare() {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [initialized, setInitialized] = useState(false);
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
    () => candidatesQuery.data?.find((candidate) => candidate.is_self)?.member_id,
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
        (candidate) => !compareIds.includes(candidate.member_id),
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
    const selfRow = rows.find((row) => row.member_id === selfId);
    if (!selfRow) return rows;
    return [selfRow, ...rows.filter((row) => row.member_id !== selfId)];
  }, [compareQuery.data?.rows, selfId]);

  // 清理已失效的渠道服记忆（角色列表里已不存在）。
  useEffect(() => {
    if (!displayRows.length) return;
    setRoleUidByMember((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const row of displayRows) {
        const saved = next[row.member_id];
        if (!saved) continue;
        const roles = row.roles || [];
        if (roles.length > 0 && !roles.some((role) => role.uid === saved)) {
          delete next[row.member_id];
          changed = true;
        }
      }
      if (!changed) return prev;
      saveRoleUidByMember(next);
      return next;
    });
  }, [displayRows]);

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

  const memberActions = (
    <AddCompareMemberCard
      gameName="明日方舟"
      disabled={
        compareIds.length >= COMPARE_MAX || addableCandidates.length === 0
      }
      loading={candidatesQuery.isLoading}
      candidates={addableCandidates}
      onAdd={addMember}
    />
  );

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
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
        <OperatorInfoCompareTemplate<
          ArknightsOperator,
          ArknightsOwnedChar,
          ArknightsCompareRow
        >
          gameName="明日方舟"
          operators={compareQuery.data.catalog ?? []}
          rows={displayRows}
          selfId={selfId}
          catalogVersion={compareQuery.data.catalog_version}
          memberActions={memberActions}
          renderMemberLabel={(row) => (
            <RowLabel
              row={row}
              progress={
                row.status === "ok"
                  ? computeRarityProgress(row, compareQuery.data!.catalog ?? [])
                  : null
              }
              selectedUid={roleUidByMember[row.member_id]}
              canRemove={row.member_id !== selfId}
              onUidChange={(uid) => updateRoleUid(row.member_id, uid)}
              onRemove={() => removeMember(row.member_id)}
            />
          )}
          renderCard={(operator, owned, row) =>
            owned ? (
              <OwnedCard
                op={operator}
                owned={owned}
                ownerName={row.nickname}
                channelName={row.channel_name}
                roleName={row.role_name}
              />
            ) : (
              <MissingCard op={operator} />
            )
          }
          renderDetails={(operator, owned, row) =>
            owned ? (
              <OwnedDetailTooltip
                ownerName={row.nickname}
                channelName={row.channel_name}
                roleName={row.role_name}
                op={operator}
                owned={owned}
              />
            ) : (
              <Space align="start" size={16}>
                {operator.avatar_url ? (
                  <img
                    src={operator.avatar_url}
                    alt={operator.name}
                    style={{ width: 96, height: 96, objectFit: "cover" }}
                  />
                ) : null}
                <div>
                  <Space wrap>
                    <Tag>{operator.rarity}★</Tag>
                    <Tag>{operator.profession_label || operator.profession}</Tag>
                  </Space>
                  <Typography.Paragraph style={{ marginTop: 12 }}>
                    {row.nickname} 尚未拥有这名干员。
                  </Typography.Paragraph>
                </div>
              </Space>
            )
          }
        />
      ) : null}
    </Space>
  );
}
