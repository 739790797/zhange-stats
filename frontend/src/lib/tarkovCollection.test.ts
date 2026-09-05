import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  COLLECTION_CAD_PX,
  COLLECTION_CELL_GAP_PX,
  COLLECTION_CELL_MAX_PX,
  COLLECTION_CELL_MIN_PX,
  COLLECTION_CELL_PAD_PX,
  COLLECTION_GRID_MAX_HEIGHT,
  COLLECTION_GRID_MAX_WIDTH,
  COLLECTION_GRID_MIN_HEIGHT,
  COLLECTION_GRID_MIN_WIDTH,
  collectionBoardCellSize,
  collectionViewGridSize,
  TARKOV_COLLECTION_LAYOUT_STORAGE_KEY,
  TARKOV_COLLECTION_OWNS_STORAGE_KEY,
  canPlaceCollectionItem,
  clearCollectionLayout,
  collectedIdsFromLayout,
  collectionDropCell,
  collectionExpandPreview,
  collectionGridSize,
  collectionGridSizeForPreview,
  findCollectionFit,
  collectionItemSize,
  collectionOccupiedBounds,
  collectionOwnedCount,
  filterCollectionItems,
  groupCollectionTrayItems,
  sortCollectionItemsByCells,
  layoutFromApi,
  layoutToApi,
  layoutToCollectionSlots,
  loadCollectionLayout,
  loadOwnedIds,
  moveCollectionItem,
  ownsDiff,
  parseCollectionLayout,
  parseOwnsState,
  pickCollectionLayoutSource,
  reconcileCollectionLayout,
  rotateCollectionDragGrab,
  rotateCollectionItem,
  saveCollectionLayout,
  saveOwnedIds,
  toggleCollectionItem,
} from "./tarkovCollection";

function item(
  id: string,
  size: { width?: number; height?: number; name?: string } = {},
) {
  return { id, name: size.name || id, width: size.width, height: size.height };
}

function layoutOf(
  ...rows: Array<{ itemId: string; col: number; row: number; rotated?: boolean }>
) {
  return { v: 2 as const, placements: rows };
}

describe("parseOwnsState", () => {
  it("reads per-mode lists and legacy owned as pvp", () => {
    expect(
      parseOwnsState(
        JSON.stringify({ v: 1, pvp: ["a"], pve: ["b", ""], owned: ["legacy"] }),
      ),
    ).toEqual({
      v: 1,
      pvp: ["a"],
      pve: ["b"],
      migrated: undefined,
    });
    expect(parseOwnsState(JSON.stringify({ v: 1, owned: ["x"] }))).toEqual({
      v: 1,
      pvp: ["x"],
      pve: [],
      migrated: undefined,
    });
    expect(parseOwnsState("nope")).toEqual({ v: 1, pvp: [], pve: [] });
  });
});

describe("owned storage", () => {
  const mem = new Map<string, string>();

  beforeEach(() => {
    mem.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: (key: string, value: string) => {
        mem.set(key, value);
      },
      removeItem: (key: string) => {
        mem.delete(key);
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps pvp and pve separate", () => {
    saveOwnedIds("pvp", ["a"]);
    saveOwnedIds("pve", ["b"]);
    expect(loadOwnedIds("pvp")).toEqual(["a"]);
    expect(loadOwnedIds("pve")).toEqual(["b"]);
    expect(mem.get(TARKOV_COLLECTION_OWNS_STORAGE_KEY)).toContain("a");
  });
});

describe("collectionBoardCellSize", () => {
  it("grows toward the pane, but keeps 14×14 fitting", () => {
    expect(collectionBoardCellSize(720, 640, 6, 6)).toBe(COLLECTION_CELL_MAX_PX);
    const fit14 = collectionBoardCellSize(720, 640, 14, 14);
    expect(fit14).toBeGreaterThan(1);
    expect(fit14).toBeLessThan(COLLECTION_CELL_MAX_PX);
    const innerW =
      720 - (COLLECTION_CAD_PX + 8 + COLLECTION_CELL_PAD_PX * 2 + 2);
    const innerH =
      640 - (COLLECTION_CAD_PX + COLLECTION_CELL_PAD_PX * 2 + 2);
    expect(fit14 * 14 + COLLECTION_CELL_GAP_PX * 13).toBeLessThanOrEqual(
      Math.min(innerW, innerH) + 1,
    );
  });

  it("shrinks below the preferred floor so a short pane still fits 14×14", () => {
    const cell = collectionBoardCellSize(80, 80, 14, 14);
    expect(cell).toBeGreaterThanOrEqual(1);
    expect(cell).toBeLessThan(COLLECTION_CELL_MIN_PX);
    const innerH =
      80 - (COLLECTION_CAD_PX + COLLECTION_CELL_PAD_PX * 2 + 2);
    expect(cell * 14 + COLLECTION_CELL_GAP_PX * 13).toBeLessThanOrEqual(innerH);
  });
});

describe("collection layout", () => {
  it("starts empty: everything uncollected, canvas is 3x3", () => {
    const items = [item("a"), item("b", { width: 2, height: 1 })];
    const layout = reconcileCollectionLayout(null, items);
    expect(layout.placements).toEqual([]);
    expect(layoutToCollectionSlots(layout, items).uncollected.map((row) => row.id)).toEqual(
      ["b", "a"],
    );
    expect(collectionGridSize(layout, items)).toEqual({
      cols: COLLECTION_GRID_MIN_WIDTH,
      rows: COLLECTION_GRID_MIN_HEIGHT,
    });
    expect(collectionOccupiedBounds(layout, items)).toEqual({
      width: 0,
      height: 0,
      used: 0,
      col0: 0,
      row0: 0,
    });
  });

  it("ignores the old boxed v1 layout", () => {
    const stale = {
      v: 1,
      boxIds: ["box-1"],
      placements: [{ itemId: "a", boxId: "box-1", col: 0, row: 0 }],
    };
    expect(parseCollectionLayout(stale)).toBeNull();
    expect(reconcileCollectionLayout(stale as never, [item("a")]).placements).toEqual(
      [],
    );
  });

  it("placing onto the grid collects; tray uncollects", () => {
    const items = [item("a"), item("b")];
    const empty = reconcileCollectionLayout(null, items);
    const placed = moveCollectionItem(empty, items, "a", {
      kind: "grid",
      col: 1,
      row: 2,
    });
    expect(placed?.placements).toEqual([{ itemId: "a", col: 1, row: 2 }]);
    expect(collectedIdsFromLayout(placed!)).toEqual(["a"]);
    const { slots, uncollected } = layoutToCollectionSlots(placed!, items);
    expect(slots).toHaveLength(1);
    expect(uncollected.map((row) => row.id)).toEqual(["b"]);
    const back = moveCollectionItem(placed!, items, "a", { kind: "tray" });
    expect(back?.placements).toEqual([]);
  });

  it("rejects overlap and negative cells, but not a 3x3 box wall", () => {
    const items = [item("a"), item("wide", { width: 2, height: 1 })];
    const layout = layoutOf({ itemId: "a", col: 0, row: 0 });
    expect(canPlaceCollectionItem(layout, items, "wide", 0, 0)).toBe(false);
    expect(canPlaceCollectionItem(layout, items, "wide", -1, 0)).toBe(false);
    const far = moveCollectionItem(layout, items, "wide", {
      kind: "grid",
      col: 4,
      row: 5,
    });
    expect(far?.placements.find((row) => row.itemId === "wide")).toMatchObject({
      col: 4,
      row: 5,
    });
    const overlap = moveCollectionItem(layout, items, "wide", {
      kind: "grid",
      col: 0,
      row: 0,
    });
    expect(overlap).toBeNull();
    expect(
      canPlaceCollectionItem(layout, items, "wide", COLLECTION_GRID_MAX_WIDTH - 1, 0),
    ).toBe(false);
  });

  it("grows the canvas around occupied cells and reports the bounding box", () => {
    const items = [
      item("a"),
      item("wide", { width: 2, height: 1 }),
      item("tall", { width: 1, height: 3 }),
    ];
    const layout = layoutOf(
      { itemId: "a", col: 0, row: 0 },
      { itemId: "wide", col: 3, row: 1 },
      { itemId: "tall", col: 1, row: 2 },
    );
    expect(collectionOccupiedBounds(layout, items)).toEqual({
      width: 5,
      height: 5,
      used: 1 + 2 + 3,
      col0: 0,
      row0: 0,
    });
    expect(collectionGridSize(layout, items)).toEqual({ cols: 6, rows: 6 });
  });

  it("previews a larger canvas only when the drop would expand it", () => {
    const items = [item("a"), item("wide", { width: 2, height: 1 })];
    const empty = layoutOf();
    expect(
      collectionExpandPreview(empty, items, { kind: "grid", col: 2, row: 0 }, "a"),
    ).toEqual({ cols: 4, rows: COLLECTION_GRID_MIN_HEIGHT });
    expect(
      collectionExpandPreview(empty, items, { kind: "grid", col: 0, row: 0 }, "a"),
    ).toBeNull();
    expect(
      collectionExpandPreview(empty, items, { kind: "tray" }, "a"),
    ).toBeNull();
    const packed = layoutOf({ itemId: "a", col: 0, row: 0 });
    expect(
      collectionExpandPreview(
        packed,
        items,
        { kind: "grid", col: 0, row: 0 },
        "wide",
      ),
    ).toBeNull();
  });

  it("grows the preview to reveal extra cells on a valid drop", () => {
    const items = [item("wide", { width: 2, height: 1 })];
    const empty = layoutOf();
    expect(
      collectionGridSizeForPreview(empty, items, { kind: "tray" }, "wide"),
    ).toEqual(collectionGridSize(empty, items));
    expect(
      collectionGridSizeForPreview(empty, items, null, "wide"),
    ).toEqual(collectionGridSize(empty, items));
    expect(
      collectionGridSizeForPreview(
        empty,
        items,
        { kind: "grid", col: 2, row: 2 },
        "wide",
        true,
      ),
    ).toEqual({ cols: 4, rows: 5 });
  });

  it("first-fit expands past a packed 3x3 when the item needs more cells", () => {
    const fillers = ["a", "b", "c", "d", "e", "f", "g", "h", "i"].map((id) =>
      item(id),
    );
    const items = [...fillers, item("big", { width: 2, height: 2 })];
    const packed = layoutOf(
      ...fillers.map((row, index) => ({
        itemId: row.id,
        col: index % 3,
        row: Math.floor(index / 3),
      })),
    );
    expect(collectionGridSize(packed, items)).toEqual({ cols: 4, rows: 4 });
    expect(findCollectionFit(packed, items, "big")).toEqual({
      col: 3,
      row: 0,
      rotated: false,
    });
  });

  it("caps the canvas at the 14x14 THICC / junkbox", () => {
    const items = [item("a")];
    const packed = layoutOf({ itemId: "a", col: 13, row: 13 });
    expect(collectionGridSize(packed, items)).toEqual({
      cols: COLLECTION_GRID_MAX_WIDTH,
      rows: COLLECTION_GRID_MAX_HEIGHT,
    });
    expect(COLLECTION_GRID_MAX_WIDTH).toBe(14);
    expect(COLLECTION_GRID_MAX_HEIGHT).toBe(14);
    expect(collectionViewGridSize()).toEqual({
      cols: COLLECTION_GRID_MAX_WIDTH,
      rows: COLLECTION_GRID_MAX_HEIGHT,
    });
  });

  it("rotates a 2x1 in place when the swap still fits", () => {
    const items = [item("wide", { width: 2, height: 1 }), item("a")];
    const layout = layoutOf(
      { itemId: "wide", col: 0, row: 0 },
      { itemId: "a", col: 2, row: 0 },
    );
    const rotated = rotateCollectionItem(layout, items, "wide");
    expect(rotated?.placements.find((row) => row.itemId === "wide")).toMatchObject({
      col: 0,
      row: 0,
      rotated: true,
    });
    const { slots } = layoutToCollectionSlots(rotated!, items);
    expect(slots.find((row) => row.item.id === "wide")).toMatchObject({
      width: 1,
      height: 2,
      rotated: true,
    });
    const blocked = layoutOf(
      { itemId: "wide", col: 0, row: 0 },
      { itemId: "a", col: 0, row: 1 },
    );
    expect(rotateCollectionItem(blocked, items, "wide")).toBeNull();
  });

  it("reconciles unknown ids and overlapping cells, but does not auto-place newcomers", () => {
    const stale = layoutOf(
      { itemId: "gone", col: 0, row: 0 },
      { itemId: "keep", col: 1, row: 0 },
      { itemId: "overlap", col: 1, row: 0 },
    );
    const items = [item("keep"), item("overlap"), item("new")];
    const next = reconcileCollectionLayout(stale, items);
    expect(next.placements.map((row) => row.itemId)).toEqual(["keep"]);
    expect(layoutToCollectionSlots(next, items).uncollected.map((row) => row.id)).toEqual(
      ["overlap", "new"],
    );
  });

  it("toggles between the tray and first-fit on the grid", () => {
    const items = [
      item("a"),
      item("b"),
      item("wide", { width: 2, height: 1 }),
    ];
    const empty = reconcileCollectionLayout(null, items);
    const one = toggleCollectionItem(empty, items, "a");
    expect(one?.placements).toEqual([{ itemId: "a", col: 0, row: 0 }]);
    const two = toggleCollectionItem(one!, items, "b");
    expect(two?.placements.find((row) => row.itemId === "b")).toMatchObject({
      col: 1,
      row: 0,
    });
    const wide = toggleCollectionItem(two!, items, "wide");
    expect(wide?.placements.find((row) => row.itemId === "wide")).toMatchObject({
      col: 2,
      row: 0,
    });
    const back = toggleCollectionItem(wide!, items, "a");
    expect(back?.placements.map((row) => row.itemId).sort()).toEqual([
      "b",
      "wide",
    ]);
    expect(toggleCollectionItem(empty, items, "wide", true)?.placements[0]).toMatchObject({
      col: 0,
      row: 0,
      rotated: true,
    });
    expect(toggleCollectionItem(empty, items, "missing")).toBeNull();
  });

  it("clears the grid back to the tray", () => {
    const items = [item("a")];
    expect(
      layoutToCollectionSlots(clearCollectionLayout(), items).uncollected,
    ).toEqual(items);
  });

  it("round-trips account layout payloads", () => {
    const parsed = layoutFromApi({
      placements: [
        { item_id: "a", col: 2, row: 3, rotated: true },
        { item_id: "a", col: 0, row: 0 },
      ],
    });
    expect(parsed?.placements).toEqual([{ itemId: "a", col: 2, row: 3, rotated: true }]);
    expect(layoutToApi(parsed!)).toEqual({
      placements: [{ item_id: "a", col: 2, row: 3, rotated: true }],
    });
    expect(layoutFromApi({ placements: [] })?.placements).toEqual([]);
    expect(layoutFromApi(null)).toBeNull();
  });

  it("maps a pointer to the item top-left cell on the live grid", () => {
    expect(collectionDropCell(4 + 64 + 2 + 10, 4 + 10, 64, 2, 4, 0, 0, 3, 3)).toEqual({
      col: 1,
      row: 0,
    });
    expect(collectionDropCell(4 + 10, 4 + 10, 64, 2, 4, 1, 0, 3, 3)).toEqual({
      col: -1,
      row: 0,
    });
    expect(collectionDropCell(4 + 3 * 66, 4 + 10, 64, 2, 4, 0, 0, 3, 3)).toBeNull();
    expect(collectionItemSize(item("wide", { width: 2, height: 1 }), true)).toEqual({
      width: 1,
      height: 2,
    });
    expect(COLLECTION_GRID_MIN_WIDTH).toBe(3);
    expect(COLLECTION_GRID_MIN_HEIGHT).toBe(3);
  });

  it("rotates the grab cell so the pointer stays on the same item cell", () => {
    const once = rotateCollectionDragGrab(2, 1, 1, 0, 70, 20, 50);
    expect(once).toEqual({
      width: 1,
      height: 2,
      anchorCol: 0,
      anchorRow: 1,
      grabX: 20,
      grabY: 70,
    });
    let loop = { width: 2, height: 1, anchorCol: 1, anchorRow: 0, grabX: 70, grabY: 20 };
    for (let i = 0; i < 4; i += 1) {
      loop = rotateCollectionDragGrab(
        loop.width,
        loop.height,
        loop.anchorCol,
        loop.anchorRow,
        loop.grabX,
        loop.grabY,
        50,
      );
    }
    expect(loop).toEqual({
      width: 2,
      height: 1,
      anchorCol: 1,
      anchorRow: 0,
      grabX: 70,
      grabY: 20,
    });
  });
});

describe("collection layout storage", () => {
  const mem = new Map<string, string>();

  beforeEach(() => {
    mem.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: (key: string, value: string) => {
        mem.set(key, value);
      },
      removeItem: (key: string) => {
        mem.delete(key);
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps pvp and pve layouts separate", () => {
    saveCollectionLayout("pvp", layoutOf({ itemId: "a", col: 0, row: 0 }));
    saveCollectionLayout(
      "pve",
      layoutOf({ itemId: "b", col: 1, row: 0 }, { itemId: "c", col: 2, row: 1 }),
    );
    expect(loadCollectionLayout("pvp")?.placements.map((row) => row.itemId)).toEqual(
      ["a"],
    );
    expect(loadCollectionLayout("pve")?.placements).toHaveLength(2);
    expect(mem.get(TARKOV_COLLECTION_LAYOUT_STORAGE_KEY)).not.toContain("box-1");
  });

  it("flattens a leftover container layout onto the expanding grid", () => {
    mem.set(
      "zhange.guides.tarkov.collectionLayout.v3",
      JSON.stringify({
        v: 3,
        pvp: {
          v: 3,
          boxes: [{ id: "box-1", catalogId: "item-case" }],
          placements: [{ itemId: "a", boxId: "box-1", col: 2, row: 3 }],
        },
      }),
    );
    expect(loadCollectionLayout("pvp")?.placements).toEqual([
      { itemId: "a", col: 2, row: 3 },
    ]);
  });

  it("keeps an emptied v2 grid over leftover v3 boxes", () => {
    mem.set(
      "zhange.guides.tarkov.collectionLayout.v3",
      JSON.stringify({
        v: 3,
        pvp: {
          v: 3,
          boxes: [{ id: "box-1", catalogId: "item-case" }],
          placements: [{ itemId: "a", boxId: "box-1", col: 2, row: 3 }],
        },
      }),
    );
    saveCollectionLayout("pvp", clearCollectionLayout());
    expect(loadCollectionLayout("pvp")?.placements).toEqual([]);
    expect(mem.get("zhange.guides.tarkov.collectionLayout.v3")).toBeUndefined();
  });
});

describe("pickCollectionLayoutSource", () => {
  const local = layoutOf({ itemId: "local", col: 0, row: 0 });
  const remote = layoutOf({ itemId: "remote", col: 1, row: 1 });

  it("trusts a saved empty remote over leftover local cells", () => {
    expect(
      pickCollectionLayoutSource({
        saved: true,
        remote: clearCollectionLayout(),
        local,
      }),
    ).toEqual({ layout: clearCollectionLayout(), migrateLocal: false });
  });

  it("migrates local cells only when the account has never saved", () => {
    expect(
      pickCollectionLayoutSource({
        saved: false,
        remote: clearCollectionLayout(),
        local,
      }),
    ).toEqual({ layout: local, migrateLocal: true });
  });

  it("does not upload leftover local cells when the server is unknown", () => {
    expect(
      pickCollectionLayoutSource({
        remote: null,
        local,
      }),
    ).toEqual({ layout: local, migrateLocal: false });
  });

  it("uses a saved remote layout even when local still has other cells", () => {
    expect(
      pickCollectionLayoutSource({
        saved: true,
        remote,
        local,
      }),
    ).toEqual({ layout: remote, migrateLocal: false });
  });
});

describe("filter and count", () => {
  const items = [item("a", { name: "金色打火机" }), item("b", { name: "古币" })];

  it("filters the tray by query", () => {
    expect(filterCollectionItems(items, "古").map((row) => row.id)).toEqual([
      "b",
    ]);
    expect(filterCollectionItems(items, "").map((row) => row.id)).toEqual([
      "a",
      "b",
    ]);
  });

  it("groups the tray by occupied cell count, largest first", () => {
    const mixed = [
      { id: "gpu", name: "显卡", width: 2, height: 1 },
      { id: "lion", name: "青铜狮", width: 2, height: 2 },
      { id: "pack", name: "背包", width: 4, height: 5 },
      { id: "mystery", name: "未知", width: 1, height: 1 },
    ];
    expect(
      groupCollectionTrayItems(mixed).map((group) => ({
        label: group.label,
        ids: group.items.map((row) => row.id),
      })),
    ).toEqual([
      { label: "20格", ids: ["pack"] },
      { label: "4格", ids: ["lion"] },
      { label: "2格", ids: ["gpu"] },
      { label: "1格", ids: ["mystery"] },
    ]);
  });

  it("puts same-cell shapes in one group and keeps input order", () => {
    const same = [
      item("mid-a", { width: 2, height: 2 }),
      item("mid-b", { width: 4, height: 1 }),
    ];
    expect(
      groupCollectionTrayItems(same).map((group) => ({
        label: group.label,
        ids: group.items.map((row) => row.id),
      })),
    ).toEqual([{ label: "4格", ids: ["mid-a", "mid-b"] }]);
  });

  it("sorts tray items by occupied cells, largest first", () => {
    const mixed = [
      item("small", { width: 1, height: 1 }),
      item("wide", { width: 3, height: 2 }),
      item("mid-a", { width: 2, height: 2 }),
      item("mid-b", { width: 4, height: 1 }),
    ];
    expect(sortCollectionItemsByCells(mixed).map((row) => row.id)).toEqual([
      "wide",
      "mid-a",
      "mid-b",
      "small",
    ]);
    expect(
      filterCollectionItems(mixed, "").map((row) => row.id),
    ).toEqual(["wide", "mid-a", "mid-b", "small"]);
  });

  it("counts collected against the full list", () => {
    expect(collectionOwnedCount(items, new Set(["a", "missing"]))).toEqual({
      have: 1,
      total: 2,
    });
    expect(ownsDiff(["a", "b"], ["b", "c"])).toEqual({
      add: ["c"],
      remove: ["a"],
    });
  });
});
