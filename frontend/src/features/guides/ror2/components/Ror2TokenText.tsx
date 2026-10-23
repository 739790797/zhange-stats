import { Popover } from "antd";
import type { ReactNode } from "react";
import { toRor2ResolvedText, type Ror2TextLike } from "@/features/guides/ror2/model/ror2Text";
import styles from "./Ror2TokenText.module.css";

type TextProps = {
  value: Ror2TextLike;
  children?: ReactNode;
  className?: string;
  showInfo?: boolean;
};

export function Ror2TokenText({ value, children, className, showInfo = true }: TextProps) {
  const text = toRor2ResolvedText(value);
  const root = [styles.container, className].filter(Boolean).join(" ");
  return (
    <span className={root}>
      <span className={text.token ? styles.tokenized : undefined}>
        {children ?? text.text}
      </span>
      {showInfo && text.token ? <Ror2TextInfo value={text} /> : null}
    </span>
  );
}

export function Ror2TextInfo({ value }: { value: Ror2TextLike }) {
  const text = toRor2ResolvedText(value);
  if (!text.token) return null;
  return (
    <Popover
      rootClassName={styles.popoverRoot}
      trigger="click"
      placement="top"
      content={
        <div className={styles.popover}>
          <div className={styles.caption}>Wiki 原文</div>
          <pre className={styles.original}>{text.original}</pre>
          <div className={styles.caption}>Weblate context</div>
          <code className={styles.token}>{text.token}</code>
        </div>
      }
    >
      <button
        type="button"
        className={`${styles.infoButton} ror2-token-info-trigger`}
        aria-label="查看对应的 Wiki 原文和 Weblate 令牌"
        title="查看原文与令牌"
        aria-haspopup="dialog"
        onClick={(event) => event.stopPropagation()}
      >
        i
      </button>
    </Popover>
  );
}
