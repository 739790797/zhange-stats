import { useEffect, useState } from "react";

const REDUCE_QUERY = "(prefers-reduced-motion: reduce)";

/** 系统「减少动态效果」；无 matchMedia 时视为不减动。 */
export function readPrefersReducedMotion(
  matchMedia?: (query: string) => { matches: boolean },
): boolean {
  if (!matchMedia) return false;
  try {
    return Boolean(matchMedia(REDUCE_QUERY).matches);
  } catch {
    return false;
  }
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    readPrefersReducedMotion(
      typeof window !== "undefined" && window.matchMedia
        ? (query) => window.matchMedia(query)
        : undefined,
    ),
  );

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia(REDUCE_QUERY);
    const onChange = () => setReduced(mq.matches);
    setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
