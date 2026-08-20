import { useEffect } from "react";

export function useTarkovDocumentTitle(title: string) {
  useEffect(() => {
    const next = title.trim();
    if (!next) return;
    const prev = document.title;
    document.title = next.includes("逃离塔科夫") ? next : `${next} · 逃离塔科夫`;
    return () => {
      document.title = prev;
    };
  }, [title]);
}
