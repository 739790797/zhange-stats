/**
 * 地图气泡 / divIcon 里用 HTML 字符串拼的小图：加载失败先换备用地址，再失败就移除。
 * 站点 CSP 的 script-src 不放行内联事件属性，所以不写 onerror=；
 * img 的 error 不冒泡，由地图容器在捕获阶段统一接（气泡每次 update 都会重建 innerHTML，逐个绑会丢）。
 */
import { escapeHtml } from "@/lib/escapeHtml";

const FALLBACK_ATTR = "data-fallback-src";

export function fallbackImgHtml(input: {
  className: string;
  src: string;
  fallbackSrc: string;
  size: number;
}): string {
  if (!input.src) return "";
  return `<img class="${escapeHtml(input.className)}" src="${escapeHtml(input.src)}" alt="" width="${input.size}" height="${input.size}" ${FALLBACK_ATTR}="${escapeHtml(input.fallbackSrc)}">`;
}

function handleFallbackImgError(event: Event) {
  const img = event.target;
  if (!(img instanceof HTMLImageElement)) return;
  const fallback = img.getAttribute(FALLBACK_ATTR);
  if (fallback === null) return;
  if (fallback) {
    img.setAttribute(FALLBACK_ATTR, "");
    img.src = fallback;
  } else {
    img.remove();
  }
}

/** 返回解绑函数。 */
export function attachFallbackImgErrors(container: HTMLElement): () => void {
  container.addEventListener("error", handleFallbackImgError, true);
  return () =>
    container.removeEventListener("error", handleFallbackImgError, true);
}
