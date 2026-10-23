import { describe, expect, it } from "vitest";
import { parseRor2RichText, ror2RichTextPlain } from "./ror2RichText";

const WISP =
  "每击杀<style=cIsDamage>5</style>名敌人，获得一个临时<style=cIsDamage>环绕灵体</style>，协同你攻击最多<style=cIsUtility>3<style=cStack>（每层+1）</style></style>次";

describe("ror2 rich text", () => {
  it("keeps the game damage color and the placeholder", () => {
    expect(parseRor2RichText("传送（<style=cIsDamage>{0}%</style>）")).toEqual([
      { type: "text", text: "传送（" },
      { type: "color", color: "#e5c962", children: [{ type: "text", text: "{0}%" }] },
      { type: "text", text: "）" },
    ]);
  });

  it("nests the stack color inside the utility color", () => {
    const nodes = parseRor2RichText(WISP);
    const nested = nodes.find((node) => node.type === "color" && node.color === "#95cde5");
    expect(nested).toMatchObject({
      type: "color",
      color: "#95cde5",
      children: [
        { type: "text", text: "3" },
        {
          type: "color",
          color: "#8990a7",
          children: [{ type: "text", text: "（每层+1）" }],
        },
      ],
    });
    expect(ror2RichTextPlain(WISP)).toContain("环绕灵体");
    expect(ror2RichTextPlain(WISP)).not.toContain("cIsDamage");
  });

  it("folds mistyped style names and closes a missing tag", () => {
    expect(parseRor2RichText("<style=cIsutility>迅捷</style>")).toEqual([
      { type: "color", color: "#95cde5", children: [{ type: "text", text: "迅捷" }] },
    ]);
    expect(parseRor2RichText("<style=cIsDamage>15%")).toEqual([
      { type: "color", color: "#e5c962", children: [{ type: "text", text: "15%" }] },
    ]);
    expect(ror2RichTextPlain("防止</style><style=cIsHealing>屏障</style>")).toBe("防止屏障");
  });

  it("uses the stylesheet brackets for keyword names and drops sprite tags", () => {
    expect(parseRor2RichText("<style=cKeywordName>纠缠</style>")).toEqual([
      { type: "bold", children: [{ type: "text", text: "[ 纠缠 ]" }] },
    ]);
    expect(ror2RichTextPlain('找到10个。<sprite name="WIP">未完成')).toBe("找到10个。未完成");
  });

  it("covers every text style that shows up in the language files", () => {
    const names = [
      "cIsDamage",
      "cIsUtility",
      "cStack",
      "cIsHealing",
      "cMono",
      "cSub",
      "cWorldEvent",
      "cIsHealth",
      "cKeywordName",
      "cDeath",
      "cIsVoid",
      "cUserSetting",
      "cShrine",
      "cEvent",
      "cHumanObjective",
      "cLunarObjective",
      "cArtifact",
      "cIsTemporary",
      "cIsLunar",
      "cIsTierBoss",
      "cIsRental",
    ];
    for (const name of names) {
      const nodes = parseRor2RichText(`<style=${name}>x</style>`);
      expect(nodes.some((node) => node.type !== "text"), name).toBe(true);
      expect(ror2RichTextPlain(`<style=${name}>x</style>`)).toContain("x");
    }
  });

  it("colors wiki shortcuts that are not game style names", () => {
    expect(parseRor2RichText("{{Color|hallowed|Hallowed}}")).toEqual([
      { type: "color", color: "#9368f9", children: [{ type: "text", text: "Hallowed" }] },
    ]);
    expect(parseRor2RichText("{{Color|lunar|Lunar}}")).toEqual([
      { type: "color", color: "#307fff", children: [{ type: "text", text: "Lunar" }] },
    ]);
    expect(parseRor2RichText("{{Color|#FF7F7F|BUT}}")).toEqual([
      { type: "color", color: "#ff7f7f", children: [{ type: "text", text: "BUT" }] },
    ]);
    expect(parseRor2RichText("<style=cSub><size=80%>信息</size></style>")).toEqual([
      {
        type: "color",
        color: "#ccd3e0",
        children: [{ type: "size", size: "80%", children: [{ type: "text", text: "信息" }] }],
      },
    ]);
  });

  it("keeps sprite names inside the surrounding words", () => {
    expect(parseRor2RichText('穿过<style=cDeath>传送器<sprite name="TP" tint=1></style>')).toEqual([
      { type: "text", text: "穿过" },
      {
        type: "color",
        color: "#fe7c7c",
        children: [
          { type: "text", text: "传送器" },
          { type: "sprite", name: "TP" },
        ],
      },
    ]);
    expect(ror2RichTextPlain('找到10个。<sprite name="WIP">未完成')).toBe("找到10个。未完成");
  });

  it("keeps wiki color tags that already name a hex", () => {
    expect(parseRor2RichText("<u><color=#E5C962>underlined</color></u>")).toEqual([
      {
        type: "underline",
        children: [{ type: "color", color: "#e5c962", children: [{ type: "text", text: "underlined" }] }],
      },
    ]);
  });
});
