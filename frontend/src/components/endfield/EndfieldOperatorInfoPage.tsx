import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Empty, Space, Tag, Typography, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import {
  fetchEndfieldBox,
  fetchEndfieldBoxCompare,
  fetchEndfieldCompareCandidates,
} from "@/api/client";
import type {
  EndfieldChar,
  EndfieldCompareRow,
  EndfieldOperator,
} from "@/api/types";
import { apiError } from "@/lib/apiError";
import {
  AddCompareMemberCard,
  type OperatorCompareCandidate,
} from "@/components/operatorInfo/AddCompareMemberCard";
import { OPERATOR_COMPARE_MAX } from "@/components/operatorInfo/constants";
import {
  OperatorInfoCompareTemplate,
  OperatorInfoMemberLabel,
} from "@/components/operatorInfo/OperatorInfoCompareTemplate";
import { formatOwnTs } from "./helpers";
import { RARITY_COLOR } from "./constants";

const ROLE_UID_STORAGE_KEY = "zhange.endfield.roleUidByMember";

function loadRoleUidByMember(): Record<number, string> {
  try {
    const raw = localStorage.getItem(ROLE_UID_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const result: Record<number, string> = {};
    for (const [key, value] of Object.entries(parsed)) {
      const memberId = Number(key);
      if (Number.isSafeInteger(memberId) && typeof value === "string" && value.trim()) {
        result[memberId] = value.trim();
      }
    }
    return result;
  } catch {
    return {};
  }
}

function saveRoleUidByMember(value: Record<number, string>) {
  try {
    localStorage.setItem(ROLE_UID_STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Ignore disabled storage and quota limits.
  }
}

function EndfieldCharacterCard({
  operator,
  progress,
}: {
  operator: EndfieldOperator;
  progress?: EndfieldChar;
}) {
  const [failedImageUrls, setFailedImageUrls] = useState<Set<string>>(
    () => new Set(),
  );
  const accent = RARITY_COLOR[operator.rarity] || "#8a9099";
  const imageUrls = [
    progress?.avatar_url,
    progress?.illustration_url,
    `/endfield/inn/chefs/${operator.char_id}.png`,
  ].filter((url): url is string => Boolean(url));
  const imageUrl = imageUrls.find((url) => !failedImageUrls.has(url));

  return (
    <div
      style={{
        width: 120,
        height: 156,
        position: "relative",
        overflow: "hidden",
        background: "#1c1c1c",
        boxShadow: `inset 0 0 0 1.5px ${accent}`,
      }}
    >
      {imageUrl ? (
        <img
          src={imageUrl}
          alt={operator.name}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() =>
            setFailedImageUrls((previous) => new Set(previous).add(imageUrl))
          }
          style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center top" }}
        />
      ) : (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "grid",
            placeItems: "center",
            color: "#ddd",
            background: `linear-gradient(160deg, ${accent}66, #202020 68%)`,
            fontSize: 30,
            fontWeight: 700,
          }}
        >
          {operator.name.slice(0, 1)}
        </div>
      )}
      <div
        style={{
          position: "absolute",
          inset: "40% 0 0",
          background: "linear-gradient(180deg, transparent, rgba(0,0,0,0.9))",
          pointerEvents: "none",
        }}
      />
      <Typography.Text
        style={{
          position: "absolute",
          top: 5,
          left: 6,
          color: "#fff",
          fontSize: 12,
          textShadow: "0 1px 3px #000",
        }}
      >
        {"★".repeat(Math.max(1, Math.min(6, operator.rarity)))}
      </Typography.Text>
      <div
        style={{
          position: "absolute",
          left: 6,
          right: 6,
          bottom: 6,
          display: "flex",
          flexDirection: "column",
          gap: 3,
          textAlign: "right",
          color: "#fff",
          textShadow: "0 1px 3px #000",
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {operator.name}
        </span>
        <span style={{ fontSize: 11, opacity: 0.9 }}>
          {progress ? `Lv.${progress.level} · 精英${progress.evolve_phase}` : "未持有"}
        </span>
      </div>
      {!progress ? (
        <Tag
          style={{ position: "absolute", top: 4, right: 4, margin: 0, fontSize: 10 }}
        >
          未持有
        </Tag>
      ) : null}
    </div>
  );
}

function EndfieldOperatorDetails({
  operator,
  progress,
  ownerName,
}: {
  operator: EndfieldOperator;
  progress?: EndfieldChar;
  ownerName: string;
}) {
  const image = progress?.illustration_url || progress?.avatar_url;
  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(120px, 220px) minmax(0, 1fr)",
          gap: 20,
          alignItems: "start",
        }}
      >
        {image ? (
          <img
            src={image}
            alt={operator.name}
            referrerPolicy="no-referrer"
            style={{ width: "100%", maxHeight: 300, objectFit: "contain", borderRadius: 8 }}
          />
        ) : (
          <div
            style={{
              minHeight: 150,
              display: "grid",
              placeItems: "center",
              borderRadius: 8,
              color: "#fff",
              fontSize: 30,
              background: `linear-gradient(160deg, ${RARITY_COLOR[operator.rarity] || "#8a9099"}66, #202020)`,
            }}
          >
            {operator.name}
          </div>
        )}
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          <Space wrap>
            <Tag color={RARITY_COLOR[operator.rarity] || "default"}>{operator.rarity}★</Tag>
            <Tag>{operator.profession_label || operator.profession}</Tag>
            {progress?.property_name ? <Tag>{progress.property_name}</Tag> : null}
            {progress?.weapon_type ? <Tag>{progress.weapon_type}</Tag> : null}
          </Space>
          {progress ? (
            <Typography.Text>
              Lv.{progress.level} · 精英{progress.evolve_phase} · 潜能{progress.potential_level}
              {formatOwnTs(progress.own_ts) ? ` · 获得 ${formatOwnTs(progress.own_ts)}` : ""}
            </Typography.Text>
          ) : (
            <Alert
              type="info"
              showIcon
              message={`${ownerName}尚未拥有这名干员`}
              description="可查看图鉴信息；养成、武器与技能数据以森空岛已同步信息为准。"
            />
          )}
        </Space>
      </div>
      {progress ? (
        <>
          {progress.weapon ? (
            <Card size="small" title="武器">
              <Space wrap>
                {progress.weapon.icon_url ? (
                  <img
                    src={progress.weapon.icon_url}
                    alt={progress.weapon.name}
                    width={56}
                    height={56}
                    style={{ objectFit: "contain" }}
                    referrerPolicy="no-referrer"
                  />
                ) : null}
                <Typography.Text>
                  {progress.weapon.name} · {progress.weapon.rarity}★ · Lv.{progress.weapon.level}
                  {progress.weapon.refine_level ? ` · 精锻${progress.weapon.refine_level}` : ""}
                </Typography.Text>
              </Space>
            </Card>
          ) : null}
          {progress.skills?.length ? (
            <Card size="small" title="技能">
              <Space wrap size={[8, 8]}>
                {progress.skills.map((skill) => (
                  <Tag key={skill.skill_id}>
                    {skill.name} · Lv.{skill.level}/{skill.max_level}
                  </Tag>
                ))}
              </Space>
            </Card>
          ) : null}
          {progress.equips?.length ? (
            <Card size="small" title="装备">
              <Space wrap size={[12, 12]}>
                {progress.equips.map((equip) => (
                  <Space key={equip.slot} size={6}>
                    {equip.icon_url ? (
                      <img
                        src={equip.icon_url}
                        alt={equip.name}
                        width={42}
                        height={42}
                        style={{ objectFit: "contain" }}
                        referrerPolicy="no-referrer"
                      />
                    ) : null}
                    <span>{equip.name}</span>
                  </Space>
                ))}
              </Space>
            </Card>
          ) : null}
        </>
      ) : null}
    </Space>
  );
}

export function EndfieldOperatorInfoPage({ enabled }: { enabled: boolean }) {
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [initialized, setInitialized] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [roleUidByMember, setRoleUidByMember] =
    useState<Record<number, string>>(loadRoleUidByMember);

  const candidatesQuery = useQuery({
    queryKey: ["endfield-compare-candidates"],
    queryFn: fetchEndfieldCompareCandidates,
    enabled,
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
  }, [initialized, selfId]);

  const compareIds = useMemo(() => {
    const ids = selectedIds.slice(0, OPERATOR_COMPARE_MAX);
    if (selfId == null || !ids.includes(selfId)) return ids;
    return [selfId, ...ids.filter((id) => id !== selfId)];
  }, [selectedIds, selfId]);

  const candidates = useMemo(
    () =>
      (candidatesQuery.data || []).filter(
        (candidate) => !compareIds.includes(candidate.member_id),
      ),
    [candidatesQuery.data, compareIds],
  );

  const roleUids = useMemo(() => {
    const selected: Record<number, string> = {};
    for (const memberId of compareIds) {
      if (roleUidByMember[memberId]) selected[memberId] = roleUidByMember[memberId];
    }
    return selected;
  }, [compareIds, roleUidByMember]);

  const roleUidKey = useMemo(
    () =>
      Object.entries(roleUids)
        .map(([memberId, uid]) => `${memberId}:${uid}`)
        .sort()
        .join(","),
    [roleUids],
  );

  const compareQuery = useQuery({
    queryKey: ["endfield-box-compare", compareIds.join(","), roleUidKey],
    queryFn: () => fetchEndfieldBoxCompare(compareIds, roleUids),
    enabled: enabled && compareIds.length > 0,
    retry: false,
  });

  const displayRows = useMemo(() => {
    const rows = compareQuery.data?.rows || [];
    if (selfId == null) return rows;
    const selfRow = rows.find((row) => row.member_id === selfId);
    return selfRow
      ? [selfRow, ...rows.filter((row) => row.member_id !== selfId)]
      : rows;
  }, [compareQuery.data?.rows, selfId]);

  useEffect(() => {
    if (!displayRows.length) return;
    setRoleUidByMember((previous) => {
      const next = { ...previous };
      let changed = false;
      for (const row of displayRows) {
        const saved = next[row.member_id];
        if (saved && row.roles?.length && !row.roles.some((role) => role.uid === saved)) {
          delete next[row.member_id];
          changed = true;
        }
      }
      if (changed) saveRoleUidByMember(next);
      return changed ? next : previous;
    });
  }, [displayRows]);

  const updateRoleUid = (memberId: number, uid: string) => {
    setRoleUidByMember((previous) => {
      const next = { ...previous, [memberId]: uid };
      saveRoleUidByMember(next);
      return next;
    });
  };

  const addMember = (memberId: number) => {
    setSelectedIds((previous) => {
      if (previous.includes(memberId) || previous.length >= OPERATOR_COMPARE_MAX) return previous;
      if (selfId != null && previous.includes(selfId)) {
        return [selfId, ...previous.filter((id) => id !== selfId), memberId].slice(0, OPERATOR_COMPARE_MAX);
      }
      return [...previous, memberId].slice(0, OPERATOR_COMPARE_MAX);
    });
  };

  const removeMember = (memberId: number) => {
    if (memberId === selfId) return;
    setSelectedIds((previous) => previous.filter((id) => id !== memberId));
  };

  const refreshSelf = async () => {
    if (selfId == null) return;
    setRefreshing(true);
    try {
      await fetchEndfieldBox(roleUidByMember[selfId], true);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["endfield-box-compare"] }),
        queryClient.invalidateQueries({ queryKey: ["endfield-compare-candidates"] }),
      ]);
      message.success("已同步终末地干员信息");
    } catch (error: unknown) {
      message.error(apiError(error, "同步失败"));
    } finally {
      setRefreshing(false);
    }
  };

  if (!enabled) {
    return (
      <Alert
        type="info"
        showIcon
        message="绑定森空岛后可查看终末地干员信息"
        description="干员图鉴来自本站同步的 EndfieldData；拥有情况和练度需要读取已绑定角色的数据。"
      />
    );
  }

  if (candidatesQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="无法加载可选成员"
        description={apiError(candidatesQuery.error, "请稍后重试")}
      />
    );
  }
  if (!candidatesQuery.data || (selectedIds.length === 0 && selfId == null)) {
    return <Card loading />;
  }
  if (compareQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="无法加载终末地干员信息"
        description={apiError(compareQuery.error, "请检查上游数据同步任务后重试")}
      />
    );
  }
  if (compareQuery.isLoading || !compareQuery.data) return <Card loading />;
  const catalog = compareQuery.data.catalog ?? [];
  if (!catalog.length) {
    return <Empty description="暂无终末地干员图鉴数据" />;
  }

  const memberActions = (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Button
        block
        icon={<ReloadOutlined />}
        loading={refreshing}
        onClick={() => void refreshSelf()}
      >
        同步我的干员练度
      </Button>
      <AddCompareMemberCard
        gameName="终末地"
        disabled={
          compareIds.length >= OPERATOR_COMPARE_MAX || candidates.length === 0
        }
        loading={candidatesQuery.isLoading}
        candidates={candidates as OperatorCompareCandidate[]}
        onAdd={addMember}
      />
    </Space>
  );

  return (
    <OperatorInfoCompareTemplate<
      EndfieldOperator,
      EndfieldChar,
      EndfieldCompareRow
    >
      gameName="终末地"
      operators={catalog}
      rows={displayRows}
      selfId={selfId}
      cardRows={1}
      memberActions={memberActions}
      renderMemberLabel={(row) => (
        <OperatorInfoMemberLabel
          row={row}
          canRemove={row.member_id !== selfId}
          onRemove={() => removeMember(row.member_id)}
          showGameIdentity
          selectedUid={roleUidByMember[row.member_id]}
          onUidChange={(uid) => updateRoleUid(row.member_id, uid)}
          summary={
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              已拥有 {Object.keys(row.owned || {}).length} / {compareQuery.data.catalog_count ?? catalog.length} 名
            </Typography.Text>
          }
        />
      )}
      renderCard={(operator, progress) => (
        <EndfieldCharacterCard operator={operator} progress={progress} />
      )}
      renderDetails={(operator, progress, row) => (
        <EndfieldOperatorDetails
          operator={operator}
          progress={progress}
          ownerName={row.nickname}
        />
      )}
    />
  );
}
