/** @vitest-environment happy-dom */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { Ror2RichText } from "./Ror2RichText";
import { Ror2TextInfo, Ror2TokenText } from "./Ror2TokenText";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const tokenText = {
  text: "已审核的显示文本",
  original: "Wiki 原文段落",
  token: "ror2.items.ITEM_EXAMPLE.name",
};

let container: HTMLDivElement | undefined;
let root: Root | undefined;

async function mount(node: React.ReactNode) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => {
    root?.render(node);
  });
}

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount());
    root = undefined;
  }
  container?.remove();
  container = undefined;
  document.querySelectorAll(".ant-popover").forEach((node) => node.remove());
});

describe("ROR2 token text components", () => {
  it("adds token styling and an info trigger only when a Weblate context exists", async () => {
    await mount(
      createElement(
        "div",
        null,
        createElement(Ror2TokenText, { value: tokenText }),
        createElement(Ror2TokenText, { value: "本站本地提示" }),
      ),
    );

    expect(container?.querySelectorAll("button")).toHaveLength(1);
    expect(container?.querySelector("button")?.classList.contains("ror2-token-info-trigger")).toBe(true);
    expect(container?.querySelectorAll('[class*="tokenized"]')).toHaveLength(1);
    expect(container?.textContent).toContain("已审核的显示文本");
    expect(container?.textContent).toContain("本站本地提示");
  });

  it("opens the Wiki original and exact Weblate context from the info trigger", async () => {
    await mount(createElement(Ror2TextInfo, { value: tokenText }));
    const button = container?.querySelector("button");
    expect(button).not.toBeNull();

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(document.body.textContent).toContain("Wiki 原文");
    expect(document.body.textContent).toContain("Wiki 原文段落");
    expect(document.body.textContent).toContain("Weblate context");
    expect(document.body.textContent).toContain("ror2.items.ITEM_EXAMPLE.name");
  });

  it("preserves links and Wiki rich-text markup while keeping info outside the link", async () => {
    const rich = {
      text: "<style=cIsDamage>火焰</style><style=cKeywordName>关键字</style>",
      original: "Wiki rich 原文",
      token: "ror2.items.ITEM_EXAMPLE.description",
    };
    await mount(
      createElement(
        "div",
        null,
        createElement(
          "a",
          { href: "/guides/ror2/items" },
          createElement(Ror2RichText, { text: rich, showInfo: false }),
        ),
        createElement(Ror2TextInfo, { value: rich }),
      ),
    );

    const link = container?.querySelector("a");
    expect(link?.getAttribute("href")).toBe("/guides/ror2/items");
    expect(link?.querySelector("strong")?.textContent).toBe("[ 关键字 ]");
    expect(link?.querySelector('[style*="color"]')).not.toBeNull();
    expect(link?.querySelector("button")).toBeNull();
    expect(container?.querySelector("button")).not.toBeNull();
  });
});