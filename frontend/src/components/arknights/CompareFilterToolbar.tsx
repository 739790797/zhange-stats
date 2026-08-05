import { Card, Input, Select, Space } from "antd";
import type { SortMode } from "./constants";

export function CompareFilterToolbar({
  keyword,
  onKeywordChange,
  rarityFilter,
  onRarityFilterChange,
  professionFilter,
  onProfessionFilterChange,
  professions,
  sortMode,
  onSortModeChange,
}: {
  keyword: string;
  onKeywordChange: (value: string) => void;
  rarityFilter: number | "all";
  onRarityFilterChange: (value: number | "all") => void;
  professionFilter: string;
  onProfessionFilterChange: (value: string) => void;
  professions: string[];
  sortMode: SortMode;
  onSortModeChange: (value: SortMode) => void;
}) {
  return (
    <Card size="small">
      <Space wrap style={{ width: "100%" }}>
        <Input.Search
          allowClear
          placeholder="搜索干员"
          style={{ width: 160 }}
          value={keyword}
          onChange={(e) => onKeywordChange(e.target.value)}
        />
        <Select
          style={{ width: 110 }}
          value={rarityFilter}
          onChange={onRarityFilterChange}
          options={[
            { value: "all", label: "全部星级" },
            ...[6, 5, 4, 3, 2, 1].map((n) => ({
              value: n,
              label: `${n}★`,
            })),
          ]}
        />
        <Select
          style={{ width: 120 }}
          value={professionFilter}
          onChange={onProfessionFilterChange}
          options={[
            { value: "all", label: "全部职业" },
            ...professions.map((p) => ({ value: p, label: p })),
          ]}
        />
        <Select
          value={sortMode}
          style={{ width: 150 }}
          onChange={(v: SortMode) => onSortModeChange(v)}
          options={[
            { value: "catalog", label: "稀有度排序" },
            { value: "level", label: "等级（以我为准）" },
          ]}
        />
      </Space>
    </Card>
  );
}
