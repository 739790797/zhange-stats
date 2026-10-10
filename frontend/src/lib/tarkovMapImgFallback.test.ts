/** @vitest-environment happy-dom */
import { afterEach, describe, expect, it } from "vitest";
import {
  attachFallbackImgErrors,
  fallbackImgHtml,
} from "./tarkovMapImgFallback";

const ICON = "https://tarkov.dev/images/traders/prapor-icon.jpg";
const PORTRAIT = "https://tarkov.dev/images/traders/prapor-portrait.png";

function traderImg() {
  return fallbackImgHtml({
    className: "trader",
    src: ICON,
    fallbackSrc: PORTRAIT,
    size: 20,
  });
}

describe("fallbackImgHtml", () => {
  it("carries the fallback in a data attribute instead of an inline handler", () => {
    const html = traderImg();
    expect(html).not.toMatch(/\son[a-z]+=/i);
    expect(html).toContain(`src="${ICON}"`);
    expect(html).toContain(`data-fallback-src="${PORTRAIT}"`);
  });

  it("escapes attribute values", () => {
    const html = fallbackImgHtml({
      className: "trader",
      src: `x" onerror="alert(1)`,
      fallbackSrc: `y' onload='alert(2)`,
      size: 20,
    });
    expect(html).not.toContain(`" onerror="`);
    expect(html).not.toContain(`' onload='`);
  });

  it("renders nothing without a src", () => {
    expect(
      fallbackImgHtml({
        className: "trader",
        src: "",
        fallbackSrc: PORTRAIT,
        size: 20,
      }),
    ).toBe("");
  });
});

describe("attachFallbackImgErrors", () => {
  let root: HTMLDivElement | undefined;

  afterEach(() => {
    root?.remove();
    root = undefined;
  });

  function mount(html: string) {
    root = document.createElement("div");
    document.body.appendChild(root);
    const detach = attachFallbackImgErrors(root);
    const pane = document.createElement("div");
    root.appendChild(pane);
    pane.innerHTML = html;
    const img = pane.querySelector("img");
    if (!img) throw new Error("no img");
    return { detach, img };
  }

  it("swaps to the fallback once, then removes the image", () => {
    const { img } = mount(traderImg());

    img.dispatchEvent(new Event("error"));
    expect(img.getAttribute("src")).toBe(PORTRAIT);
    expect(img.isConnected).toBe(true);

    img.dispatchEvent(new Event("error"));
    expect(img.isConnected).toBe(false);
  });

  it("ignores images without a fallback attribute", () => {
    const { img } = mount(`<img src="${ICON}" alt="">`);

    img.dispatchEvent(new Event("error"));
    expect(img.getAttribute("src")).toBe(ICON);
    expect(img.isConnected).toBe(true);
  });

  it("stops handling after detach", () => {
    const { detach, img } = mount(traderImg());
    detach();

    img.dispatchEvent(new Event("error"));
    expect(img.getAttribute("src")).toBe(ICON);
  });
});
