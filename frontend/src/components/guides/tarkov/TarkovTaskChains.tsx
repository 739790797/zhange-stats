import { Link } from "react-router-dom";
import { useState, type ReactNode } from "react";
import { tarkovTaskHref } from "@/lib/tarkovHomeNav";
import { tarkovTaskProgressLabel } from "@/lib/tarkovTaskProgress";
import {
  groupChainsByTrader,
  type GraphTask,
  type TaskChain,
} from "@/lib/tarkovTaskGraph";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import styles from "./TarkovTaskChains.module.css";

type TraderChip = {
  slug: string;
  name: string;
};

type Props = {
  items: GraphTask[];
  traders: TraderChip[];
  mine?: boolean;
  showTraderHead?: boolean;
};

function factionSuffix(value: string | undefined): string {
  const v = (value || "").trim();
  if (!v || v === "Any") return "";
  return ` (${v})`;
}

function statusClass(status: string | null | undefined): string {
  if (status === "available") return styles.statusAvailable;
  if (status === "complete") return styles.statusComplete;
  if (status === "failed") return styles.statusFailed;
  if (status === "locked") return styles.statusLocked;
  return "";
}

function Fold({
  title,
  count,
  defaultOpen,
  children,
}: {
  title: string;
  count: number;
  defaultOpen: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details
      className={styles.chain}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className={styles.summary}>
        <span className={styles.chainTitle}>{title}</span>
        <span className={styles.chainCount}>{count}</span>
      </summary>
      {children}
    </details>
  );
}

function ChainBlock({
  chain,
  mine,
  defaultOpen,
}: {
  chain: TaskChain;
  mine?: boolean;
  defaultOpen: boolean;
}) {
  return (
    <Fold title={chain.title} count={chain.rows.length} defaultOpen={defaultOpen}>
      <ol className={styles.rows}>
        {chain.rows.map((row) => {
          const label = row.task.name || row.task.id;
          const status = row.task.progress_status;
          return (
            <li
              key={row.task.id}
              className={styles.row}
              style={{ paddingLeft: 8 + row.depth * 18 }}
            >
              <Link className={styles.name} to={tarkovTaskHref(row.task.id)}>
                {label}
                {factionSuffix(row.task.faction_name)}
              </Link>
              {mine && status ? (
                <span className={`${styles.status} ${statusClass(status)}`}>
                  {tarkovTaskProgressLabel(status)}
                </span>
              ) : null}
              {row.extraParents.length ? (
                <span className={styles.extras}>
                  还要
                  {row.extraParents.map((parent, index) => (
                    <span key={parent.id}>
                      {index ? "、" : " "}
                      <Link className={styles.extraLink} to={tarkovTaskHref(parent.id)}>
                        {parent.name}
                      </Link>
                      {mine && parent.met === true
                        ? "（已满足）"
                        : mine && parent.met === false
                          ? "（未完成）"
                          : ""}
                    </span>
                  ))}
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </Fold>
  );
}

export function TarkovTaskChains({
  items,
  traders,
  mine,
  showTraderHead = true,
}: Props) {
  const groups = groupChainsByTrader(items, traders);
  if (!groups.length) {
    return <div className={styles.empty}>当前筛选下无任务</div>;
  }

  return (
    <div className={styles.stack}>
      {groups.map((group) => {
        const linked = group.chains.filter((chain) => !chain.singleton);
        const singles = group.chains.filter((chain) => chain.singleton);
        const inner = (
          <>
            {linked.map((chain) => (
              <ChainBlock
                key={chain.id}
                chain={chain}
                mine={mine}
                defaultOpen={chain.rows.length >= 2}
              />
            ))}
            {singles.length ? (
              <Fold
                title={linked.length ? "其他任务" : "任务"}
                count={singles.length}
                defaultOpen={!linked.length}
              >
                <ol className={styles.rows}>
                  {singles.flatMap((chain) =>
                    chain.rows.map((row) => {
                      const status = row.task.progress_status;
                      return (
                        <li key={row.task.id} className={styles.row}>
                          <Link
                            className={styles.name}
                            to={tarkovTaskHref(row.task.id)}
                          >
                            {row.task.name || row.task.id}
                            {factionSuffix(row.task.faction_name)}
                          </Link>
                          {mine && status ? (
                            <span
                              className={`${styles.status} ${statusClass(status)}`}
                            >
                              {tarkovTaskProgressLabel(status)}
                            </span>
                          ) : null}
                          {row.extraParents.length ? (
                            <span className={styles.extras}>
                              还要
                              {row.extraParents.map((parent, index) => (
                                <span key={parent.id}>
                                  {index ? "、" : " "}
                                  <Link
                                    className={styles.extraLink}
                                    to={tarkovTaskHref(parent.id)}
                                  >
                                    {parent.name}
                                  </Link>
                                  {mine && parent.met === true
                                    ? "（已满足）"
                                    : mine && parent.met === false
                                      ? "（未完成）"
                                      : ""}
                                </span>
                              ))}
                            </span>
                          ) : null}
                        </li>
                      );
                    }),
                  )}
                </ol>
              </Fold>
            ) : null}
          </>
        );

        if (!showTraderHead) {
          return (
            <div key={group.traderSlug || "none"} className={styles.groupInner}>
              {inner}
            </div>
          );
        }

        return (
          <section key={group.traderSlug || "none"} className={styles.group}>
            <h3 className={styles.traderHead}>
              {group.traderSlug ? (
                <TarkovTraderThumb
                  slug={group.traderSlug}
                  size={28}
                  title={group.traderName}
                />
              ) : null}
              <span>{group.traderName || "未知商人"}</span>
              <span className={styles.chainCount}>
                {group.chains.reduce((sum, chain) => sum + chain.rows.length, 0)}
              </span>
            </h3>
            {inner}
          </section>
        );
      })}
    </div>
  );
}
