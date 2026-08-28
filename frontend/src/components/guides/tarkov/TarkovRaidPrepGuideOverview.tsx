import { useEffect, useMemo, useState } from "react";
import { Modal } from "antd";
import {
  EFTARKOV_GUIDE_ORIGIN,
  eftarkovTaskGuideUrl,
  resolveRaidPrepGuideId,
} from "@/lib/eftarkovGuide";
import { colorForTaskId, colorForUserId, displayRaidPrepTaskName } from "@/lib/tarkovRaidPrep";
import {
  type RaidPrepParticipant,
} from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import styles from "./TarkovRaidPrepPanel.module.css";

export type RaidPrepGuideTask = {
  id: string;
  name?: string | null;
  normalized_name?: string | null;
  trader_slug?: string | null;
  trader_name?: string | null;
};

type Props = {
  tasks: RaidPrepGuideTask[];
  participantsByTask?: ReadonlyMap<string, readonly RaidPrepParticipant[]>;
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
  participantsByTask,
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
  const selectedIds = useMemo(() => tasks.map((row) => row.id), [tasks]);
  const guideId = resolveRaidPrepGuideId(selectedIds, activeId);
  const activeUrl = guideId ? eftarkovTaskGuideUrl(guideId) : null;
  const activeTask = tasks.find((row) => row.id === guideId);

  useEffect(() => {
    if (!selectedIds.length) {
      if (activeId) setActiveId("");
      return;
    }
    const next = resolveRaidPrepGuideId(selectedIds, activeId);
    if (next !== activeId) setActiveId(next);
  }, [activeId, selectedIds, setActiveId]);

  return (
    <>
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
        title="任务攻略总览"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width="calc(100vw - 24px)"
        centered
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
              <div className={styles.guideSideHead}>
                <span>参与人员</span>
                <span>任务名称</span>
              </div>
              <div className={styles.guideSideList} role="tablist">
                {tasks.map((row) => {
                  const on = row.id === guideId;
                  const label = displayRaidPrepTaskName(row);
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
                        <span className={styles.guideSideTaskName}>{label}</span>
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
    </>
  );
}
