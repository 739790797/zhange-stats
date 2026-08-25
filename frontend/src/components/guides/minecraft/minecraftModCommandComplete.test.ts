import { describe, expect, it } from "vitest";
import {
  applySuggestionLine,
  completeLine,
  parseCommandLine,
  suggestionsForLine,
  type CommandNodeSpec,
} from "./minecraftModCommandComplete";

const TREE: CommandNodeSpec[] = [
  { id: "world", args: [{ id: "world", kind: "world" }] },
  {
    id: "shape",
    args: [
      {
        id: "shape",
        kind: "enum",
        options: [
          { value: "square" },
          { value: "circle" },
          { value: "diamond" },
        ],
      },
    ],
  },
  {
    id: "center",
    args: [
      { id: "x", kind: "int" },
      { id: "z", kind: "int" },
    ],
  },
  {
    id: "worldborder",
    args: [{ id: "world", kind: "world", optional: true }],
  },
  { id: "spawn" },
  { id: "trim", confirm: "会删除范围外区块" },
];

const WORLDS = ["world", "minecraft:overworld", "minecraft:the_nether"];

describe("suggestionsForLine", () => {
  it("lists first-level commands on empty / click preview", () => {
    expect(suggestionsForLine("", TREE, WORLDS).map((row) => row.token)).toEqual(
      ["world", "shape", "center", "worldborder", "spawn", "trim"],
    );
  });

  it("filters first-level commands while typing", () => {
    expect(
      suggestionsForLine("wo", TREE, WORLDS).map((row) => row.token),
    ).toEqual(["world", "worldborder"]);
  });

  it("suggests world names after a completed command", () => {
    expect(
      suggestionsForLine("world ", TREE, WORLDS).map((row) => row.token),
    ).toEqual(WORLDS);
    expect(
      suggestionsForLine("world minecraft:", TREE, WORLDS).map((row) => row.line),
    ).toEqual(["world minecraft:overworld", "world minecraft:the_nether"]);
  });

  it("suggests raw enum values, not translated labels", () => {
    expect(
      suggestionsForLine("shape c", TREE, WORLDS).map((row) => row.token),
    ).toEqual(["circle"]);
  });
});

describe("completeLine", () => {
  it("completes a unique prefix and advances to the next argument", () => {
    expect(completeLine("sh", TREE, WORLDS)).toBe("shape ");
    expect(completeLine("spa", TREE, WORLDS)).toBe("spawn");
  });

  it("completes the shared prefix when several commands match", () => {
    expect(completeLine("w", TREE, WORLDS)).toBe("world");
  });

  it("advances into required arguments on Tab", () => {
    expect(completeLine("world", TREE, WORLDS)).toBe("world ");
  });

  it("tabs through argument choices", () => {
    expect(completeLine("shape ", TREE, WORLDS)).toBe("shape square");
    expect(completeLine("shape square", TREE, WORLDS)).toBe("shape circle");
  });
});

describe("parseCommandLine", () => {
  it("parses command id and typed arguments", () => {
    expect(parseCommandLine("world minecraft:the_nether", TREE)).toEqual({
      commandId: "world",
      args: { world: "minecraft:the_nether" },
    });
    expect(parseCommandLine("center 32 -64", TREE)).toEqual({
      commandId: "center",
      args: { x: 32, z: -64 },
    });
    expect(parseCommandLine("worldborder", TREE)).toEqual({
      commandId: "worldborder",
      args: {},
    });
    expect(parseCommandLine("trim", TREE)).toEqual({
      commandId: "trim",
      args: {},
    });
  });

  it("rejects incomplete or unknown lines", () => {
    expect(parseCommandLine("", TREE)).toEqual({ error: "输入指令" });
    expect(parseCommandLine("nope", TREE)).toEqual({ error: "不支持的指令" });
    expect(parseCommandLine("world", TREE)).toEqual({ error: "缺少 world" });
    expect(parseCommandLine("shape oval", TREE)).toEqual({
      error: "不支持的 shape",
    });
  });
});

describe("applySuggestionLine", () => {
  it("adds a trailing space only when the next argument is required", () => {
    expect(applySuggestionLine("world", TREE)).toBe("world ");
    expect(applySuggestionLine("spawn", TREE)).toBe("spawn");
    expect(applySuggestionLine("worldborder", TREE)).toBe("worldborder");
  });
});
