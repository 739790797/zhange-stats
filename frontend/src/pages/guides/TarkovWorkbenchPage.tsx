import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Spin } from "antd";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { TarkovWorkbenchBuild } from "@/components/guides/tarkov/workbench/TarkovWorkbenchBuild";
import { TarkovWorkbenchEmpty } from "@/components/guides/tarkov/workbench/TarkovWorkbenchEmpty";
import { TarkovWorkbenchGunPickerModal } from "@/components/guides/tarkov/workbench/TarkovWorkbenchGunPickerModal";
import { TarkovWorkbenchGunsmithModal } from "@/components/guides/tarkov/workbench/TarkovWorkbenchGunsmithModal";
import styles from "@/components/guides/tarkov/workbench/TarkovWorkbenchBuild.module.css";
import { fetchTarkovWorkbenchGunsmithTasks } from "@/api/guidesApi";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_WORKBENCH_PATH,
  tarkovWorkbenchHref,
} from "@/lib/tarkovHomeNav";
import { findGunsmithSpec } from "@/lib/tarkovWorkbenchGunsmith";

export default function TarkovWorkbenchPage() {
  const { gunId } = useParams<{ gunId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const gameMode = useTarkovGameMode();
  const [pickOpen, setPickOpen] = useState(false);
  const [gunsmithOpen, setGunsmithOpen] = useState(false);
  const taskId = (searchParams.get("task") || "").trim();
  const objectiveId = (searchParams.get("obj") || "").trim();

  const gunsmithQuery = useQuery({
    queryKey: ["guides-tarkov-workbench-gunsmith-tasks", gameMode],
    queryFn: fetchTarkovWorkbenchGunsmithTasks,
    enabled: Boolean(taskId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const spec = findGunsmithSpec(gunsmithQuery.data?.items, taskId, objectiveId);

  useEffect(() => {
    if (!taskId || gunId) return;
    if (!spec?.loadable || !spec.weapon_id) return;
    navigate(
      tarkovWorkbenchHref(spec.weapon_id, {
        taskId: spec.task_id,
        objectiveId: spec.objective_id || undefined,
      }),
      { replace: true },
    );
  }, [gunId, navigate, spec, taskId]);

  useEffect(() => {
    if (!gunId || !spec?.loadable || !spec.weapon_id) return;
    if (spec.weapon_id === gunId) return;
    navigate(
      tarkovWorkbenchHref(spec.weapon_id, {
        taskId: spec.task_id,
        objectiveId: spec.objective_id || undefined,
      }),
      { replace: true },
    );
  }, [gunId, navigate, spec]);

  const pickGun = (id: string) => {
    setPickOpen(false);
    navigate(tarkovWorkbenchHref(id));
  };

  const pickGunsmith = (row: {
    weapon_id: string;
    task_id: string;
    objective_id?: string;
    loadable?: boolean;
  }) => {
    setGunsmithOpen(false);
    if (!row.weapon_id) return;
    navigate(
      tarkovWorkbenchHref(row.weapon_id, {
        taskId: row.task_id,
        objectiveId: row.objective_id,
      }),
    );
  };

  return (
    <TarkovItemsPageShell
      title={gunId ? undefined : "枪械工作台"}
      crumbs={gunId ? [{ label: "改枪" }] : []}
      sectionLabel="工作台"
      sectionHref={TARKOV_WORKBENCH_PATH}
      fill
    >
      <div className={styles.stage}>
        {gunId ? (
          <TarkovWorkbenchBuild
            gunId={gunId}
            taskId={taskId}
            objectiveId={objectiveId}
            onChangeGun={() => setPickOpen(true)}
            onPickGunsmith={() => setGunsmithOpen(true)}
            onClearGunsmith={() => navigate(tarkovWorkbenchHref(gunId))}
          />
        ) : taskId && gunsmithQuery.isLoading ? (
          <div className={styles.status}>
            <Spin tip="加载枪匠任务…" />
          </div>
        ) : (
          <TarkovWorkbenchEmpty
            onAdd={() => setPickOpen(true)}
            onGunsmith={() => setGunsmithOpen(true)}
          />
        )}
        <TarkovWorkbenchGunPickerModal
          open={pickOpen}
          onCancel={() => setPickOpen(false)}
          onPick={pickGun}
        />
        <TarkovWorkbenchGunsmithModal
          open={gunsmithOpen}
          onCancel={() => setGunsmithOpen(false)}
          onPick={pickGunsmith}
        />
      </div>
    </TarkovItemsPageShell>
  );
}
