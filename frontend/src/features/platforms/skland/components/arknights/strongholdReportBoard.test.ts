/** @vitest-environment jsdom */
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  StrongholdMatch,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";
import { StrongholdReportBoard } from "./StrongholdReportBoard";

const scope = {
  season_id: "s1",
  season_label: "规程",
  mode_type: "multi" as const,
  difficulty_id: "abyss",
  difficulty_label: "终极模拟",
};
const ended_at = "2026-11-27T01:33:41+08:00";
const primary: StrongholdRecordDetail = {
  ...scope,
  id: "first",
  match_id: "sample",
  ended_at,
  completed: false,
  pass_round: 15,
  strategy_id: null,
  strategy_name: null,
  is_own: true,
  role_name: "样例博士",
  battle: {
    started_at: "2026-11-27T00:43:01+08:00",
    trophy_before: 317,
    trophy_after: 325,
    kill_count: 197,
    coin_cost: 177,
    sync_count: 11,
    bosses: [{ id: "test-boss", name: "示例首领", hidden: false, killed: true }],
  },
  roster: [
    {
      id: "sample-golden",
      normal_chess_id: "sample-normal",
      char_id: "char_sample",
      phase: 2,
      is_elite: true,
      profession: "SNIPER",
      branch_id: "fastshot",
      branch_name: "速射手",
      name: "干员甲",
      level: 60,
      tier: 3,
      merge_level: 1,
      traits: [{ id: "trait", name: "持续叠加" }],
      skill_id: "skill",
      skill: { name: "技能甲" },
      module_id: "module",
      module: { name: "模组甲" },
      equipment: [
        {
          id: "gear1",
          name: "装备甲",
          icon_url: "/example-item.png",
          description: "示例装备的详情",
        },
        { id: "gear2", name: "装备乙" },
        { id: "gear3", name: "装备丙" },
      ],
    },
  ],
  bonds: [{ bond_id: "active", name: "盟约甲", active: true, layer: 0 }],
  available_bonds: [
    {
      bond_id: "inactive",
      name: "盟约乙",
      active: false,
      operators: [{ id: "sample-normal", char_id: "char_sample" }],
    },
  ],
};
const match: StrongholdMatch = {
  ...scope,
  id: "sample",
  ended_at,
  success: true,
  participants: [],
  my_record_id: "first",
  views: [
    primary,
    {
      ...primary,
      id: "second",
      is_own: false,
      pass_round: 11,
      role_name: "协作视角",
      roster: [],
      bonds: null,
    },
  ],
};

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

function mount(value = match) {
  act(() =>
    root.render(createElement(StrongholdReportBoard, { match: value, requestedView: null })),
  );
}

function button(label: string, scope: ParentNode = host) {
  const element = [...scope.querySelectorAll("button")].find(
    (item) => item.getAttribute("aria-label") === label || item.textContent?.includes(label),
  );
  if (!element) throw new Error(`Missing button: ${label}`);
  return element;
}

function pointerOver(element: Element) {
  const event = new MouseEvent("pointerover", { bubbles: true });
  Object.defineProperty(event, "pointerType", { value: "mouse" });
  act(() => element.dispatchEvent(event));
}

describe("Stronghold report detail", () => {
  it("puts the group result on the round row and switches all sections when the player changes", () => {
    mount();
    const overview = host.querySelector('section[aria-label="对局信息"]')!;
    const roster = host.querySelector('section[aria-label="出战干员"]')!;
    expect(
      [...host.querySelectorAll("aside[aria-label], section[aria-label]")].map(
        (section) => section.ariaLabel,
      ),
    ).toEqual(["对局玩家", "对局信息", "盟约", "出战干员"]);
    expect(host.querySelectorAll('aside[aria-label="对局玩家"] ol > li')).toHaveLength(4);
    expect(overview.querySelector("dl > div")?.textContent).toBe("通过回合15模拟完成");
    expect(overview.textContent).toContain("用时50 分 40 秒");
    expect(overview.textContent).toContain("+8317 → 325");
    expect(overview.textContent).toContain("普通首领示例首领已击杀");
    expect(host.textContent).not.toMatch(/同步次数|其他战斗记录/);
    expect(roster.querySelectorAll("ul > li")).toHaveLength(10);
    expect(roster.textContent?.match(/空位/g)).toHaveLength(9);
    expect(host.querySelector('section[aria-label="盟约"]')?.textContent).toContain("盟约甲0");
    expect(button("盟约乙，本局未点亮", roster)).toBeTruthy();
    const teammate = button("协作视角");
    const controlledPanels = teammate
      .getAttribute("aria-controls")!
      .split(" ")
      .map((id) => document.getElementById(id));
    expect(controlledPanels[0]?.contains(overview)).toBe(true);
    expect(controlledPanels[1]).toBe(roster);
    act(() => teammate.click());
    expect(host.querySelector('section[aria-label="对局信息"] dl > div')?.textContent).toBe(
      "通过回合11模拟完成",
    );
    expect(host.textContent).toContain("盟约数据暂不可用");
    expect(host.textContent).toContain("该视角没有出战干员");
  });

  it("keeps equipment off the closed card and opens a separate effect bubble from the drawer", () => {
    mount({ ...match, success: false });
    expect(host.querySelector('section[aria-label="对局信息"] dl > div')?.textContent).toBe(
      "通过回合15模拟中断",
    );
    const trigger = button("查看干员甲的出战详情");
    const drawer = document.getElementById(trigger.getAttribute("aria-controls")!)!;
    expect(drawer.getAttribute("aria-hidden")).toBe("true");
    expect(drawer.inert).toBe(true);
    act(() => trigger.click());
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(drawer.inert).toBe(false);
    expect([...drawer.querySelectorAll("dt")].map((element) => element.textContent)).toEqual([
      "特质",
      "技能",
      "模组",
      "装备",
    ]);
    expect(drawer.querySelectorAll('button[aria-label^="装备："]')).toHaveLength(3);
    expect(drawer.textContent).toContain("速射手");
    expect(drawer.textContent).not.toContain("合成");

    const equipment = button("装备：装备甲", drawer);
    pointerOver(equipment);
    const bubble = document.getElementById(equipment.getAttribute("aria-controls")!)!;
    expect(bubble.textContent).toContain("示例装备的详情");
    expect(bubble.querySelector('img[src="/example-item.png"]')).not.toBeNull();
    act(() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })));
    expect(equipment.getAttribute("aria-expanded")).toBe("false");
    act(() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })));
    expect(drawer.inert).toBe(true);
  });
});
