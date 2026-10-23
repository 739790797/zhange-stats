import { Modal } from "antd";
import { formatBeijing } from "@/shared/lib/time";

/**
 * 整表重置只是推断出来的时候问玩家：重置不可撤销，猜错了会清掉正常进度。
 * - prestige：日志里已完成的任务又被重新接了，像是转生；
 * - profile：账号还不知道之前用的是哪个角色，日志里另有一个角色（可能是上个赛季的号）。
 * 确认才整表重置；取消就当普通增量同步。
 */
export function confirmTarkovQuestReset(info: {
  reason: "prestige" | "profile";
  at: string;
  taskCount: number;
}): Promise<boolean> {
  const when = formatBeijing(info.at);
  const prestige = info.reason === "prestige";
  return new Promise((resolve) => {
    Modal.confirm({
      title: prestige ? "看起来你转生了" : "日志里有另一个游戏角色",
      content: prestige
        ? `日志里有 ${info.taskCount} 个已完成的任务在 ${when} 之后又重新接了，像是转生 / 重置了角色。要按转生处理吗？会清掉账号上这个时刻之前的任务进度，只保留之后日志里的，之后同步也不会再写回之前的任务。不是的话选「不是」，照常同步。`
        : `日志里除了当前角色，还有别的角色（可能是上个赛季的号）。当前角色从 ${when} 开始出现。要从那一刻起重新同步吗？会清掉账号上的任务进度，只按当前角色的日志重放；在网站上手动勾的、日志里已经没有的任务会丢掉。只是旧号残留的话选「不是」，照常同步。`,
      okText: prestige ? "是，按转生同步" : "是，从当前角色重新同步",
      okButtonProps: { danger: true },
      cancelText: "不是",
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    });
  });
}
