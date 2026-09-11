import { Button } from "antd";
import type { TarkovWorkbenchStats } from "@/api/guidesApi";
import {
  categoryGroupKey,
  formatGunsmithConstraint,
  gunsmithLiveCheck,
  isGunsmithConstraintLive,
  orderedGunsmithConstraints,
  type GunsmithSpec,
} from "@/lib/tarkovWorkbenchGunsmith";
import styles from "./TarkovWorkbenchBuild.module.css";

type Props = {
  spec: GunsmithSpec;
  stats: TarkovWorkbenchStats | null;
  installedIds: string[];
  installedCategoryIds: string[];
  solving?: boolean;
  onSolve: () => void;
  onClear: () => void;
};

function mark(ok: boolean): string {
  return ok ? "✓" : "×";
}

export function TarkovWorkbenchGunsmithPanel({
  spec,
  stats,
  installedIds,
  installedCategoryIds,
  solving,
  onSolve,
  onClear,
}: Props) {
  const check = gunsmithLiveCheck(spec, stats, installedIds, installedCategoryIds);
  const constraints = orderedGunsmithConstraints(spec.constraints);

  return (
    <div className={styles.gunsmithPanel}>
      <div className={styles.paneHead}>
        <span>枪匠任务</span>
        <button type="button" className={styles.gunsmithClear} onClick={onClear}>
          退出
        </button>
      </div>
      <div className={styles.gunsmithTitle}>{spec.task_name}</div>
      {spec.trader_name || spec.weapon_name ? (
        <div className={styles.gunsmithMeta}>
          {[spec.trader_name, spec.weapon_name].filter(Boolean).join(" · ")}
        </div>
      ) : null}
      {constraints.length ? (
        <ul className={styles.gunsmithChecks}>
          {constraints.map(([key, value]) => {
            const live = isGunsmithConstraintLive(key);
            const unmet = live && check?.unmetConstraints.includes(key);
            const hint =
              key === "min_durability"
                ? "（上交时）"
                : key === "max_width" || key === "max_height"
                  ? "（工作台暂不按折叠对照）"
                  : "";
            return (
              <li
                key={key}
                data-ok={live ? (unmet ? "false" : "true") : "note"}
              >
                {live ? mark(!unmet) : "·"} {formatGunsmithConstraint(key, Number(value))}
                {hint}
              </li>
            );
          })}
        </ul>
      ) : null}
      {(spec.required_items || []).length ? (
        <ul className={styles.gunsmithChecks}>
          {(spec.required_items || []).map((item) => {
            const missing = check?.missingItemIds.includes(item.id);
            return (
              <li key={item.id} data-ok={missing ? "false" : "true"}>
                {mark(!missing)} 必装 {item.name || item.id}
              </li>
            );
          })}
        </ul>
      ) : null}
      {(spec.required_category_groups || []).map((group, index) => {
        const key = categoryGroupKey(group);
        const missing = (check?.missingCategoryGroups || []).some(
          (row) => categoryGroupKey(row) === key,
        );
        const label = group.map((row) => row.name || row.id).join(" / ");
        return (
          <ul key={`cat-${index}`} className={styles.gunsmithChecks}>
            <li data-ok={missing ? "false" : "true"}>
              {mark(!missing)} 配件分类：{label}
            </li>
          </ul>
        );
      })}
      <Button
        type="primary"
        size="small"
        loading={solving}
        disabled={!spec.loadable}
        onClick={onSolve}
      >
        求解
      </Button>
    </div>
  );
}
