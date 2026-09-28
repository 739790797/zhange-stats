import type { ReactNode } from "react";
import { useTarkovScreenshotPosition } from "@/lib/useTarkovScreenshotPosition";
import styles from "./TarkovRaidPrepPanel.module.css";

type Props = {
  keyword: string;
  onKeyword: (value: string) => void;
  /** 搜索框上方插槽（如「更换地图」「同步日志」） */
  leading?: ReactNode;
};

export function TarkovShotDirButton() {
  const shotWatch = useTarkovScreenshotPosition();
  if (!shotWatch.supported) return null;
  const label =
    shotWatch.perm === "granted"
      ? "设定截图目录"
      : shotWatch.hasStored
        ? "继续读取截图目录"
        : "设定截图目录";
  return (
    <button
      type="button"
      className={styles.changeMapBtn}
      disabled={shotWatch.busy || shotWatch.perm === "unknown"}
      title={
        shotWatch.perm === "granted"
          ? shotWatch.fix
            ? "正在把你的位置同步到房间"
            : "战局里按游戏截图键，位置会同步到房间"
          : label
      }
      onClick={() => void shotWatch.enable()}
    >
      {label}
    </button>
  );
}

export function TarkovRaidPrepFilters({
  keyword,
  onKeyword,
  leading,
}: Props) {
  return (
    <>
      {leading}
      <input
        id="raid-prep-search"
        className={styles.dockSearch}
        type="search"
        value={keyword}
        onChange={(event) => onKeyword(event.target.value)}
        placeholder="搜索任务"
        aria-label="搜索任务"
      />
    </>
  );
}
