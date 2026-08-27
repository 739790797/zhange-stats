import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Spin, Tag, Tooltip } from "antd";
import { CheckSquareOutlined, ClearOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchTarkovAmmo, type TarkovAmmoItem } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  AMMO_TYPE_ORDER,
  formatAmmoTypeLabel,
  formatCaliberLabel,
} from "@/lib/tarkovAmmoCategories";
import {
  loadTarkovAmmoFilters,
  resolveCaliberSelection,
  saveTarkovAmmoFilters,
} from "@/lib/tarkovAmmoFilterStorage";
import { TarkovAmmoWikiTable } from "@/components/guides/tarkov/TarkovAmmoWikiTable";
import { TarkovAmmoScatterChart } from "@/components/guides/tarkov/TarkovAmmoScatterChart";
import { ammoScatterAxisMax, distinctCaliberColor } from "@/lib/tarkovAmmoScatter";
import styles from "./TarkovAmmoScatterPanel.module.css";

const EMPTY_ITEMS: TarkovAmmoItem[] = [];

function compareCaliberLabel(a: string, b: string): number {
  return formatCaliberLabel(a).localeCompare(formatCaliberLabel(b), "zh", {
    numeric: true,
    sensitivity: "base",
  });
}

export function TarkovAmmoScatterPanel() {
  const gameMode = useTarkovGameMode();
  const navigate = useNavigate();
  const ammoQuery = useQuery({
    queryKey: ["guides-tarkov-ammo", gameMode],
    queryFn: fetchTarkovAmmo,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const goGunsForAmmo = useCallback(
    (ammo: TarkovAmmoItem) => {
      const id = (ammo.id || "").trim();
      if (!id) return;
      navigate(`/guides/tarkov/items/guns?ammo=${encodeURIComponent(id)}`);
    },
    [navigate],
  );

  const items = ammoQuery.data?.items ?? EMPTY_ITEMS;
  const allCalibers = useMemo(
    () =>
      Array.from(new Set(items.map((row) => row.caliber))).sort(
        compareCaliberLabel,
      ),
    [items],
  );

  const [savedSelection, setSavedSelection] = useState<string[] | null>(
    () => loadTarkovAmmoFilters().selectedCalibers,
  );
  const [selectedCalibers, setSelectedCalibers] = useState<string[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!allCalibers.length) return;
    const next = resolveCaliberSelection(allCalibers, savedSelection);
    setSelectedCalibers(next);
    setReady(true);
  }, [allCalibers, savedSelection]);

  const selectedSet = useMemo(
    () => new Set(selectedCalibers),
    [selectedCalibers],
  );

  const persistSelection = (next: string[]) => {
    setSelectedCalibers(next);
    setSavedSelection(next);
    saveTarkovAmmoFilters({ selectedCalibers: next });
  };

  const typeRows = useMemo(() => {
    const byType = new Map<string, Set<string>>();
    for (const row of items) {
      const t = (row.ammo_type || "").trim() || "";
      if (!byType.has(t)) byType.set(t, new Set());
      byType.get(t)!.add(row.caliber);
    }
    const known = AMMO_TYPE_ORDER.filter((t) => byType.has(t));
    const knownSet = new Set<string>(known);
    const extra = Array.from(byType.keys())
      .filter((t) => !knownSet.has(t))
      .sort((a, b) =>
        formatAmmoTypeLabel(a).localeCompare(formatAmmoTypeLabel(b), "zh"),
      );
    return [...known, ...extra].map((id) => ({
      id: id || "unknown",
      label: formatAmmoTypeLabel(id),
      calibers: Array.from(byType.get(id) || []).sort(compareCaliberLabel),
    }));
  }, [items]);

  const toggleCaliber = (caliber: string) => {
    const next = new Set(selectedSet);
    if (next.has(caliber)) next.delete(caliber);
    else next.add(caliber);
    persistSelection(allCalibers.filter((c) => next.has(c)));
  };

  const toggleCategory = (calibers: string[], selectAll: boolean) => {
    const next = new Set(selectedSet);
    for (const c of calibers) {
      if (selectAll) next.add(c);
      else next.delete(c);
    }
    persistSelection(allCalibers.filter((c) => next.has(c)));
  };

  const caliberColors = useMemo(() => {
    const map = new Map<string, string>();
    allCalibers.forEach((c, i) => {
      map.set(c, distinctCaliberColor(i));
    });
    return map;
  }, [allCalibers]);

  const data = useMemo(() => {
    return items.filter((row) => selectedSet.has(row.caliber));
  }, [items, selectedSet]);

  const axisMax = useMemo(() => ammoScatterAxisMax(items), [items]);

  if (ammoQuery.isLoading || !ready) {
    return (
      <div className={styles.status}>
        <Spin tip="加载弹药数据…" />
      </div>
    );
  }

  if (ammoQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="弹药数据加载失败"
        description={apiError(ammoQuery.error, "弹药数据加载失败")}
      />
    );
  }

  return (
    <div className={styles.stack}>
      <div className={styles.filterPanel}>
        {typeRows.length ? (
          typeRows.map((row) => {
            const selectedInRow = row.calibers.filter((c) =>
              selectedSet.has(c),
            ).length;
            const allOn = selectedInRow === row.calibers.length;
            return (
              <div key={row.id} className={styles.filterRow}>
                <div className={styles.filterLabel}>{row.label}</div>
                <div className={styles.filterChips}>
                  {row.calibers.map((caliber) => {
                    const checked = selectedSet.has(caliber);
                    const color =
                      caliberColors.get(caliber) || distinctCaliberColor(0);
                    const label = formatCaliberLabel(caliber);
                    return (
                      <Tag.CheckableTag
                        key={caliber}
                        checked={checked}
                        onChange={() => toggleCaliber(caliber)}
                        className={`${styles.chip} ${checked ? styles.chipOn : styles.chipOff}`}
                      >
                        <span
                          className={styles.dot}
                          style={{
                            background: color,
                            opacity: checked ? 1 : 0.35,
                          }}
                        />
                        <span title={label} className={styles.chipLabel}>
                          {label}
                        </span>
                      </Tag.CheckableTag>
                    );
                  })}
                </div>
                <div className={styles.rowActions}>
                  <Tooltip title="全选本行">
                    <Button
                      type="text"
                      size="small"
                      icon={<CheckSquareOutlined />}
                      onClick={() => toggleCategory(row.calibers, true)}
                      disabled={allOn}
                      aria-label="全选本行"
                    />
                  </Tooltip>
                  <Tooltip title="清空本行">
                    <Button
                      type="text"
                      size="small"
                      icon={<ClearOutlined />}
                      onClick={() => toggleCategory(row.calibers, false)}
                      disabled={selectedInRow === 0}
                      aria-label="清空本行"
                    />
                  </Tooltip>
                </div>
              </div>
            );
          })
        ) : (
          <div className={styles.empty}>暂无口径数据</div>
        )}
      </div>

      <div className={styles.panel}>
        <span className={styles.hint}>
          点击色点筛选能使用该弹药的枪械；下方表格点名称打开物品详情
        </span>
        <div className={styles.chart}>
          <TarkovAmmoScatterChart
            data={data}
            colorField="caliber"
            colorDomain={allCalibers}
            axisMax={axisMax}
            onAmmoClick={goGunsForAmmo}
          />
        </div>
      </div>

      <div className={styles.panel}>
        <TarkovAmmoWikiTable data={data} />
      </div>
    </div>
  );
}
