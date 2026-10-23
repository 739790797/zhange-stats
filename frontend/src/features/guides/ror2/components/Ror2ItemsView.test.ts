/** @vitest-environment happy-dom */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Ror2Catalog, Ror2Item } from "../api/ror2Api";
import { Ror2ItemDetailView } from "./Ror2ItemDetailView";
import { Ror2ItemsView } from "./Ror2ItemsView";

const catalogMock = vi.hoisted(() => ({ useRor2Catalog: vi.fn() }));
vi.mock("../hooks/useRor2Catalog", () => ({ useRor2Catalog: catalogMock.useRor2Catalog }));
vi.mock("./Ror2WikiStructure", () => ({ Ror2WikiStructure: () => null }));

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const token = (text: string, original: string, context: string | null) => ({ text, original, token: context });
const fireworks = {
  name: "Fireworks",
  rarity: "Common",
  quote: "Short pickup source",
  description: "Detailed description source",
  lore: "Logbook source",
  unlock: "",
  expansion: "SotV",
  internal_name: "ITEM_FIREWORKS",
  code: "Fireworks",
  corrupt: "",
  uncorrupt: "",
  boss: "",
  cooldown: "",
  wiki_url: "https://riskofrain2.wiki.gg/wiki/Fireworks",
  image_url: "https://example.test/fireworks.png",
  categories: [],
  stats: [{
    label: "Stack",
    value: "",
    stack: "Linear",
    add: "",
    localizedText: { stack: token("线性译文", "Linear", "items.items.ITEM_FIREWORKS.Stats.1.Stack") },
  }],
  localizedText: {
    name: token("一捆烟花", "Fireworks", "items.items.ITEM_FIREWORKS.name"),
    rarity: token("普通译文", "Common", "items.items.ITEM_FIREWORKS.Rarity"),
    quote: token("简单描述译文", "Short pickup source", "items.items.ITEM_FIREWORKS.Quote"),
    description: token("详细描述译文", "Detailed description source", "items.items.ITEM_FIREWORKS.Desc"),
    lore: token("日志译文", "Logbook source", "lore.lore.Fireworks.Desc"),
    unlock: token("", "", null),
  },
} as unknown as Ror2Item;
const catalog = {
  items: [fireworks],
  equipment: [],
  survivors: [],
  monsters: [],
  drones: [],
  environments: [],
  challenges: [],
  interactables: [],
  artifacts: [],
  wiki_articles: [],
} as unknown as Ror2Catalog;

let container: HTMLDivElement | undefined;
let root: Root | undefined;

async function mount(node: ReactNode) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => root?.render(node));
}

beforeEach(() => {
  catalogMock.useRor2Catalog.mockReturnValue({
    data: catalog,
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  });
});

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount());
    root = undefined;
  }
  container?.remove();
  container = undefined;
});

describe("ROR2 item list and detail layout", () => {
  it("renders one description column with short and detailed text stacked, without log text", async () => {
    await mount(
      createElement(
        MemoryRouter,
        { initialEntries: ["/guides/ror2/items?cat=Common&q=fireworks"] },
        createElement(Ror2ItemsView),
      ),
    );

    const headers = [...(container?.querySelectorAll("thead th") ?? [])].map((header) => header.textContent?.trim());
    expect(headers).toEqual(["物品", "描述", "堆叠方式"]);
    expect(container?.textContent).toContain("普通译文");
    const row = container?.querySelector("tbody tr");
    expect(row?.children).toHaveLength(3);
    const itemIdentity = row?.children[0]?.firstElementChild;
    const itemIcon = row?.children[0]?.querySelector('img[width="56"]');
    const dlcIcon = row?.children[0]?.querySelector('img[width="18"]');
    expect(itemIcon?.parentElement).toBe(itemIdentity?.firstElementChild);
    expect(dlcIcon?.closest("span")?.parentElement).toBe(itemIcon?.parentElement);
    expect(itemIdentity?.lastElementChild?.querySelector("a")).not.toBeNull();
    const descriptionGroups = [...(row?.children[1]?.querySelectorAll('[role="group"]') ?? [])];
    expect(descriptionGroups.map((group) => group.getAttribute("aria-label"))).toEqual(["简单描述", "详细描述"]);
    expect(container?.querySelector('[aria-label="简单描述"]')?.textContent).toContain("简单描述译文");
    expect(container?.querySelector('[aria-label="详细描述"]')?.textContent).toContain("详细描述译文");
    expect(container?.querySelector("tbody")?.textContent).not.toContain("日志译文");
    const stackCell = row?.children[2];
    expect(stackCell?.textContent).toContain("线性译文");
    expect(stackCell?.querySelector('button[aria-label="查看对应的 Wiki 原文和 Weblate 令牌"]')).not.toBeNull();
    expect(container?.querySelector("tbody details")).toBeNull();
    expect(container?.querySelector('a[href="/guides/ror2/items/item/ITEM_FIREWORKS?cat=Common&q=fireworks"]')).not.toBeNull();
  });

  it("shows the logbook on the item detail page", async () => {
    await mount(
      createElement(
        MemoryRouter,
        { initialEntries: ["/guides/ror2/items/item/ITEM_FIREWORKS?cat=Common"] },
        createElement(
          Routes,
          null,
          createElement(Route, {
            path: "/guides/ror2/items/:itemKind/:itemId",
            element: createElement(Ror2ItemDetailView),
          }),
        ),
      ),
    );

    expect(container?.querySelector("h1")?.textContent).toContain("一捆烟花");
    expect([...((container?.querySelectorAll("h2") ?? []) as NodeListOf<HTMLHeadingElement>)].map((heading) => heading.textContent)).toEqual([
      "简单描述",
      "详细描述",
      "日志",
    ]);
    expect(container?.textContent).toContain("日志译文");
    expect(container?.textContent).toContain("普通译文");
    expect(container?.textContent).toContain("线性译文");
    expect(container?.querySelectorAll('dd button[aria-label="查看对应的 Wiki 原文和 Weblate 令牌"]')).toHaveLength(2);
    expect(container?.querySelector('a[href="/guides/ror2/items?cat=Common"]')?.textContent).toContain("返回物品列表");
  });
});
