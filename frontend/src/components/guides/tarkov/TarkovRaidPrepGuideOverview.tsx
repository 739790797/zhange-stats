import { useEffect, useMemo, useState } from "react";
import { ConfigProvider, Modal } from "antd";
import { useTarkovMapOverlayContainer } from "@/lib/tarkovMapFullscreen";
import {
  EFTARKOV_GUIDE_ORIGIN,
  eftarkovTaskGuideUrl,
  resolveRaidPrepGuideId,
} from "@/lib/eftarkovGuide";
import {
  collectRaidPrepFailChips,
  collectRaidPrepOtherMapGroups,
  collectRaidPrepSequenceGroups,
  collectRaidPrepTaskObjectives,
  colorForTaskId,
  colorForUserId,
  displayRaidPrepTaskName,
  raidPrepMapObjectivesComplete,
  raidPrepSkippedIds,
  type RaidPrepSkipMap,
  type RaidPrepTaskLike,
} from "@/lib/tarkovRaidPrep";
import {
  type RaidPrepParticipant,
} from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepObjectiveProgress } from "@/components/guides/tarkov/TarkovRaidPrepObjectiveHint";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import styles from "./TarkovRaidPrepPanel.module.css";

export type RaidPrepGuideTask = {
  id: string;
  name?: string | null;
  normalized_name?: string | null;
  trader_slug?: string | null;
  trader_name?: string | null;
  objectives?: RaidPrepTaskLike["objectives"];
  fail_conditions?: RaidPrepTaskLike["fail_conditions"];
};

type Props = {
  tasks: RaidPrepGuideTask[];
  mapId?: string;
  participantsByTask?: ReadonlyMap<string, readonly RaidPrepParticipant[]>;
  skippedByTask?: RaidPrepSkipMap;
  doneTaskIds?: ReadonlySet<string> | readonly string[] | null;
  onToggleObjective?: (taskId: string, objectiveId: string) => void;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  activeId?: string;
  onActiveIdChange?: (taskId: string) => void;
};

function ParticipantLine({
  people,
}: {
  people: readonly RaidPrepParticipant[];
}) {
  if (!people.length) {
    return <span className={styles.summaryNone}>—</span>;
  }
  return (
    <div className={styles.summaryPeople}>
      {people.map((person, index) => (
        <span
          key={`${person.userId ?? person.name}-${index}`}
          className={styles.summaryPerson}
          title={person.name}
        >
          <span
            className={styles.memberDot}
            style={{
              background:
                person.userId != null
                  ? colorForUserId(person.userId)
                  : colorForTaskId(person.name),
            }}
          />
          <span className={styles.summaryPersonName}>{person.name}</span>
        </span>
      ))}
    </div>
  );
}

export function TarkovRaidPrepGuideOverview({
  tasks,
  mapId = "",
  participantsByTask,
  skippedByTask,
  doneTaskIds,
  onToggleObjective,
  open: openProp,
  onOpenChange,
  activeId: activeIdProp,
  onActiveIdChange,
}: Props) {
  const [openInner, setOpenInner] = useState(false);
  const [activeIdInner, setActiveIdInner] = useState("");
  const open = openProp ?? openInner;
  const setOpen = onOpenChange ?? setOpenInner;
  const activeId = activeIdProp ?? activeIdInner;
  const setActiveId = onActiveIdChange ?? setActiveIdInner;
  const overlayRoot = useTarkovMapOverlayContainer();
  const popupContainer = () => overlayRoot || document.body;
  const selectedIds = useMemo(() => tasks.map((row) => row.id), [tasks]);
  const guideId = resolveRaidPrepGuideId(selectedIds, activeId);
  const activeUrl = guideId ? eftarkovTaskGuideUrl(guideId) : null;
  const activeTask = tasks.find((row) => row.id === guideId);
  const activeObjectives = useMemo(
    () => (activeTask ? collectRaidPrepTaskObjectives(activeTask, mapId) : []),
    [activeTask, mapId],
  );
  const activeOtherMaps = useMemo(
    () => (activeTask ? collectRaidPrepOtherMapGroups(activeTask, mapId) : []),
    [activeTask, mapId],
  );
  const activeSequence = useMemo(
    () => (activeTask ? collectRaidPrepSequenceGroups(activeTask, mapId) : []),
    [activeTask, mapId],
  );
  const activeFailChips = useMemo(
    () => (activeTask ? collectRaidPrepFailChips(activeTask.fail_conditions) : []),
    [activeTask],
  );
  const activeSkipped = useMemo(
    () => (guideId ? raidPrepSkippedIds(skippedByTask, guideId) : undefined),
    [guideId, skippedByTask],
  );
  const doneIdSet = useMemo(
    () => (doneTaskIds instanceof Set ? doneTaskIds : new Set(doneTaskIds || [])),
    [doneTaskIds],
  );

  useEffect(() => {
    const next = resolveRaidPrepGuideId(selectedIds, activeId);
    if (next !== activeId) setActiveId(next);
  }, [activeId, selectedIds, setActiveId]);

  return (
    <ConfigProvider getPopupContainer={popupContainer}>
      <button
        type="button"
        className={styles.summary}
        onClick={() => setOpen(true)}
      >
        <span className={styles.summaryBtnText}>
          <span className={styles.summaryTitle}>任务攻略总览</span>
        </span>
        <span className={styles.summaryAction}>查看</span>
      </button>
      <Modal
        key={overlayRoot ? "fs" : "page"}
        title="任务攻略总览"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width="calc(100vw - 24px)"
        centered
        zIndex={2100}
        getContainer={() => overlayRoot || document.body}
        className={styles.guideModal}
        classNames={{
          body: styles.guideModalBody,
          content: styles.guideModalContent,
        }}
        styles={{
          body: { maxHeight: "none", height: "100%", paddingTop: 12 },
        }}
      >
        {!tasks.length ? (
          <div className={styles.summaryEmpty}>勾选任务后查看中文图文攻略</div>
        ) : (
          <div className={styles.guideLayout}>
            <aside className={styles.guideSidebar} aria-label="已选任务">
              {activeTask ? (
                <div className={styles.guideProgress}>
                  <div className={styles.guideProgressHead}>任务进度</div>
                  <div className={styles.guideProgressBody}>
                    <TarkovRaidPrepObjectiveProgress
                      taskName={displayRaidPrepTaskName(activeTask)}
                      traderSlug={activeTask.trader_slug || ""}
                      traderName={activeTask.trader_name || ""}
                      objectives={activeObjectives}
                      otherMapGroups={activeOtherMaps}
                      sequenceGroups={activeSequence}
                      failChips={activeFailChips}
                      skipped={activeSkipped}
                      taskDone={Boolean(guideId && doneIdSet.has(guideId))}
                      onToggle={
                        onToggleObjective && guideId
                          ? (objectiveId) =>
                              onToggleObjective(guideId, objectiveId)
                          : undefined
                      }
                    />
                  </div>
                </div>
              ) : null}
              <div className={styles.guideSideHead}>
                <span>参与人员</span>
                <span>任务名称</span>
              </div>
              <div className={styles.guideSideList} role="tablist">
                {tasks.map((row) => {
                  const on = row.id === guideId;
                  const label = displayRaidPrepTaskName(row);
                  const mapDone = raidPrepMapObjectivesComplete(
                    row,
                    mapId,
                    raidPrepSkippedIds(skippedByTask, row.id),
                  );
                  return (
                    <button
                      key={row.id}
                      type="button"
                      role="tab"
                      aria-selected={on}
                      className={`${styles.guideSideRow} ${
                        on ? styles.guideSideRowOn : ""
                      }`}
                      title={label}
                      onClick={() => setActiveId(row.id)}
                    >
                      <div className={styles.guideSidePeople}>
                        <ParticipantLine
                          people={participantsByTask?.get(row.id) || []}
                        />
                      </div>
                      <div className={styles.guideSideTask}>
                        <span
                          className={styles.swatch}
                          style={{ background: colorForTaskId(row.id) }}
                        />
                        {row.trader_slug ? (
                          <TarkovTraderThumb
                            slug={row.trader_slug}
                            size={22}
                            title={row.trader_name || row.trader_slug}
                          />
                        ) : null}
                        <span
                          className={`${styles.guideSideTaskName}${
                            mapDone ? ` ${styles.guideSideTaskNameDone}` : ""
                          }`}
                        >
                          {label}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </aside>

            <div className={styles.guideMain}>
              <p className={`${styles.summaryModalLead} ${styles.guideModalLead}`}>
                攻略内嵌自{" "}
                <a
                  className={styles.wiki}
                  href={EFTARKOV_GUIDE_ORIGIN}
                  target="_blank"
                  rel="noreferrer"
                >
                  eftarkov.com
                </a>
                {activeUrl ? (
                  <>
                    {" · "}
                    <a
                      className={styles.wiki}
                      href={activeUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      新标签打开
                    </a>
                  </>
                ) : null}
              </p>
              {activeUrl ? (
                <iframe
                  key={guideId}
                  className={styles.guideFrame}
                  src={activeUrl}
                  title={
                    activeTask
                      ? `${displayRaidPrepTaskName(activeTask)} · eftarkov 攻略`
                      : "eftarkov 任务攻略"
                  }
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                />
              ) : (
                <div className={styles.summaryEmpty}>
                  当前任务暂无 eftarkov 攻略链接
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </ConfigProvider>
  );
}
