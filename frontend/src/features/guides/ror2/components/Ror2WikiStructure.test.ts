/** @vitest-environment happy-dom */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import type { Ror2WikiArticle } from "@/features/guides/ror2/api/ror2Api";
import { Ror2WikiStructure } from "./Ror2WikiStructure";

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

const text = (value: string, token: string) => ({ text: value, original: "Original " + value, token });
const itemsArticle = {
  id: "Items",
  title: text("Items", "wiki-page/Items.title"),
  sections: [
    {
      id: "common",
      level: 2,
      title: text("Common", "wiki-page/Items.section.common.title"),
      tables: [
        {
          id: "equipment",
          caption: text("Equipment", "wiki-page/Items.section.common.table.equipment.caption"),
          columns: [
            { id: "name", label: text("Name", "wiki-page/Items.section.common.table.equipment.column.name") },
            {
              id: "description",
              label: text("Description", "wiki-page/Items.section.common.table.equipment.column.description"),
            },
          ],
        },
      ],
    },
  ],
} as Ror2WikiArticle;

describe("ROR2 Wiki structure", () => {
  it("renders the selected article headings and table labels as token-aware Wiki text", async () => {
    await mount(createElement(Ror2WikiStructure, { articles: [itemsArticle], articleIds: ["Items"] }));

    expect(container?.querySelector("summary")?.textContent).toContain("Wiki 章节与表头");
    expect(container?.textContent).toContain("Items");
    expect(container?.textContent).toContain("Common");
    expect(container?.textContent).toContain("Equipment");
    expect(container?.textContent).toContain("Description");
    expect(container?.querySelectorAll('[class*="tokenized"]').length).toBeGreaterThan(0);
  });

  it("does not render unrelated Wiki article structures", async () => {
    await mount(createElement(Ror2WikiStructure, { articles: [itemsArticle], articleIds: ["Survivors"] }));
    expect(container?.querySelector("details")).toBeNull();
  });
});
