import { Input, Modal, Spin } from "antd";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTarkovWorkbenchGunsmithTasks,
  type TarkovWorkbenchGunsmithTask,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { taskVisibleForFaction, useTarkovPmcFaction } from "@/lib/tarkovPmcFaction";
import styles from "./TarkovWorkbenchBuild.module.css";

type Props = {
  open: boolean;
  onCancel: () => void;
  onPick: (task: TarkovWorkbenchGunsmithTask) => void;
};

export function TarkovWorkbenchGunsmithModal({ open, onCancel, onPick }: Props) {
  const gameMode = useTarkovGameMode();
  const { faction } = useTarkovPmcFaction();
  const [query, setQuery] = useState("");
  const listQuery = useQuery({
    queryKey: ["guides-tarkov-workbench-gunsmith-tasks", gameMode],
    queryFn: fetchTarkovWorkbenchGunsmithTasks,
    enabled: open,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (listQuery.data?.items || []).filter((row) => {
      if (!taskVisibleForFaction(row.faction_name, faction)) return false;
      if (!needle) return true;
      const blob = [row.task_name, row.weapon_name, row.trader_name, row.task_id]
        .join(" ")
        .toLowerCase();
      return blob.includes(needle);
    });
  }, [faction, listQuery.data?.items, query]);

  return (
    <Modal
      open={open}
      title="枪匠任务"
      footer={null}
      destroyOnClose
      centered
      width={720}
      className={styles.pickerModal}
      classNames={{
        body: styles.pickerModalBody,
        content: styles.pickerModalContent,
      }}
      onCancel={onCancel}
    >
      <Input
        allowClear
        size="small"
        className={styles.pickerSearch}
        placeholder="搜索任务 / 枪名"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {listQuery.isLoading ? (
        <div className={styles.status}>
          <Spin tip="加载枪匠任务…" />
        </div>
      ) : listQuery.isError ? (
        <div className={styles.hint}>{apiError(listQuery.error, "枪匠任务加载失败")}</div>
      ) : rows.length ? (
        <div className={styles.gunsmithList}>
          {rows.map((row) => (
            <button
              key={row.id}
              type="button"
              className={styles.gunsmithRow}
              disabled={!row.loadable}
              onClick={() => {
                if (!row.loadable) return;
                onPick(row);
              }}
            >
              {row.weapon_image ? (
                <img src={row.weapon_image} alt="" className={styles.gunsmithThumb} />
              ) : (
                <span className={styles.gunsmithThumb} />
              )}
              <span className={styles.gunsmithRowBody}>
                <span className={styles.gunsmithName}>{row.task_name}</span>
                <span className={styles.gunsmithMeta}>
                  {[row.trader_name, row.weapon_name].filter(Boolean).join(" · ")}
                  {row.loadable ? "" : " · 图鉴没有这把枪"}
                </span>
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div className={styles.hint}>没有枪匠改装任务</div>
      )}
    </Modal>
  );
}
