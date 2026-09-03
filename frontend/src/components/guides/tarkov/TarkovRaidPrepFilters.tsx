import type { ReactNode } from "react";
import styles from "./TarkovRaidPrepPanel.module.css";

type Props = {
  keyword: string;
  onKeyword: (value: string) => void;
  /** 搜索框上方插槽（如「更换地图」「同步日志」） */
  leading?: ReactNode;
};

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
