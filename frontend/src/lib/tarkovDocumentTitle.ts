import { useDocumentTitle } from "@/lib/documentTitle";

/** 塔科夫攻略标签：`栏目 · 逃离塔科夫`。 */
export function useTarkovDocumentTitle(title: string) {
  useDocumentTitle(title, "逃离塔科夫");
}
