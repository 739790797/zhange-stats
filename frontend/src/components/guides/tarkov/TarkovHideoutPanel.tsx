import { CalculatorOutlined } from "@ant-design/icons";
import { Alert, Button, Spin, Table, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovCrafts,
  fetchTarkovHideout,
  fetchTarkovHideoutLevels,
  fetchTarkovProfile,
  setTarkovHideoutLevel,
  type TarkovCraft,
  type TarkovHideoutLevel,
  type TarkovHideoutStation,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useAuthStore } from "@/stores/authStore";
import {
  TARKOV_HIDEOUT_PATH,
  tarkovMeHref,
  traderDisplayName,
  traderIconUrl,
} from "@/lib/tarkovHomeNav";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import {
  tarkovStashFloor,
  traderLevelsForHideout,
} from "@/lib/tarkovProfile";
import { formatDurationSeconds, formatMoney } from "@/lib/tarkovItemFormat";
import { TarkovGuideItemStack } from "@/components/guides/tarkov/TarkovGuideItemCell";
import { TarkovHideoutCalcModal } from "@/components/guides/tarkov/TarkovHideoutCalcModal";
import { TarkovHideoutTree } from "@/components/guides/tarkov/TarkovHideoutTree";
import {
  applyHideoutLevel,
  buildHideoutBonusTable,
  filledHideoutLevels,
  formatHideoutBonusCell,
  hideoutBonusLabel,
  hideoutDefaultLevel,
  hideoutLevelSpec,
  hideoutLevelsFromRows,
  hideoutMaxLevel,
  hideoutReqStatus,
  hideoutUpgradeItemKey,
  hideoutUpgradeMaterialItems,
  hideoutItemNeedsFleaBuy,
  hideoutUpgradeFleaCost,
  indexHideoutStations,
  isHideoutMoneyItem,
  skillReqMet,
  stationReqMet,
  traderReqMet,
  type HideoutItemReq,
  type HideoutReqStatus,
  type HideoutStationSpec,
} from "@/lib/tarkovHideoutProgress";
import { hideoutRoman } from "@/lib/tarkovHideoutTree";
import tableStyles from "./TarkovDarkTable.module.css";
import trade from "./TarkovGuideTrade.module.css";
import styles from "./TarkovHideoutPanel.module.css";

type Station = TarkovHideoutStation & HideoutStationSpec;
type Level = TarkovHideoutLevel & {
  bonuses?: Array<{
    type?: string;
    name?: string;
    value?: number;
    skill?: string;
    slot_items?: NonNullable<TarkovHideoutLevel["item_requirements"]>;
  }>;
};
type Craft = TarkovCraft;

const EMPTY_STATIONS: Station[] = [];

async function fetchStationCrafts(station: string) {
  const pageSize = 100;
  const first = await fetchTarkovCrafts({ station, page: 1, pageSize });
  const items = [...(first.items || [])];
  const total = Number(first.total || items.length);
  let page = 2;
  while (items.length < total && page <= 20) {
    const more = await fetchTarkovCrafts({ station, page, pageSize });
    const batch = more.items || [];
    if (!batch.length) break;
    items.push(...batch);
    page += 1;
  }
  return { ...first, items };
}

function statusClass(status: HideoutReqStatus): string {
  if (status === "met") return styles.met;
  if (status === "unmet") return styles.unmet;
  return styles.unset;
}

function reqCheckMark(status: HideoutReqStatus): { mark: string; label: string } {
  if (status === "met") return { mark: "√", label: "已满足" };
  if (status === "unmet") return { mark: "×", label: "未满足" };
  return { mark: "·", label: "未维护" };
}

function HideoutReqCheck({
  status,
  icon,
  wiki,
  children,
}: {
  status: HideoutReqStatus;
  icon?: ReactNode;
  wiki?: boolean;
  children: ReactNode;
}) {
  if (wiki) {
    return (
      <li className={styles.reqRow}>
        {icon}
        <span className={styles.reqText}>{children}</span>
      </li>
    );
  }
  const { mark, label } = reqCheckMark(status);
  return (
    <li className={`${styles.reqRow} ${statusClass(status)}`}>
      <span className={styles.reqMark} aria-label={label}>
        {mark}
      </span>
      {icon}
      <span className={styles.reqText}>{children}</span>
    </li>
  );
}

function HideoutReqList({
  spec,
  levels,
  byId,
  traderLevels,
  showItems = true,
  title,
  showFooter = true,
  wiki = false,
}: {
  spec: Level;
  levels: Record<string, number>;
  byId: Map<string, HideoutStationSpec>;
  traderLevels?: Record<string, number>;
  showItems?: boolean;
  title?: string;
  showFooter?: boolean;
  wiki?: boolean;
}) {
  const stations = spec.station_requirements || [];
  const traders = spec.trader_requirements || [];
  const skills = spec.skill_requirements || [];
  const items = showItems
    ? hideoutUpgradeMaterialItems(spec.item_requirements)
    : [];
  const noReqs =
    !stations.length &&
    !traders.length &&
    !skills.length &&
    !(spec.item_requirements || []).length;
  return (
    <div className={styles.reqList}>
      {title ? <div className={styles.reqTitle}>{title}</div> : null}
      {noReqs ? <div className={styles.unset}>无前置</div> : null}
      {stations.length || traders.length || skills.length ? (
        <ul className={styles.reqChecks} aria-label="升级要求">
          {stations.map((req) => {
            const other = byId.get((req.station_id || "").trim());
            const status = hideoutReqStatus(stationReqMet(req, levels, byId));
            return (
              <HideoutReqCheck
                key={`${req.station_id}-${req.level}`}
                status={status}
                wiki={wiki}
                icon={
                  other?.image_link ? <img src={other.image_link} alt="" /> : null
                }
              >
                {req.station_name || other?.name || req.station_slug} Lv.
                {req.level}
              </HideoutReqCheck>
            );
          })}
          {traders.map((req) => {
            const status = hideoutReqStatus(traderReqMet(req, traderLevels));
            const slug = req.slug || req.id || "";
            return (
              <HideoutReqCheck
                key={`${req.id}-${req.level}`}
                status={status}
                wiki={wiki}
                icon={slug ? <img src={traderIconUrl(slug)} alt="" /> : null}
              >
                {traderDisplayName(req.slug, req.name)} LL{req.level}
                {!wiki && status === "unset" ? " · 未维护" : ""}
              </HideoutReqCheck>
            );
          })}
          {skills.map((req) => {
            const status = hideoutReqStatus(skillReqMet(req, undefined));
            return (
              <HideoutReqCheck
                key={`${req.skill_id || req.skill}-${req.level}`}
                status={status}
                wiki={wiki}
              >
                {req.skill || req.skill_id} {req.level}
                {!wiki && status === "unset" ? " · 未维护" : ""}
              </HideoutReqCheck>
            );
          })}
        </ul>
      ) : null}
      {items.map((req) => {
        const ident = (req.id || "").trim();
        const label = [
          req.name || req.short_name || ident,
          req.found_in_raid ? "战局内" : "",
        ]
          .filter(Boolean)
          .join(" · ");
        const body = (
          <>
            {req.icon_link ? <img src={req.icon_link} alt="" /> : null}
            <span>
              {req.count && req.count !== 1
                ? `${isHideoutMoneyItem(req) ? Number(req.count).toLocaleString("zh-CN") : req.count}× `
                : ""}
              {label}
            </span>
          </>
        );
        if (!ident) {
          return (
            <div key={`${label}-${req.count}`} className={styles.reqRow}>
              {body}
            </div>
          );
        }
        return (
          <Link
            key={`${ident}-${req.count}-${req.found_in_raid ? "fir" : "any"}`}
            className={`${styles.reqRow} ${styles.reqItem}`}
            to={itemHrefFromTypes(ident, req.types || [])}
            onClick={(event) => event.stopPropagation()}
          >
            {body}
          </Link>
        );
      })}
      {showFooter && spec.construction_time ? (
        <div className={styles.reqNote}>
          建造 {formatDurationSeconds(spec.construction_time)}
        </div>
      ) : null}
      {showFooter && !wiki ? (
        <div className={styles.reqNote}>
          {traderLevels ? (
            "技能尚未维护，暂不计入绿灯。"
          ) : (
            <>
              商人好感在
              <Link to={tarkovMeHref("profile")}>个人资料</Link>
              维护后计入绿灯。
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

function HideoutBonusList({
  table,
  current,
  focus,
}: {
  table: ReturnType<typeof buildHideoutBonusTable>;
  current: number;
  focus: number;
}) {
  return (
    <ul className={styles.bonusList} aria-label="效果">
      {table.rows.map((row) => (
        <li key={row.key} className={styles.bonusRow}>
          <div className={styles.bonusName}>{hideoutBonusLabel(row)}</div>
          {row.slot_items?.some((item) => item.id) ? (
            <div className={styles.bonusSlots}>
              {(row.slot_items || []).map((item) => {
                const ident = (item.id || "").trim();
                if (!ident) return null;
                return (
                  <Link
                    key={ident}
                    className={styles.bonusSlot}
                    to={itemHrefFromTypes(ident, item.types || [])}
                  >
                    {item.icon_link ? <img src={item.icon_link} alt="" /> : null}
                    <span>{item.short_name || item.name || ident}</span>
                  </Link>
                );
              })}
            </div>
          ) : null}
          <ul className={styles.bonusLevels}>
            {table.levels.map((level, index) => {
              const isFocus = level === focus;
              const isBuilt = level === current;
              const mark = isFocus
                ? isBuilt
                  ? " 当前"
                  : " 选中"
                : isBuilt
                  ? " 已建"
                  : "";
              return (
                <li
                  key={level}
                  className={`${styles.bonusLv}${
                    isFocus ? ` ${styles.bonusLvNow}` : ""
                  }`}
                >
                  <span>
                    Lv.{level}
                    {mark}
                  </span>
                  <span>{formatHideoutBonusCell(row.type, row.values[index])}</span>
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ul>
  );
}

function HideoutMaterialList({ items }: { items: HideoutItemReq[] }) {
  if (!items.length) {
    return <div className={styles.detailSub}>无额外材料。</div>;
  }
  return (
    <ul className={styles.itemList} aria-label="升级材料">
      {items.map((req) => {
        const ident = (req.id || "").trim();
        const key = hideoutUpgradeItemKey(req) || `${req.name}-${req.count}`;
        const label = [
          req.name || req.short_name || ident,
          req.found_in_raid ? "战局内" : "",
        ]
          .filter(Boolean)
          .join(" · ");
        const countText =
          req.count && req.count !== 1
            ? `${isHideoutMoneyItem(req) ? Number(req.count).toLocaleString("zh-CN") : req.count}× `
            : "";
        const flea = isHideoutMoneyItem(req)
          ? formatMoney(req.count)
          : hideoutItemNeedsFleaBuy(req)
            ? formatMoney(req.flea_price)
            : "—";
        const body = (
          <>
            {req.icon_link ? <img src={req.icon_link} alt="" /> : null}
            <span className={styles.itemName}>
              {countText}
              {label}
            </span>
            <span className={styles.itemFlea}>{flea}</span>
          </>
        );
        if (!ident) {
          return (
            <li key={key} className={styles.itemRow}>
              {body}
            </li>
          );
        }
        return (
          <li key={key}>
            <Link
              className={`${styles.itemRow} ${styles.reqItem}`}
              to={itemHrefFromTypes(ident, req.types || [])}
            >
              {body}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function StationDetail({
  station,
  current,
  focusLevel,
  levels,
  byId,
  traderLevels,
  wiki = false,
}: {
  station: Station;
  current: number;
  focusLevel?: number;
  levels: Record<string, number>;
  byId: Map<string, HideoutStationSpec>;
  traderLevels?: Record<string, number>;
  wiki?: boolean;
}) {
  const gameMode = useTarkovGameMode();
  const high = hideoutMaxLevel(station);
  const selected = (() => {
    const raw = Math.trunc(Number(focusLevel) || 0);
    if (raw >= 1) return high ? Math.min(raw, high) : raw;
    return Math.max(current, 1);
  })();
  const spec = hideoutLevelSpec(station, selected) as Level | undefined;
  const roman = hideoutRoman(selected);
  const built = current >= selected;
  const craftsQuery = useQuery({
    queryKey: ["guides-tarkov-crafts", gameMode, station.slug || station.id],
    queryFn: () => fetchStationCrafts(station.slug || station.id),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: Boolean(station.slug || station.id),
  });
  const crafts = useMemo(() => {
    const rows = (craftsQuery.data?.items || []) as Craft[];
    return [...rows].sort(
      (a, b) => Number(a.level || 0) - Number(b.level || 0),
    );
  }, [craftsQuery.data]);
  const bonusTable = useMemo(() => buildHideoutBonusTable(station), [station]);
  const cost = spec ? hideoutUpgradeFleaCost(spec.item_requirements) : null;
  const materialItems = hideoutUpgradeMaterialItems(spec?.item_requirements);

  const craftColumns: ColumnsType<Craft> = [
    {
      title: "产物",
      key: "product",
      render: (_: unknown, row) => (
        <TarkovGuideItemStack items={row.product_item ? [row.product_item] : []} />
      ),
    },
    {
      title: "材料",
      key: "need",
      render: (_: unknown, row) => (
        <TarkovGuideItemStack items={row.required_items} />
      ),
    },
    {
      title: "模块",
      dataIndex: "level",
      width: 72,
      render: (level: number) => `Lv.${level}`,
    },
    {
      title: "时长",
      dataIndex: "duration",
      width: 88,
      render: (duration: number) => formatDurationSeconds(duration),
    },
  ];

  return (
    <div className={styles.detail}>
      <div className={styles.detailMain}>
        <div className={styles.detailHead}>
          {station.image_link ? (
            <img className={styles.detailIcon} src={station.image_link} alt="" />
          ) : null}
          <div>
            <h3 className={styles.detailName}>
              {station.name}
              {roman ? ` ${roman}` : ""}
            </h3>
            <div className={styles.detailSub}>
              {`Lv.${selected}`}
              {high ? ` / ${high}` : ""}
              {wiki
                ? spec?.description
                  ? ` · ${spec.description}`
                  : ""
                : `${
                    built
                      ? " · 已建成"
                      : current > 0
                        ? ` · 已建到 Lv.${current}`
                        : " · 尚未建造"
                  }${spec?.description ? ` · ${spec.description}` : ""}`}
            </div>
          </div>
        </div>

        {bonusTable.rows.length ? (
          <section>
            <h4 className={styles.sectionTitle}>效果</h4>
            <HideoutBonusList
              table={bonusTable}
              current={current}
              focus={selected}
            />
          </section>
        ) : selected > 0 ? (
          <div className={styles.detailSub}>该等级没有列出加成。</div>
        ) : null}

        {spec ? (
          <>
            <section>
              <h4 className={styles.sectionTitle}>
                {roman ? `${roman} ` : ""}建造要求
                <span className={styles.needMeta}>
                  {` · Lv.${selected}`}
                  {spec.construction_time
                    ? ` · ${formatDurationSeconds(spec.construction_time)}`
                    : ""}
                </span>
              </h4>
              <HideoutReqList
                spec={spec}
                levels={levels}
                byId={byId}
                traderLevels={traderLevels}
                showItems={false}
                showFooter={false}
                wiki={wiki}
              />
            </section>
            <section>
              <h4 className={styles.sectionTitle}>
                {roman ? `${roman} ` : ""}建造材料
                {cost != null ? (
                  <span className={styles.needMeta}>
                    {` · 跳蚤 ${formatMoney(cost)}`}
                  </span>
                ) : null}
              </h4>
              <HideoutMaterialList items={materialItems} />
            </section>
          </>
        ) : (
          <div className={styles.detailSub}>该等级没有建造数据。</div>
        )}
      </div>

      {craftsQuery.isLoading ? (
        <Spin />
      ) : crafts.length ? (
        <section>
          <h4 className={styles.sectionTitle}>制作</h4>
          <div className={styles.detailSub}>
            {wiki
              ? "本设施全部配方。"
              : "本设施全部配方；高于当前已建等级的行灰显预告。"}
          </div>
          <div className={tableStyles.table}>
            <Table<Craft>
              rowKey={(row) => row.id}
              columns={craftColumns}
              dataSource={crafts}
              pagination={false}
              size="small"
              rowClassName={
                wiki
                  ? undefined
                  : (row) =>
                      Number(row.level || 0) > current ? styles.craftLocked : ""
              }
            />
          </div>
        </section>
      ) : null}
    </div>
  );
}

export function TarkovHideoutPanel({
  stationSlug,
  wiki = false,
}: {
  stationSlug?: string;
  wiki?: boolean;
}) {
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const loggedIn = Boolean(useAuthStore((s) => s.user));
  const [searchParams, setSearchParams] = useSearchParams();
  const [calcOpen, setCalcOpen] = useState(false);
  const selectedKey =
    (stationSlug || searchParams.get("station") || "").trim();

  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-hideout", gameMode],
    queryFn: fetchTarkovHideout,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const levelsQuery = useQuery({
    queryKey: ["guides-tarkov-hideout-levels", gameMode],
    queryFn: fetchTarkovHideoutLevels,
    staleTime: 30_000,
    retry: 1,
    enabled: !wiki && loggedIn,
  });
  const profileQuery = useQuery({
    queryKey: ["guides-tarkov-profile", gameMode],
    queryFn: fetchTarkovProfile,
    staleTime: 30_000,
    retry: 1,
    enabled: !wiki && loggedIn,
  });

  const stashFloor = wiki
    ? tarkovStashFloor(undefined)
    : tarkovStashFloor(profileQuery.data?.game_edition);
  const traderLevels = wiki
    ? undefined
    : traderLevelsForHideout(profileQuery.data?.trader_levels);
  const stations = (catalogQuery.data?.items || EMPTY_STATIONS) as Station[];
  const byId = useMemo(() => indexHideoutStations(stations), [stations]);
  const levels = useMemo(
    () =>
      filledHideoutLevels(
        stations,
        hideoutLevelsFromRows(levelsQuery.data?.levels),
        stashFloor,
      ),
    [stations, levelsQuery.data, stashFloor],
  );
  const selected =
    stations.find(
      (row) => row.slug === selectedKey || row.id === selectedKey,
    ) || null;
  const selectedLevel = (() => {
    if (!selected) return undefined;
    const high = hideoutMaxLevel(selected);
    const raw = Number(searchParams.get("level") || "");
    if (Number.isFinite(raw) && raw >= 1) {
      const value = Math.trunc(raw);
      return high ? Math.min(value, high) : value;
    }
    const current =
      levels[selected.id] ?? hideoutDefaultLevel(selected, stashFloor);
    return Math.max(current, 1);
  })();

  const mutation = useMutation({
    mutationFn: ({ stationId, level }: { stationId: string; level: number }) =>
      setTarkovHideoutLevel(stationId, level),
    onSuccess: (data) => {
      queryClient.setQueryData(
        ["guides-tarkov-hideout-levels", gameMode],
        data,
      );
    },
    onError: (error) => {
      message.error(apiError(error, "藏身处等级保存失败"));
    },
  });

  const setSelected = (slug: string, level?: number) => {
    if (wiki) {
      if (!slug) {
        navigate(TARKOV_HIDEOUT_PATH, { replace: true });
        return;
      }
      const params = new URLSearchParams();
      if (level && level > 0) params.set("level", String(level));
      const query = params.toString();
      navigate(
        `${TARKOV_HIDEOUT_PATH}/${encodeURIComponent(slug)}${
          query ? `?${query}` : ""
        }`,
        { replace: true },
      );
      return;
    }
    if (stationSlug) return;
    const next = new URLSearchParams(searchParams);
    if (!slug) {
      next.delete("station");
      next.delete("level");
    } else {
      next.set("station", slug);
      if (level && level > 0) next.set("level", String(level));
      else next.delete("level");
    }
    setSearchParams(next, { replace: true });
  };

  const changeLevel = (station: HideoutStationSpec, delta: 1 | -1) => {
    const ident = (station.id || "").trim();
    if (!ident || mutation.isPending) return;
    const current = levels[ident] ?? hideoutDefaultLevel(station, stashFloor);
    const target = current + delta;
    try {
      applyHideoutLevel(stations, levels, ident, target, stashFloor);
    } catch {
      return;
    }
    mutation.mutate({ stationId: ident, level: target });
  };

  if (
    catalogQuery.isLoading ||
    (!wiki && (levelsQuery.isLoading || profileQuery.isLoading))
  ) {
    return (
      <div className={trade.status}>
        <Spin />
      </div>
    );
  }

  if (catalogQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="藏身处加载失败"
        description={apiError(catalogQuery.error, "藏身处加载失败")}
      />
    );
  }

  if (!wiki && levelsQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="藏身处进度加载失败"
        description={apiError(levelsQuery.error, "藏身处进度加载失败")}
      />
    );
  }

  return (
    <div className={trade.stack}>
      <div className={styles.toolbar}>
        {wiki ? (
          <p className={styles.wikiHint}>
            目录百科，不含个人进度。
            <Link to={tarkovMeHref("hideout")}>去个人中心规划</Link>
          </p>
        ) : (
          <span />
        )}
        <Button
          icon={<CalculatorOutlined />}
          onClick={() => setCalcOpen(true)}
        >
          材料计算
        </Button>
      </div>
      <TarkovHideoutTree
        stations={stations}
        levels={levels}
        byId={byId}
        stashFloor={stashFloor}
        selectedId={selected?.id}
        selectedLevel={selectedLevel}
        pending={mutation.isPending}
        wiki={wiki}
        onSelect={setSelected}
        onChangeLevel={wiki ? undefined : changeLevel}
      />
      {selected ? (
        <StationDetail
          station={selected}
          current={levels[selected.id] ?? hideoutDefaultLevel(selected, stashFloor)}
          focusLevel={selectedLevel}
          levels={levels}
          byId={byId}
          traderLevels={traderLevels}
          wiki={wiki}
        />
      ) : (
        <div className={styles.detailSub}>
          悬停格子可预览前置与路线；点击查看详情，再点取消选中。
        </div>
      )}
      <div className={trade.meta}>
        {catalogQuery.data?.station_count ?? stations.length} 个模块
        {catalogQuery.data?.synced_at
          ? ` · 同步 ${catalogQuery.data.synced_at}`
          : ""}
      </div>
      <TarkovHideoutCalcModal
        open={calcOpen}
        stations={stations}
        onCancel={() => setCalcOpen(false)}
      />
    </div>
  );
}
