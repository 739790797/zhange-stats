import { useEffect, useState } from "react";

/** 后台标签页停掉 TanStack Query 轮询。 */
export function visibleRefetchInterval(
  ms: number,
  hidden: boolean,
): number | false {
  if (hidden) return false;
  return ms;
}

export function useDocumentHidden(): boolean {
  const [hidden, setHidden] = useState(
    () => typeof document !== "undefined" && document.hidden,
  );
  useEffect(() => {
    const onVis = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);
  return hidden;
}
