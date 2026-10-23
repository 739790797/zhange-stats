/** 换页聚焦用：压掉 F5 等键盘刷新触发的 :focus-visible 描边。 */
export const ROUTE_FOCUS_CLASS = "app-route-focus";

type FocusOptionsWithVisible = FocusOptions & { focusVisible?: boolean };

/** 把焦点移到 main，读屏能跟上换页，但不画出整栏黑框。 */
export function focusWithoutVisibleRing(el: HTMLElement | null | undefined) {
  if (!el) return;
  el.classList.add(ROUTE_FOCUS_CLASS);
  el.focus({
    preventScroll: true,
    focusVisible: false,
  } as FocusOptionsWithVisible);
  el.addEventListener(
    "blur",
    () => {
      el.classList.remove(ROUTE_FOCUS_CLASS);
    },
    { once: true },
  );
}
