import { useMemo, useState, type ReactNode } from "react";
import {
  Avatar,
  Button,
  Card,
  Empty,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  OperatorInfoFilterToolbar,
  type OperatorInfoSortMode,
} from "./OperatorInfoFilterToolbar";

export type OperatorInfoBase = {
  char_id: string;
  name: string;
  rarity: number;
  profession: string;
  profession_label?: string | null;
};

export type OperatorInfoRole = {
  uid: string;
  role_name?: string | null;
  channel_name?: string | null;
};

export type OperatorInfoMemberRow<TProgress> = {
  member_id: number;
  nickname: string;
  avatar_url?: string | null;
  status: string;
  message?: string | null;
  uid?: string | null;
  role_name?: string | null;
  channel_name?: string | null;
  player_level?: number | null;
  synced_at?: string | null;
  char_count?: number;
  owned?: Record<string, TProgress>;
  roles?: OperatorInfoRole[];
};

type SelectedOperator<TOperator, TProgress, TRow> = {
  operator: TOperator;
  row: TRow;
  progress?: TProgress;
};

type Props<
  TOperator extends OperatorInfoBase,
  TProgress,
  TRow extends OperatorInfoMemberRow<TProgress>,
> = {
  gameName: string;
  operators: TOperator[];
  rows: TRow[];
  selfId?: number;
  catalogVersion?: string | null;
  cardRows?: 1 | 2;
  memberActions?: ReactNode;
  renderMemberLabel: (row: TRow) => ReactNode;
  renderCard: (
    operator: TOperator,
    progress: TProgress | undefined,
    row: TRow,
  ) => ReactNode;
  renderDetails: (
    operator: TOperator,
    progress: TProgress | undefined,
    row: TRow,
  ) => ReactNode;
};

const CARD_WIDTH = 120;
const CARD_HEIGHT = 156;
const CARD_GAP = 6;

export function OperatorInfoCompareTemplate<
  TOperator extends OperatorInfoBase,
  TProgress extends { level?: number; evolve_phase?: number },
  TRow extends OperatorInfoMemberRow<TProgress>,
>({
  gameName,
  operators,
  rows,
  selfId,
  catalogVersion,
  cardRows = 2,
  memberActions,
  renderMemberLabel,
  renderCard,
  renderDetails,
}: Props<TOperator, TProgress, TRow>) {
  const [sortMode, setSortMode] = useState<OperatorInfoSortMode>("catalog");
  const [keyword, setKeyword] = useState("");
  const [rarityFilter, setRarityFilter] = useState<number | "all">("all");
  const [professionFilter, setProfessionFilter] = useState("all");
  const [selected, setSelected] =
    useState<SelectedOperator<TOperator, TProgress, TRow> | null>(null);

  const professions = useMemo(
    () =>
      Array.from(
        new Set(
          operators
            .map((operator) => operator.profession_label || operator.profession)
            .filter(Boolean),
        ),
      ).sort(),
    [operators],
  );

  const orderedOperators = useMemo(() => {
    let result = operators.filter((operator) => {
      if (rarityFilter !== "all" && operator.rarity !== rarityFilter) return false;
      if (
        professionFilter !== "all" &&
        (operator.profession_label || operator.profession) !== professionFilter
      ) {
        return false;
      }
      const query = keyword.trim().toLocaleLowerCase();
      if (
        query &&
        !operator.name.toLocaleLowerCase().includes(query) &&
        !operator.char_id.toLocaleLowerCase().includes(query)
      ) {
        return false;
      }
      return true;
    });

    if (sortMode === "level" && rows.length > 0) {
      const ownRow = rows.find((row) => row.member_id === selfId) || rows[0];
      result = [...result].sort((left, right) => {
        const a = ownRow.owned?.[left.char_id];
        const b = ownRow.owned?.[right.char_id];
        if (!a && !b) return 0;
        if (!a) return 1;
        if (!b) return -1;
        if ((b.evolve_phase || 0) !== (a.evolve_phase || 0)) {
          return (b.evolve_phase || 0) - (a.evolve_phase || 0);
        }
        if ((b.level || 0) !== (a.level || 0)) {
          return (b.level || 0) - (a.level || 0);
        }
        return right.rarity - left.rarity || left.char_id.localeCompare(right.char_id);
      });
    }
    return result;
  }, [
    keyword,
    operators,
    professionFilter,
    rarityFilter,
    rows,
    selfId,
    sortMode,
  ]);

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <OperatorInfoFilterToolbar
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
      <Typography.Text type="secondary">
        展示 {orderedOperators.length} / {operators.length} 名干员
        {catalogVersion ? ` · 资源 ${catalogVersion}` : ""}
      </Typography.Text>
      {orderedOperators.length ? (
        <div
          style={{
            overflowX: "auto",
            overflowY: "hidden",
            WebkitOverflowScrolling: "touch",
            border: "1px solid rgba(0,0,0,0.06)",
            borderRadius: 10,
            background: "#f0f0f0",
          }}
        >
          {rows.map((row, rowIndex) => (
            <div
              key={row.member_id}
              style={{
                display: "flex",
                alignItems: "stretch",
                minHeight:
                  CARD_HEIGHT * cardRows + CARD_GAP * (cardRows - 1) + 24,
                borderBottom:
                  rowIndex === rows.length - 1
                    ? "none"
                    : "1px solid rgba(0,0,0,0.06)",
                background: rowIndex % 2 ? "#f7f7f7" : "#fafafa",
              }}
            >
              {renderMemberLabel(row)}
              <div
                style={{
                  display: "grid",
                  gridTemplateRows: `repeat(${cardRows}, ${CARD_HEIGHT}px)`,
                  gridAutoFlow: "column",
                  gridAutoColumns: CARD_WIDTH,
                  gap: CARD_GAP,
                  padding: "10px 12px",
                  alignItems: "start",
                }}
              >
                {row.status !== "ok" ? (
                  <Typography.Text
                    type="secondary"
                    style={{ padding: "0 8px", gridRow: "1 / span 2" }}
                  >
                    {row.message || "无法读取盒子"}
                  </Typography.Text>
                ) : (
                  orderedOperators.map((operator) => {
                    const progress = row.owned?.[operator.char_id];
                    return (
                      <button
                        key={operator.char_id}
                        type="button"
                        aria-label={`${row.nickname} · ${operator.name}详情`}
                        onClick={() => setSelected({ operator, progress, row })}
                        style={{
                          display: "block",
                          width: CARD_WIDTH,
                          height: CARD_HEIGHT,
                          flex: "0 0 auto",
                          cursor: "pointer",
                          padding: 0,
                          border: 0,
                          background: "transparent",
                          font: "inherit",
                          borderRadius: 4,
                          outlineOffset: 3,
                        }}
                      >
                        {renderCard(operator, progress, row)}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Card>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={`没有符合筛选的${gameName}干员`}
          />
        </Card>
      )}
      {memberActions}
      <Modal
        title={
          selected ? (
            <Space wrap>
              <span>{selected.operator.name}</span>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                {selected.row.nickname}
              </Typography.Text>
            </Space>
          ) : null
        }
        open={selected != null}
        onCancel={() => setSelected(null)}
        footer={null}
        width="min(900px, calc(100vw - 24px))"
        destroyOnClose
      >
        {selected
          ? renderDetails(selected.operator, selected.progress, selected.row)
          : null}
      </Modal>
    </Space>
  );
}

export function OperatorInfoMemberLabel<TProgress>({
  row,
  canRemove,
  onRemove,
  selectedUid,
  onUidChange,
  summary,
  showGameIdentity = false,
}: {
  row: OperatorInfoMemberRow<TProgress>;
  canRemove?: boolean;
  onRemove?: () => void;
  selectedUid?: string;
  onUidChange?: (uid: string) => void;
  summary?: ReactNode;
  showGameIdentity?: boolean;
}) {
  const roles = row.roles || [];
  const currentUid = roles.some((role) => role.uid === selectedUid)
    ? selectedUid
    : roles[0]?.uid;
  return (
    <div
      style={{
        width: 176,
        flex: "0 0 176px",
        padding: "10px 8px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 8,
        borderRight: "1px solid rgba(0,0,0,0.06)",
        background: "#fff",
        position: "sticky",
        left: 0,
        zIndex: 8,
        isolation: "isolate",
        boxShadow: "4px 0 10px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
        <Avatar src={row.avatar_url || undefined} size="small">
          {(row.nickname || "?").slice(0, 1)}
        </Avatar>
        <Typography.Text strong ellipsis style={{ flex: 1, minWidth: 0 }}>
          {row.nickname}
        </Typography.Text>
        {canRemove ? (
          <Button
            type="text"
            size="small"
            onClick={onRemove}
            aria-label="移除对比"
          >
            ×
          </Button>
        ) : null}
      </div>
      {roles.length > 0 ? (
        <Select
          size="small"
          style={{ width: "100%" }}
          value={currentUid}
          placeholder="渠道服"
          options={roles.map((role) => ({
            value: role.uid,
            label: (
              <Space size={6}>
                <Avatar src={row.avatar_url || undefined} size={22}>
                  {(row.nickname || "?").slice(0, 1)}
                </Avatar>
                <span>{role.role_name || role.uid}</span>
              </Space>
            ),
            title: `${role.role_name || role.uid} · ${role.channel_name || ""}`,
          }))}
          onChange={onUidChange}
          popupMatchSelectWidth={false}
        />
      ) : null}
      {row.status === "ok" ? (
        <>
          {showGameIdentity ? (
            <>
              {row.role_name || row.uid ? (
                <Typography.Text
                  type="secondary"
                  style={{ fontSize: 11 }}
                  ellipsis
                  title={`${row.role_name || "游戏角色"}${row.uid ? ` · UID ${row.uid}` : ""}`}
                >
                  {row.role_name || "游戏角色"}
                  {row.uid ? ` · UID ${row.uid}` : ""}
                </Typography.Text>
              ) : null}
              <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                {row.player_level != null ? `Lv.${row.player_level}` : "已绑定"}
              </Typography.Text>
            </>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
              {row.role_name || (row.player_level != null ? `Lv.${row.player_level}` : "已绑定")}
              {row.player_level != null && row.role_name ? ` · Lv.${row.player_level}` : ""}
            </Typography.Text>
          )}
          {summary}
          {row.synced_at ? (
            <Typography.Text
              type="secondary"
              style={{ fontSize: 11 }}
              title={row.synced_at}
            >
              同步于 {new Date(row.synced_at).toLocaleString("zh-CN")}
            </Typography.Text>
          ) : null}
        </>
      ) : (
        <Tag color={row.status === "unbound" ? "default" : "warning"} style={{ margin: 0 }}>
          {row.message || row.status}
        </Tag>
      )}
    </div>
  );
}
