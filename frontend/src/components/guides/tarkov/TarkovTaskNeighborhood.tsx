import { Link } from "react-router-dom";
import { tarkovTaskHref } from "@/lib/tarkovHomeNav";
import { tarkovTaskProgressLabel } from "@/lib/tarkovTaskProgress";
import {
  layoutTaskNeighborhood,
  type NeighborhoodEdge,
  type NeighborhoodNode,
} from "@/lib/tarkovTaskGraph";
import styles from "./TarkovTaskNeighborhood.module.css";

type Props = {
  currentId: string;
  nodes: NeighborhoodNode[];
  edges: NeighborhoodEdge[];
  showProgress?: boolean;
};

function statusClass(status: string | null | undefined, current: boolean): string {
  if (current) return styles.nodeCurrent;
  if (status === "available") return styles.nodeAvailable;
  if (status === "complete") return styles.nodeComplete;
  if (status === "failed") return styles.nodeFailed;
  if (status === "locked") return styles.nodeLocked;
  return "";
}

export function TarkovTaskNeighborhood({
  currentId,
  nodes,
  edges,
  showProgress,
}: Props) {
  const others = nodes.filter((node) => node.id !== currentId);
  if (!others.length) {
    return <div className={styles.empty}>无前置 · 无后续</div>;
  }

  const layout = layoutTaskNeighborhood(nodes, edges, currentId);
  return (
    <div className={styles.wrap}>
      <h3 className={styles.heading}>任务线</h3>
      <div
        className={styles.canvas}
        style={{ width: layout.width, height: layout.height }}
      >
        <svg
          className={styles.edges}
          width={layout.width}
          height={layout.height}
          aria-hidden
        >
          {layout.edges.map((edge) => (
            <line
              key={`${edge.source_id}-${edge.target_id}`}
              x1={edge.x1}
              y1={edge.y1}
              x2={edge.x2}
              y2={edge.y2}
            />
          ))}
        </svg>
        {layout.nodes.map((node) => {
          const label = node.name || node.id;
          const className = `${styles.node} ${statusClass(
            showProgress ? node.progress_status : undefined,
            node.current,
          )}`;
          const inner = (
            <>
              <span className={styles.nodeName}>{label}</span>
              {showProgress && node.progress_status ? (
                <span className={styles.nodeMeta}>
                  {tarkovTaskProgressLabel(node.progress_status)}
                </span>
              ) : null}
            </>
          );
          const style = {
            left: node.x,
            top: node.y,
            width: node.width,
            height: node.height,
          };
          if (node.current) {
            return (
              <div
                key={node.id}
                className={className}
                style={style}
                aria-current="page"
              >
                {inner}
              </div>
            );
          }
          return (
            <Link
              key={node.id}
              className={className}
              style={style}
              to={tarkovTaskHref(node.id)}
            >
              {inner}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
