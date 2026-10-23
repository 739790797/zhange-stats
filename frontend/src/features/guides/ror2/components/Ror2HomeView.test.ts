/** @vitest-environment happy-dom */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Ror2Catalog, Ror2Item } from "../api/ror2Api";
import { Ror2HomeView } from "./Ror2HomeView";

const catalogMock = vi.hoisted(() => ({ useRor2Catalog: vi.fn() }));
vi.mock("../hooks/useRor2Catalog", () => ({ useRor2Catalog: catalogMock.useRor2Catalog }));

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const token = (text: string, original: string, context: string | null) => ({ text, original, token: context });
const item = {
  name: "Fireworks",
  rarity: "Common",
  quote: "A firework launcher.",
  description: "Launches fireworks.",
  lore: "",
  unlock: "",
  expansion: "",
  internal_name: "ITEM_FIREWORKS",
  code: "Fireworks",
  corrupt: "",
  uncorrupt: "",
  boss: "",
  cooldown: "",
  wiki_url: "https://riskofrain2.wiki.gg/wiki/Fireworks",
  image_url: "https://example.test/fireworks.png",
  categories: [],
  stats: [],
  localizedText: {
    name: token("一捆烟花", "Fireworks", "items.items.ITEM_FIREWORKS.name"),
    rarity: token("官方稀有度译文", "Common", "items.items.ITEM_FIREWORKS.Rarity"),
    quote: token("烟花发射器。", "A firework launcher.", "items.items.ITEM_FIREWORKS.Quote"),
    description: token("发射烟花。", "Launches fireworks.", "items.items.ITEM_FIREWORKS.Desc"),
    lore: token("", "", null),
    unlock: token("", "", null),
  },
} as unknown as Ror2Item;
const catalog = {
  items: [item],
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

describe("ROR2 home search results", () => {
  it("renders rarity from its Weblate token and exposes the source info trigger", async () => {
    await mount(
      createElement(
        MemoryRouter,
        { initialEntries: ["/guides/ror2?q=Fireworks"] },
        createElement(Ror2HomeView),
      ),
    );

    expect(container?.textContent).toContain("官方稀有度译文");
    expect(container?.textContent).not.toContain("普通");
    expect(container?.querySelectorAll('button[aria-label="查看对应的 Wiki 原文和 Weblate 令牌"]')).toHaveLength(4);
  });
});
