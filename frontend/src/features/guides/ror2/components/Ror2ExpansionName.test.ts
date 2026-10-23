/** @vitest-environment happy-dom */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { Ror2ExpansionName } from "./Ror2ExpansionName";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

let container: HTMLDivElement | undefined;
let root: Root | undefined;

async function mount(node: React.ReactNode) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => root?.render(node));
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

describe("ROR2 expansion names", () => {
  it("uses supplied official Chinese names when the matching Weblate token is unavailable", async () => {
    await mount(
      createElement(
        "div",
        null,
        createElement(Ror2ExpansionName, { id: "SotV" }),
        createElement(Ror2ExpansionName, { id: "SotS" }),
        createElement(Ror2ExpansionName, { id: "AC" }),
        createElement(Ror2ExpansionName, { id: "HC" }),
        createElement(Ror2ExpansionName, { id: "base" }),
        createElement(Ror2ExpansionName, { id: "Other", fallback: "Other" }),
      ),
    );

    expect(container?.textContent).toBe("虚空幸存者风暴探寻者合金意念神圣观念雨中冒险2Other");
    expect(container?.querySelectorAll("button")).toHaveLength(0);
  });

  it("uses the Wiki title unit and exposes its original/context when a token exists", async () => {
    await mount(
      createElement(Ror2ExpansionName, {
        id: "SotV",
        wikiArticles: [
          {
            id: "expansion:SotV",
            title: {
              text: "虚空幸存者",
              original: "Survivors of the Void",
              token: "wiki-expansion/SotV.title",
            },
            sections: [],
          },
        ],
      }),
    );

    expect(container?.textContent).toContain("虚空幸存者");
    expect(container?.querySelector("button.ror2-token-info-trigger")).not.toBeNull();
    expect(container?.querySelector('[class*="tokenized"]')).not.toBeNull();

    await act(async () => {
      container?.querySelector("button")?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(document.body.textContent).toContain("Survivors of the Void");
    expect(document.body.textContent).toContain("wiki-expansion/SotV.title");
  });
});
