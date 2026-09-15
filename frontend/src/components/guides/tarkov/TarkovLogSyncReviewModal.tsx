import { Modal } from "antd";
import type { QuestLogSyncReview } from "@/lib/tarkovTaskLogSync";
import styles from "./TarkovLogSyncReviewModal.module.css";

type Props = {
  open: boolean;
  review: QuestLogSyncReview | null;
  onClose: () => void;
};

export function TarkovLogSyncReviewModal({ open, review, onClose }: Props) {
  const rows = review?.rows || [];
  return (
    <Modal
      title="任务日志"
      open={open}
      onCancel={onClose}
      footer={
        <div className={styles.footer}>
          <button type="button" className={styles.ok} onClick={onClose}>
            关闭
          </button>
        </div>
      }
      width={920}
      destroyOnClose
      classNames={{ body: styles.body }}
    >
      {review?.hint ? <p className={styles.hint}>{review.hint}</p> : null}
      {review?.dropHint ? <p className={styles.warn}>{review.dropHint}</p> : null}
      <p className={styles.count}>共 {rows.length} 条任务相关日志</p>
      {rows.length ? (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">日志行</th>
                <th scope="col">任务名称</th>
                <th scope="col">状态变更</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.at}:${row.taskId}:${index}`}>
                  <td className={styles.line} title={row.line}>
                    {row.line}
                  </td>
                  <td className={styles.name} title={row.taskName}>
                    {row.taskName}
                  </td>
                  <td className={styles.change}>{row.change}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className={styles.empty}>
          {review?.dropHint
            ? "这次范围内没有写入当前账的任务邮件。"
            : "这次范围内没有解析到任务邮件。"}
        </p>
      )}
    </Modal>
  );
}
