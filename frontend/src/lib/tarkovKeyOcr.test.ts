import { describe, expect, it } from "vitest";
import {
  flattenKeyPackKeys,
  matchKeysFromOcr,
  parseKeyOcrTokens,
} from "./tarkovKeyOcr";

const catalog = [
  { id: "114", name: "宿舍 114 钥匙", short_name: "114" },
  { id: "214", name: "宿舍 214 钥匙", short_name: "214" },
  { id: "rbst", name: "RB-ST 钥匙", short_name: "RB-ST" },
  { id: "cottage", name: "海岸线别墅钥匙", short_name: "Cottage" },
  { id: "e108", name: "疗养院东楼 108 钥匙", short_name: "东 108" },
  { id: "w108", name: "疗养院西楼 108 钥匙", short_name: "西 108" },
  { id: "factory", name: "工厂紧急出口钥匙", short_name: "Factory" },
];

describe("parseKeyOcrTokens", () => {
  it("keeps short codes and drops UI noise", () => {
    const tokens = parseKeyOcrTokens(`钥匙工具
RB-ST
114
40/40
1x1
搜索`);
    expect(tokens).toContain("RB-ST");
    expect(tokens).toContain("114");
    expect(tokens.some((row) => /40\/40/.test(row))).toBe(false);
    expect(tokens).not.toContain("搜索");
  });

  it("splits compact latin codes", () => {
    expect(parseKeyOcrTokens("RBST Cottage")).toEqual(
      expect.arrayContaining(["RBST", "Cottage"]),
    );
  });

  it("joins stacked color-card glyphs and repairs west-wing OCR", () => {
    const tokens = parseKeyOcrTokens(`绿
卡
画203
Wi222
10/10
110/10)`);
    expect(tokens).toContain("绿卡");
    expect(tokens).toContain("西203");
    expect(tokens).toContain("西222");
    expect(tokens).not.toContain("110");
    expect(tokens).not.toContain("10");
  });
});

describe("flattenKeyPackKeys", () => {
  it("dedupes ids across packs", () => {
    expect(
      flattenKeyPackKeys([
        { keys: [catalog[0], catalog[2]] },
        { keys: [catalog[2], catalog[3]] },
      ]).map((row) => row.id),
    ).toEqual(["114", "rbst", "cottage"]);
  });
});

describe("matchKeysFromOcr", () => {
  it("matches exact short names", () => {
    expect(
      matchKeysFromOcr({
        tokens: ["114", "RB-ST"],
        catalog,
      }).map((row) => row.id),
    ).toEqual(["114", "rbst"]);
  });

  it("matches hyphenless short codes", () => {
    expect(
      matchKeysFromOcr({ tokens: ["RBST"], catalog }).map((row) => row.id),
    ).toEqual(["rbst"]);
  });

  it("does not map 114 onto 214", () => {
    expect(
      matchKeysFromOcr({ tokens: ["114"], catalog }).map((row) => row.id),
    ).toEqual(["114"]);
  });

  it("restricts matches to icon-collision candidates", () => {
    expect(
      matchKeysFromOcr({
        tokens: ["114"],
        catalog,
        allowIds: ["214"],
      }).map((row) => row.id),
    ).toEqual([]);
    expect(
      matchKeysFromOcr({
        tokens: ["114"],
        catalog,
        allowIds: ["114", "214"],
      }).map((row) => row.id),
    ).toEqual(["114"]);
  });

  it("skips ambiguous room numbers shared by two keys", () => {
    expect(
      matchKeysFromOcr({ tokens: ["108"], catalog }).map((row) => row.id),
    ).toEqual([]);
    expect(
      matchKeysFromOcr({ tokens: ["东 108"], catalog }).map((row) => row.id),
    ).toEqual(["e108"]);
  });

  it("matches Chinese full names", () => {
    expect(
      matchKeysFromOcr({
        texts: ["海岸线别墅钥匙"],
        catalog,
      }).map((row) => row.id),
    ).toEqual(["cottage"]);
  });

  it("accepts unique fuzzy short-code typo", () => {
    const hits = matchKeysFromOcr({ tokens: ["RB-5T"], catalog });
    expect(hits.map((row) => row.id)).toEqual(["rbst"]);
    expect(hits[0]?.confidence).toBe("fuzzy");
  });

  it("ignores generic key words", () => {
    expect(matchKeysFromOcr({ tokens: ["钥匙", "Key"], catalog })).toEqual([]);
  });

  it("reads inventory-style OCR dump", () => {
    const raw = `钥匙工具
114 Key
RB-ST
Cottage
Factory
40/40`;
    expect(
      matchKeysFromOcr({ texts: [raw], catalog }).map((row) => row.id),
    ).toEqual(["114", "rbst", "cottage", "factory"]);
  });
});

describe("keybox screenshot rules", () => {
  const keyboxCatalog = [
    { id: "blue", name: "实验室钥匙卡·蓝", short_name: "蓝卡" },
    { id: "yellow", name: "实验室钥匙卡·黄", short_name: "黄卡" },
    { id: "green", name: "实验室钥匙卡·绿", short_name: "绿卡" },
    { id: "red", name: "实验室钥匙卡·红", short_name: "红卡" },
    { id: "314", name: "宿舍楼 314 房间符号钥匙", short_name: "314钥匙" },
    { id: "e314", name: "疗养院东楼 314 房间钥匙", short_name: "东314" },
    { id: "cardinal", name: "Cardinal 公寓钥匙", short_name: "Cardinal" },
    { id: "w203", name: "疗养院西楼 203 房间钥匙", short_name: "西203" },
    { id: "d203", name: "宿舍203房间钥匙", short_name: "203钥匙" },
    { id: "w222", name: "疗养院西楼 222 房间钥匙", short_name: "西222" },
    { id: "e222", name: "疗养院东楼 222 房间钥匙", short_name: "东222" },
    { id: "chek13", name: "神秘房间符号钥匙", short_name: "Chek. 13" },
    { id: "chek15", name: "Chekannaya 15号公寓钥匙", short_name: "Chek. 15" },
    { id: "11sr", name: "Object #11SR 钥匙卡", short_name: "#11SR" },
    { id: "black", name: "实验室钥匙卡·黑", short_name: "黑卡" },
    { id: "purple", name: "实验室钥匙卡·紫", short_name: "紫卡" },
    { id: "blank", name: "空白 RFID 钥匙卡", short_name: "空白" },
    { id: "rbvo", name: "RB-VO 符号钥匙", short_name: "RB-VO" },
    { id: "rbao", name: "RB-AO 钥匙", short_name: "RB-AO" },
    { id: "plant", name: "TerraGroup 仓库钥匙卡", short_name: "化工厂" },
    { id: "living", name: "TerraGroup 实验室生活区钥匙卡", short_name: "生活区" },
    { id: "ssk", name: "Shturman 的储物箱钥匙", short_name: "SSK" },
    { id: "rbbk", name: "RB-BK 符号钥匙", short_name: "RB-BK" },
    { id: "abandoned", name: "废弃工厂符号钥匙", short_name: "废弃工厂" },
    { id: "factory", name: "工厂紧急出口钥匙", short_name: "工厂" },
    { id: "aspect", name: "Aspect 公司办公区钥匙", short_name: "Aspect" },
    { id: "goshan", name: "Goshan收银机钥匙", short_name: "Goshan" },
    { id: "d110", name: "宿舍110房间钥匙", short_name: "110钥匙" },
    { id: "mp13", name: "RB-MP13钥匙", short_name: "RB-MP13" },
    { id: "apt20", name: "Zmeevsky 5公寓20号钥匙", short_name: "公寓20" },
    { id: "office", name: "公司主管办公室钥匙", short_name: "主管办" },
    { id: "rusty", name: "生锈的带血钥匙", short_name: "生锈钥匙" },
    { id: "w301", name: "疗养院西楼 301 房间钥匙", short_name: "西301" },
    { id: "rbrh", name: "RB-RH钥匙", short_name: "RB-RH" },
    { id: "rbpkpm", name: "RB-PKPM 符号钥匙", short_name: "RB-PKPM" },
    { id: "rbpsp2", name: "RB-PSP2钥匙", short_name: "RB-PSP2" },
    { id: "admin", name: "公寓管理员钥匙", short_name: "管理员钥匙" },
    { id: "admin2", name: "管理员钥匙", short_name: "管理员" },
    { id: "gas", name: "加油站商店钥匙", short_name: "加油站" },
    { id: "customs", name: "海关 Tarcone 主管办公室钥匙", short_name: "海关物流" },
    { id: "d118", name: "宿舍118房间钥匙", short_name: "118钥匙" },
    { id: "d218", name: "宿舍218房间钥匙", short_name: "218钥匙" },
    { id: "d104", name: "宿舍104房间钥匙", short_name: "104钥匙" },
  ];

  const keyboxOcr = `P 钥匙箱
Z
绿
卡
10/10
110/10)
画203
画223|
314铂是
Candinal
废弃工厂
Chek.13
化工月
化工厂
RB-BK
SSK
生活区|
蓝卡
黄卡
红卡|
Wi222
AS
go
20/20`;

  it("keeps real keybox shorts and drops durability false positives", () => {
    const hits = matchKeysFromOcr({
      texts: [keyboxOcr],
      catalog: keyboxCatalog,
    }).map((row) => row.id);
    expect(hits).toEqual(
      expect.arrayContaining([
        "blue",
        "yellow",
        "green",
        "red",
        "314",
        "cardinal",
        "w203",
        "w222",
        "chek13",
        "plant",
        "living",
        "ssk",
        "rbbk",
        "abandoned",
      ]),
    );
    expect(hits).not.toContain("d203");
    expect(hits).not.toContain("e314");
    expect(hits).not.toContain("chek15");
    expect(hits).not.toContain("mp13");
    expect(hits).not.toContain("apt20");
    expect(hits).not.toContain("d110");
    expect(hits).not.toContain("aspect");
    expect(hits).not.toContain("goshan");
    expect(hits).not.toContain("factory");
  });

  it("does not promote bare room numbers or generic 工厂", () => {
    const hits = matchKeysFromOcr({
      tokens: ["西203", "203", "废弃工厂", "工厂", "314铂是"],
      words: [
        { text: "203", confidence: 80 },
        { text: "工厂", confidence: 80 },
      ],
      catalog: keyboxCatalog,
    }).map((row) => row.id);
    expect(hits).toEqual(expect.arrayContaining(["w203", "abandoned", "314"]));
    expect(hits).not.toContain("d203");
    expect(hits).not.toContain("factory");
  });

  it("repairs keybox OCR for black card, blank card, and #11SR", () => {
    const hits = matchKeysFromOcr({
      tokens: ["傅卡", "空自", "#1SR|", "RB3VO|", "W203", "RBaVvO", "Enak 13"],
      catalog: keyboxCatalog,
    }).map((row) => row.id);
    expect(hits).toEqual(
      expect.arrayContaining([
        "black",
        "blank",
        "11sr",
        "rbvo",
        "w203",
        "chek13",
      ]),
    );
    expect(hits).not.toContain("purple");
    expect(hits).not.toContain("rbao");
    expect(hits).not.toContain("chek15");
  });

  it("does not remap a used short code onto a neighbor", () => {
    expect(
      matchKeysFromOcr({
        tokens: ["RB-VO", "RB-VO"],
        catalog: keyboxCatalog,
      }).map((row) => row.id),
    ).toEqual(["rbvo"]);
  });

  it("does not guess RB-VO from ambiguous RBavO", () => {
    expect(
      matchKeysFromOcr({ tokens: ["RBavO"], catalog: keyboxCatalog }).map(
        (row) => row.id,
      ),
    ).toEqual([]);
  });

  it("repairs 蛇卡、生锈残字、H301 and RB shorts", () => {
    const hits = matchKeysFromOcr({
      tokens: ["蛇卡", "生锈乌几", "H301)", "RBzsRH", "RB=PKRR", "RB-RSsP2", "管理员铂是", "加油关", "海关移消"],
      catalog: keyboxCatalog,
    }).map((row) => row.id);
    expect(hits).toEqual(
      expect.arrayContaining(["red", "rusty", "w301", "rbrh", "rbpkpm", "rbpsp2", "admin", "gas", "customs"]),
    );
    expect(hits).not.toContain("admin2");
  });

  it("does not promote 104便局 or 118 after 218", () => {
    const hits = matchKeysFromOcr({
      tokens: ["218钥此", "118钥此", "104便局"],
      catalog: keyboxCatalog,
    }).map((row) => row.id);
    expect(hits).toContain("d218");
    expect(hits).not.toContain("d118");
    expect(hits).not.toContain("d104");
  });

  it("does not treat bare 管理员 as a key", () => {
    expect(
      matchKeysFromOcr({ tokens: ["管理员"], catalog: keyboxCatalog }).map((row) => row.id),
    ).toEqual([]);
    expect(
      matchKeysFromOcr({ tokens: ["管理员钥匙"], catalog: keyboxCatalog }).map((row) => row.id),
    ).toEqual(["admin"]);
  });

  it("repairs 管办 onto 主管办", () => {
    expect(
      matchKeysFromOcr({ tokens: ["管办"], catalog: keyboxCatalog }).map((row) => row.id),
    ).toEqual(["office"]);
  });

  it("does not map durability leftovers or off-by-one rooms", () => {
    const roomCatalog = [
      { id: "104", name: "宿舍104房间钥匙", short_name: "104钥匙" },
      { id: "105", name: "宿舍105房间钥匙", short_name: "105钥匙" },
      { id: "218", name: "宿舍218房间钥匙", short_name: "218钥匙" },
      { id: "220", name: "宿舍220房间钥匙", short_name: "220钥匙" },
      { id: "314", name: "宿舍楼 314 房间符号钥匙", short_name: "314钥匙" },
      { id: "w309", name: "疗养院西楼 309 房间钥匙", short_name: "西309" },
      { id: "w325", name: "疗养院西楼 325 房间钥匙", short_name: "西325" },
    ];
    const hits = matchKeysFromOcr({
      tokens: [
        "1049)%",
        "195钥匙",
        "220%)",
        "西399",
        "218钥此",
        "314铂是",
        "西325",
      ],
      catalog: roomCatalog,
    }).map((row) => row.id);
    expect(hits).toEqual(expect.arrayContaining(["218", "314", "w325"]));
    expect(hits).not.toContain("104");
    expect(hits).not.toContain("105");
    expect(hits).not.toContain("220");
    expect(hits).not.toContain("w309");
  });
});

describe("loot screenshot false positives", () => {
  const lootCatalog = [
    { id: "leon", name: "Leon的藏身处钥匙", short_name: "Leon" },
    { id: "kiba-out", name: "Kiba 商店外门钥匙", short_name: "KIBA外" },
    { id: "kiba-in", name: "Kiba 商店内侧格栅门钥匙", short_name: "KIBA内" },
    { id: "rbst", name: "RB-ST 钥匙", short_name: "RB-ST" },
    { id: "labs", name: "TerraGroup实验室访问钥匙卡", short_name: "钥匙卡" },
    { id: "blue-mark", name: "蓝色记号钥匙卡", short_name: "钥匙卡" },
  ];

  it("does not map Lion statue OCR onto Leon", () => {
    expect(
      matchKeysFromOcr({ tokens: ["Lion", "LEDX", "H2O2"], catalog: lootCatalog }).map(
        (row) => row.id,
      ),
    ).toEqual([]);
  });

  it("does not promote leftover KIBA onto the inner key", () => {
    expect(
      matchKeysFromOcr({
        tokens: ["KIBA外", "KIBA"],
        catalog: lootCatalog,
      }).map((row) => row.id),
    ).toEqual(["kiba-out"]);
  });

  it("still fuzzy-matches hyphenated short codes", () => {
    expect(
      matchKeysFromOcr({ tokens: ["RB-5T"], catalog: lootCatalog }).map(
        (row) => row.id,
      ),
    ).toEqual(["rbst"]);
  });

  it("skips generic 钥匙卡 when two cards share it", () => {
    expect(
      matchKeysFromOcr({ tokens: ["钥匙卡"], catalog: lootCatalog }),
    ).toEqual([]);
  });
});
