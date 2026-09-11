import { InfoCircleOutlined } from "@ant-design/icons";
import { Image, Table, Tooltip } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { TarkovAmmoItem } from "@/api/guidesApi";
import { formatCaliberLabel } from "@/lib/tarkovAmmoCategories";
import { ammoPackDisplayUrls } from "@/lib/tarkovAmmoPack";
import { ammoDetailHref } from "@/lib/tarkovItemTypes";
import { hdPreviewUrl, transparentThumbUrl } from "@/lib/tarkovItemImages";
import {
  AMMO_COLUMN_HINTS,
  ammoTraitMarks,
  formatChancePct,
} from "@/lib/tarkovAmmoMarks";
import {
  ARMOR_EFFECT_COLORS,
  ARMOR_EFFECT_LABELS,
  armorEffectLevel,
} from "@/lib/tarkovAmmoArmorEffect";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovAmmoWikiTable.module.css";

type Props = {
  data: TarkovAmmoItem[];
  defaultAmmoId?: string;
  compact?: boolean;
  highlightedId?: string | null;
  onHoverId?: (id: string | null) => void;
};

type SortKey =
  | "damage"
  | "penetration"
  | "armor_damage"
  | "fragmentation_chance"
  | "ricochet_chance"
  | "initial_speed"
  | "accuracy_modifier"
  | "recoil_modifier"
  | "light_bleed_modifier"
  | "heavy_bleed_modifier";

const SORT_KEYS: SortKey[] = [
  "damage",
  "penetration",
  "armor_damage",
  "fragmentation_chance",
  "ricochet_chance",
  "initial_speed",
  "accuracy_modifier",
  "recoil_modifier",
  "light_bleed_modifier",
  "heavy_bleed_modifier",
];

function HeaderHint({
  label,
  hint,
  showIcon = true,
}: {
  label: string;
  hint: string;
  showIcon?: boolean;
}) {
  return (
    <Tooltip title={hint} mouseEnterDelay={0.12}>
      <span className={styles.colHint}>
        {label}
        {showIcon ? <InfoCircleOutlined className={styles.colHintIcon} /> : null}
      </span>
    </Tooltip>
  );
}

function formatModifierPct(value: number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "0%";
  const pct = Math.round(n * 1000) / 10;
  const text = Number.isInteger(pct) ? String(pct) : pct.toFixed(1);
  return pct > 0 ? `+${text}%` : `${text}%`;
}

function renderModifierPct(value: number | null | undefined) {
  const n = Number(value);
  const text = formatModifierPct(n);
  if (!Number.isFinite(n) || n === 0) {
    return <span style={{ color: "#8a8a8a" }}>{text}</span>;
  }
  return text;
}

function renderChancePct(value: number | null | undefined) {
  const n = Number(value);
  const text = formatChancePct(n);
  if (!Number.isFinite(n) || n <= 0) {
    return <span style={{ color: "#8a8a8a" }}>{text}</span>;
  }
  return text;
}

/** polarity: "accuracy" 增绿减红；"recoil" 增红减绿 */
function renderSignedModifier(
  value: number | null | undefined,
  polarity: "accuracy" | "recoil",
) {
  const n = Number(value);
  const text = formatModifierPct(n);
  if (!Number.isFinite(n) || n === 0) {
    return <span style={{ color: "#8a8a8a" }}>{text}</span>;
  }
  const positiveIsGood = polarity === "accuracy";
  const good = positiveIsGood ? n > 0 : n < 0;
  return (
    <span style={{ color: good ? "#8bc34a" : "#e07070", fontWeight: 600 }}>
      {text}
    </span>
  );
}

function formatInitialSpeed(value: number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return "—";
  return String(Math.round(n));
}

function ArmorEffectStrip({ row }: { row: TarkovAmmoItem }) {
  return (
    <div className={styles.armorStrip}>
      {[1, 2, 3, 4, 5, 6].map((armorClass) => {
        const level = armorEffectLevel(
          row.penetration,
          armorClass,
          row.armor_damage,
        );
        const { bg, fg } = ARMOR_EFFECT_COLORS[level];
        return (
          <span
            key={armorClass}
            className={styles.armorBox}
            title={ARMOR_EFFECT_LABELS[level]}
            style={{ background: bg, color: fg }}
          >
            {ARMOR_EFFECT_LABELS[level]}
          </span>
        );
      })}
    </div>
  );
}

function AmmoThumb({
  src,
  hd,
  size,
}: {
  src: string;
  hd: string;
  size: number;
}) {
  return (
    <Image
      src={src}
      alt=""
      width={size}
      height={size}
      preview={{ src: hd, mask: false }}
      onClick={(e) => e.stopPropagation()}
      className={styles.thumb}
      style={{
        objectFit: "contain",
        cursor: "zoom-in",
      }}
    />
  );
}

function AmmoTraitMarks({ row }: { row: TarkovAmmoItem }) {
  const marks = ammoTraitMarks(row);
  if (!marks.length) return null;
  return (
    <span className={styles.traitMarks}>
      {marks.map((mark) => (
        <Tooltip key={mark.key} title={mark.hint} mouseEnterDelay={0.08}>
          <sup className={styles.traitMark}>{mark.key}</sup>
        </Tooltip>
      ))}
    </span>
  );
}

function buildCaliberRowSpan(rows: TarkovAmmoItem[]): Map<string, number> {
  const map = new Map<string, number>();
  let i = 0;
  while (i < rows.length) {
    let j = i + 1;
    while (j < rows.length && rows[j].caliber === rows[i].caliber) j += 1;
    map.set(rows[i].id, j - i);
    for (let k = i + 1; k < j; k += 1) map.set(rows[k].id, 0);
    i = j;
  }
  return map;
}

export function TarkovAmmoWikiTable({
  data,
  defaultAmmoId,
  compact = false,
  highlightedId,
  onHoverId,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("penetration");
  const [sortOrder, setSortOrder] = useState<"ascend" | "descend">("ascend");
  const defaultId = (defaultAmmoId || "").trim();
  const hoverId = (highlightedId || "").trim();
  const w = {
    caliber: 80,
    name: 168,
    num: 80,
    pack: 40,
    armor: 36,
    icon: 28,
    packIcon: 28,
  };

  const rows = useMemo(() => {
    return [...data].sort((a, b) => {
      const byCaliber = formatCaliberLabel(a.caliber).localeCompare(
        formatCaliberLabel(b.caliber),
        "zh",
        { numeric: true, sensitivity: "base" },
      );
      if (byCaliber !== 0) return byCaliber;
      const delta = a[sortKey] - b[sortKey];
      return sortOrder === "ascend" ? delta : -delta;
    });
  }, [data, sortKey, sortOrder]);

  const caliberRowSpan = useMemo(() => buildCaliberRowSpan(rows), [rows]);

  const statCol = {
    width: w.num,
    align: "left" as const,
    onHeaderCell: () => ({ className: styles.statTh }),
    onCell: () => ({ className: styles.statTd }),
  };

  const onTableChange: TableProps<TarkovAmmoItem>["onChange"] = (
    _pagination,
    _filters,
    sorter,
  ) => {
    const s = Array.isArray(sorter) ? sorter[0] : sorter;
    const key = s?.columnKey;
    if (SORT_KEYS.includes(key as SortKey)) {
      if (s?.order) {
        setSortKey(key as SortKey);
        setSortOrder(s.order);
      } else {
        setSortKey("penetration");
        setSortOrder("ascend");
      }
    }
  };

  const columns: ColumnsType<TarkovAmmoItem> = [
    {
      title: <HeaderHint label="口径" hint={AMMO_COLUMN_HINTS.caliber} />,
      dataIndex: "caliber",
      key: "caliber",
      width: w.caliber,
      onCell: (row) => ({
        rowSpan: caliberRowSpan.get(row.id) ?? 1,
        style: {
          verticalAlign: "middle",
          textAlign: "left",
          fontWeight: 600,
        },
      }),
      render: (caliber: string) => {
        const label = formatCaliberLabel(caliber);
        const raw = (caliber || "").trim();
        if (!raw) return label;
        return (
          <Link
            to={`/guides/tarkov/items/guns?caliber=${encodeURIComponent(raw)}`}
            title={`查看可用 ${label} 的枪械`}
            onClick={(e) => e.stopPropagation()}
          >
            {label}
          </Link>
        );
      },
    },
    {
      title: <HeaderHint label="名称" hint={AMMO_COLUMN_HINTS.name} />,
      dataIndex: "name",
      key: "name",
      ellipsis: true,
      width: w.name,
      render: (_: unknown, row) => {
        const label = row.name || row.short_name || row.id;
        const thumb = transparentThumbUrl(row.icon_link);
        const hd = hdPreviewUrl(row.icon_link) || thumb;
        return (
          <span className={styles.nameCell}>
            {thumb ? (
              <AmmoThumb src={thumb} hd={hd} size={w.icon} />
            ) : (
              <span className={styles.thumb} />
            )}
            <Link
              to={ammoDetailHref(row.id)}
              title="查看弹药详情"
              onClick={(e) => e.stopPropagation()}
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                minWidth: 0,
              }}
            >
              {label}
            </Link>
            <AmmoTraitMarks row={row} />
            {defaultId && row.id === defaultId ? (
              <span className={styles.defaultBadge}>默认</span>
            ) : null}
          </span>
        );
      },
    },
    {
      title: <HeaderHint label="弹药包" hint={AMMO_COLUMN_HINTS.pack} />,
      key: "pack",
      width: w.pack,
      align: "center",
      render: (_: unknown, row) => {
        const { thumb, hd } = ammoPackDisplayUrls(row);
        if (!thumb) {
          return (
            <span title="没有对应的弹药包" style={{ color: "#8a8a8a" }}>
              —
            </span>
          );
        }
        return (
          <span title="弹药包形态">
            <AmmoThumb src={thumb} hd={hd} size={w.packIcon} />
          </span>
        );
      },
    },
    {
      title: <HeaderHint label="伤害" hint={AMMO_COLUMN_HINTS.damage} />,
      dataIndex: "damage",
      key: "damage",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "damage" ? sortOrder : null,
    },
    {
      title: <HeaderHint label="穿透" hint={AMMO_COLUMN_HINTS.penetration} />,
      dataIndex: "penetration",
      key: "penetration",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "penetration" ? sortOrder : null,
    },
    {
      title: (
        <HeaderHint label="护甲伤害" hint={AMMO_COLUMN_HINTS.armorDamage} />
      ),
      dataIndex: "armor_damage",
      key: "armor_damage",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "armor_damage" ? sortOrder : null,
    },
    {
      title: (
        <HeaderHint label="碎弹%" hint={AMMO_COLUMN_HINTS.fragmentation} />
      ),
      dataIndex: "fragmentation_chance",
      key: "fragmentation_chance",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "fragmentation_chance" ? sortOrder : null,
      render: (v: number) => renderChancePct(v),
    },
    {
      title: <HeaderHint label="跳弹%" hint={AMMO_COLUMN_HINTS.ricochet} />,
      dataIndex: "ricochet_chance",
      key: "ricochet_chance",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "ricochet_chance" ? sortOrder : null,
      render: (v: number) => renderChancePct(v),
    },
    {
      title: <HeaderHint label="精度%" hint={AMMO_COLUMN_HINTS.accuracy} />,
      dataIndex: "accuracy_modifier",
      key: "accuracy_modifier",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "accuracy_modifier" ? sortOrder : null,
      render: (v: number) => renderSignedModifier(v, "accuracy"),
    },
    {
      title: <HeaderHint label="后坐力" hint={AMMO_COLUMN_HINTS.recoil} />,
      dataIndex: "recoil_modifier",
      key: "recoil_modifier",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "recoil_modifier" ? sortOrder : null,
      render: (v: number) => renderSignedModifier(v, "recoil"),
    },
    {
      title: <HeaderHint label="小出血" hint={AMMO_COLUMN_HINTS.lightBleed} />,
      dataIndex: "light_bleed_modifier",
      key: "light_bleed_modifier",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "light_bleed_modifier" ? sortOrder : null,
      render: (v: number) => renderModifierPct(v),
    },
    {
      title: <HeaderHint label="大出血" hint={AMMO_COLUMN_HINTS.heavyBleed} />,
      dataIndex: "heavy_bleed_modifier",
      key: "heavy_bleed_modifier",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "heavy_bleed_modifier" ? sortOrder : null,
      render: (v: number) => renderModifierPct(v),
    },
    {
      title: <HeaderHint label="M/S" hint={AMMO_COLUMN_HINTS.speed} />,
      dataIndex: "initial_speed",
      key: "initial_speed",
      ...statCol,
      sorter: true,
      sortOrder: sortKey === "initial_speed" ? sortOrder : null,
      render: (v: number) => formatInitialSpeed(v),
    },
    {
      title: (
        <div className={styles.armorHead}>
          <HeaderHint
            label={compact ? "对甲效果" : "对护甲效果（估）"}
            hint={AMMO_COLUMN_HINTS.armorEffect}
          />
          <div className={styles.armorHeadNums}>
            {[1, 2, 3, 4, 5, 6].map((armorClass) => (
              <Tooltip
                key={armorClass}
                title={`${armorClass} 级护甲。${AMMO_COLUMN_HINTS.armorClass}`}
                mouseEnterDelay={0.12}
              >
                <span className={styles.armorHeadNum}>{armorClass}</span>
              </Tooltip>
            ))}
          </div>
        </div>
      ),
      key: "armor_effect",
      width: w.armor * 6,
      align: "center",
      onHeaderCell: () => ({ className: styles.armorTh }),
      onCell: () => ({ className: styles.armorTd }),
      render: (_: unknown, row: TarkovAmmoItem) => (
        <ArmorEffectStrip row={row} />
      ),
    },
  ];

  const hiddenKeys = compact
    ? new Set(["caliber", "fragmentation_chance", "ricochet_chance"])
    : new Set<string>();
  const visibleColumns = columns.filter(
    (col) => !hiddenKeys.has(String(col.key ?? "")),
  );

  return (
    <Table<TarkovAmmoItem>
      className={`${tableStyles.table} ${styles.wiki} ${compact ? styles.compact : ""}`}
      size="small"
      rowKey="id"
      columns={visibleColumns}
      dataSource={rows}
      pagination={{
        pageSize: 50,
        showSizeChanger: true,
        pageSizeOptions: ["20", "50", "100"],
      }}
      tableLayout="fixed"
      showSorterTooltip={false}
      locale={{ emptyText: "当前筛选下无弹药" }}
      onChange={onTableChange}
      onRow={
        onHoverId
          ? (row) => ({
              onMouseEnter: () => onHoverId(row.id),
              onMouseLeave: () => onHoverId(null),
            })
          : undefined
      }
      rowClassName={(row) =>
        hoverId && row.id === hoverId ? styles.hoverRow : ""
      }
    />
  );
}
