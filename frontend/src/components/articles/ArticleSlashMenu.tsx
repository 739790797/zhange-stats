import type { SuggestionKeyDownProps, SuggestionProps } from "@tiptap/suggestion";
import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import type { ArticleSlashItem } from "@/lib/articleTiptap";
import styles from "./TavernEdit.module.css";

export type ArticleSlashMenuHandle = {
  onKeyDown: (props: SuggestionKeyDownProps) => boolean;
};

export const ArticleSlashMenu = forwardRef<
  ArticleSlashMenuHandle,
  SuggestionProps<ArticleSlashItem, ArticleSlashItem>
>(function ArticleSlashMenu(props, ref) {
  const [index, setIndex] = useState(0);
  const items = props.items || [];
  const itemKey = items.map((item) => item.id).join("|");

  useEffect(() => {
    setIndex(0);
  }, [itemKey]);

  useImperativeHandle(ref, () => ({
    onKeyDown: ({ event }) => {
      if (event.key === "ArrowDown") {
        setIndex((cur) => (cur + 1) % Math.max(items.length, 1));
        return true;
      }
      if (event.key === "ArrowUp") {
        setIndex((cur) => (cur - 1 + items.length) % Math.max(items.length, 1));
        return true;
      }
      if (event.key === "Enter") {
        const item = items[index];
        if (item) props.command(item);
        return true;
      }
      return false;
    },
  }));

  if (!items.length) {
    return <div className={styles.slashEmpty}>没有匹配的块</div>;
  }

  return (
    <div className={styles.slash} role="listbox">
      {items.map((item, i) => (
        <button
          key={item.id}
          type="button"
          className={i === index ? styles.slashItemActive : styles.slashItem}
          onMouseDown={(event) => {
            event.preventDefault();
            props.command(item);
          }}
        >
          {item.title}
        </button>
      ))}
    </div>
  );
});
