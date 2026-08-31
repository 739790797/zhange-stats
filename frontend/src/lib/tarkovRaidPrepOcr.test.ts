import { describe, expect, it } from "vitest";
import {
  compactOcrText,
  extractTaskNameFromOcrLine,
  formatRaidPrepOcrProgress,
  isLikelyLocationOrStatusLine,
  isNearWidescreen,
  isPreferredRaidPrepOcrSize,
  matchRaidPrepTasksFromOcr,
  mergeRaidPrepOcrSelection,
  mergeOcrRawTexts,
  newRaidPrepOcrIds,
  normalizeOcrText,
  ocrCatalogShortName,
  ocrGuessPartInfo,
  ocrHitRank,
  parseOcrTaskLines,
  raidPrepOcrListCropRect,
} from "./tarkovRaidPrepOcr";

describe("normalizeOcrText", () => {
  it("strips spaces and punctuation", () => {
    expect(normalizeOcrText("  Debut — 初出茅庐 ")).toBe("debut初出茅庐");
    expect(normalizeOcrText("全角：测试")).toBe("全角测试");
  });
});

describe("compactOcrText", () => {
  it("aligns game OCR with catalog Part naming", () => {
    expect(compactOcrText("医疗隐私-5")).toBe("医疗隐私5");
    expect(compactOcrText("医疗隐私 - Part 5")).toBe("医疗隐私5");
    expect(ocrHitRank("医疗隐私-5", "医疗隐私 - Part 5")).toBe(0);
    expect(ocrHitRank("塔科夫神射手-3", "塔科夫神射手 - Part 3")).toBe(0);
    expect(
      matchRaidPrepTasksFromOcr({
        lines: ["塔科夫神射手-3"],
        catalog: [{ id: "4", name: "塔科夫神射手 - Part 3" }],
      }),
    ).toHaveLength(1);
  });
});

describe("formatRaidPrepOcrProgress", () => {
  it("maps tesseract status to Chinese", () => {
    expect(formatRaidPrepOcrProgress("loading tesseract core")).toBe(
      "正在加载识别引擎…",
    );
    expect(formatRaidPrepOcrProgress("loading language traineddata")).toBe(
      "正在加载识别模型…",
    );
    expect(formatRaidPrepOcrProgress("recognizing text", 0.4)).toBe(
      "正在识别文字… 40%",
    );
  });
});

describe("extractTaskNameFromOcrLine", () => {
  it("pulls task title from table row noise", () => {
    expect(
      extractTaskNameFromOcrLine(
        "加 。 消失的线人                                                 灯塔          进行中!              %%",
      ),
    ).toBe("消失的线人");
    expect(
      extractTaskNameFromOcrLine(
        "圆 。 钞人之路 - 管理者                      灯塔     进行中!       8%",
      ),
    ).toBe("钞人之路 - 管理者");
  });
});

describe("parseOcrTaskLines", () => {
  it("keeps task-like lines and drops ui noise", () => {
    const lines = parseOcrTaskLines(
      ["任务", "初出茅庐", "  补给  ", "进行中", "12%", "射击练习"].join("\n"),
    );
    expect(lines).toEqual(["初出茅庐", "补给", "射击练习"]);
  });

  it("parses realistic tesseract table output", () => {
    const raw = `加 。 消失的线人                                                 灯塔          进行中!              %%
加 网事                                                      海岸线         进行中!              2X%
轩 。 状良之针                                                                      任意地点            进行中!                    8%`;
    const lines = parseOcrTaskLines(raw);
    expect(lines).toContain("消失的线人");
    expect(lines.some((line) => line.includes("状良之针"))).toBe(true);
  });
});

describe("layout helpers", () => {
  it("flags preferred sizes and widescreen", () => {
    expect(isPreferredRaidPrepOcrSize(1920, 1080)).toBe(true);
    expect(isPreferredRaidPrepOcrSize(2560, 1440)).toBe(true);
    expect(isPreferredRaidPrepOcrSize(1024, 576)).toBe(false);
    expect(isNearWidescreen(1024, 576)).toBe(true);
    expect(isNearWidescreen(1920, 1200)).toBe(false);
  });

  it("scales crop rect with resolution", () => {
    const a = raidPrepOcrListCropRect(1920, 1080);
    const b = raidPrepOcrListCropRect(2560, 1440);
    expect(a.x / 1920).toBeCloseTo(b.x / 2560, 2);
    expect(a.width / 1920).toBeCloseTo(b.width / 2560, 2);
  });
});

describe("matchRaidPrepTasksFromOcr", () => {
  const catalog = [
    { id: "1", name: "初出茅庐", normalized_name: "debut" },
    { id: "2", name: "射击练习", normalized_name: "shooting-caleb" },
    { id: "3", name: "补给", normalized_name: "shortage" },
    { id: "4", name: "补给短缺", normalized_name: "shortage-2" },
    { id: "5", name: "消失的线人", normalized_name: "missing-cinformant" },
    { id: "6", name: "善良之针", normalized_name: "colleagues-part-3" },
    { id: "7", name: "医疗隐私 - Part 5", normalized_name: "health-care-privacy-5" },
    { id: "8", name: "猎人之路 - 管理者", normalized_name: "the-huntsman-path-administrator" },
  ];

  it("matches exact Chinese names", () => {
    expect(
      matchRaidPrepTasksFromOcr({
        lines: ["初出茅庐", "射击练习"],
        catalog,
      }).map((row) => row.id),
    ).toEqual(["1", "2"]);
  });

  it("matches OCR table rows and typo names", () => {
    const hits = matchRaidPrepTasksFromOcr({
      lines: [
        "加 。 消失的线人                                                 灯塔          进行中!",
        "轩 。 状良之针                                                 任意地点        进行中!",
        "圆 。 钞人之路 - 管理者                      灯塔     进行中!",
      ],
      catalog,
    }).map((row) => row.name);
    expect(hits).toContain("消失的线人");
    expect(hits).toContain("善良之针");
    expect(hits).toContain("猎人之路 - 管理者");
  });

  it("matches compact part numbering", () => {
    const hits = matchRaidPrepTasksFromOcr({
      lines: ["除   契。渤。 医疗隐私-5                                                     工厂"],
      catalog,
    });
    expect(hits.map((row) => row.id)).toEqual(["7"]);
  });

  it("accepts unique fuzzy OCR typo", () => {
    const hits = matchRaidPrepTasksFromOcr({
      lines: ["初出芽庐"],
      catalog: [{ id: "1", name: "初出茅庐", normalized_name: "debut" }],
    });
    expect(hits.map((row) => row.id)).toEqual(["1"]);
  });

  it("ignores lines that do not uniquely match", () => {
    expect(
      matchRaidPrepTasksFromOcr({
        lines: ["不存在的任务"],
        catalog,
      }),
    ).toEqual([]);
  });
});

describe("real screenshot OCR fixtures", () => {
  const sample1Catalog = [
    { id: "1", name: "高效秘诀" },
    { id: "2", name: "你被盯上了" },
    { id: "3", name: "奢靡人生" },
    { id: "4", name: "塔科夫神射手 - Part 3" },
    { id: "5", name: "人口普查" },
    { id: "6", name: "妥善保管" },
    { id: "7", name: "别开枪！" },
    { id: "8", name: "猎人之路 - 大动作" },
  ];

  const sample1Ocr = `高效秘决

你被盯上了

奢摩人生

塔科夫神射手-3

人口普查

轨养保管

别开枪!

猎人之路 - 大动作

浇科夫街区

进行中!

0%`;

  it("matches sample1 streets tasks from SINGLE_COLUMN OCR", () => {
    const lines = parseOcrTaskLines(sample1Ocr);
    const hits = matchRaidPrepTasksFromOcr({
      lines,
      catalog: sample1Catalog,
    }).map((row) => row.name);
    expect(hits).toContain("高效秘诀");
    expect(hits).toContain("你被盯上了");
    expect(hits).toContain("奢靡人生");
    expect(hits).toContain("人口普查");
    expect(hits).toContain("妥善保管");
    expect(hits).toContain("别开枪！");
    expect(hits).toContain("猎人之路 - 大动作");
    expect(hits).toContain("塔科夫神射手 - Part 3");
    expect(hits.length).toBeGreaterThanOrEqual(7);
  });

  const sample2Catalog = [
    { id: "1", name: "此路不通" },
    { id: "2", name: "单程票" },
    { id: "3", name: "急诊室的故事" },
    { id: "4", name: "卫生标准 - Part 1" },
    { id: "5", name: "城市的解药" },
    { id: "6", name: "一般储备" },
    { id: "7", name: "直播 - Part 1" },
  ];

  const sample2Ocr = `此路不通

单程票

急诊室的故事

卫生标准

城市的解药

般储备

直播 -1

灯塔

进行中!`;

  it("matches sample2 mixed tasks from SINGLE_COLUMN OCR", () => {
    const lines = parseOcrTaskLines(sample2Ocr);
    const hits = matchRaidPrepTasksFromOcr({
      lines,
      catalog: sample2Catalog,
    }).map((row) => row.name);
    expect(hits).toContain("此路不通");
    expect(hits).toContain("单程票");
    expect(hits).toContain("急诊室的故事");
    expect(hits).toContain("城市的解药");
    expect(hits).toContain("一般储备");
    expect(hits.length).toBeGreaterThanOrEqual(5);
  });

  it("filters location-only lines", () => {
    expect(isLikelyLocationOrStatusLine("浇科夫街区")).toBe(true);
    expect(isLikelyLocationOrStatusLine("进行中!")).toBe(true);
    expect(isLikelyLocationOrStatusLine("人口普查")).toBe(false);
  });

  it("matches shoreline screenshot OCR with dual-pass style lines", () => {
    const shorelineCatalog = [
      { id: "1", name: "湿活 - Part 1", normalized_name: "wet-job-part-1" },
      { id: "2", name: "邪教 - Part 1", normalized_name: "the-cult-part-1" },
      { id: "3", name: "化学橱柜", normalized_name: "pharmacist" },
      { id: "4", name: "恶意环伺", normalized_name: "painkiller" },
      { id: "5", name: "引路先驱", normalized_name: "guide" },
      { id: "6", name: "背景调查", normalized_name: "background-check" },
      { id: "9", name: "平衡之力 - Part 1 (PVE)", normalized_name: "balance-of-power-part-1-pve" },
    ];
    const normalPass = `得太

宕教

化学橱柜

恶意环体`;
    const invertPass = `各而"1

宕教

化学橱柜

恶意环伺`;
    const lines = mergeOcrRawTexts(normalPass, invertPass);
    const hits = matchRaidPrepTasksFromOcr({
      lines,
      catalog: shorelineCatalog,
    }).map((row) => row.id);
    expect(lines).toContain("各而 - 1");
    expect(lines).toContain("化学橱柜");
    expect(hits).toEqual(expect.arrayContaining(["1", "2", "3", "4"]));
    expect(hits).not.toContain("9");
    expect(hits.length).toBeGreaterThanOrEqual(4);
  });

  it("preserves part suffix stripped by OCR quotes", () => {
    expect(extractTaskNameFromOcrLine('各而"1')).toBe("各而 - 1");
    expect(ocrGuessPartInfo("各而 - 1")).toEqual({ base: "各而", part: "1" });
  });

  it("rejects suffix-only part matches like 之力1 -> 平衡之力", () => {
    const catalog = [
      { id: "1", name: "湿活 - Part 1" },
      { id: "9", name: "平衡之力 - Part 1 (PVE)" },
    ];
    expect(
      matchRaidPrepTasksFromOcr({ lines: ["之力1"], catalog }).map((r) => r.id),
    ).toEqual([]);
    expect(
      matchRaidPrepTasksFromOcr({ lines: ["平稀之力1"], catalog }).map((r) => r.id),
    ).toEqual(["9"]);
    expect(
      matchRaidPrepTasksFromOcr({ lines: ["湿1"], catalog }).map((r) => r.id),
    ).toEqual(["1"]);
    expect(
      matchRaidPrepTasksFromOcr({ lines: ["湿活1"], catalog }).map((r) => r.id),
    ).toEqual(["1"]);
  });

  it("matches short catalog names against OCR typos", () => {
    expect(ocrCatalogShortName("邪教 - Part 1")).toBe("邪教");
    expect(
      matchRaidPrepTasksFromOcr({
        lines: ["宕教"],
        catalog: [{ id: "2", name: "邪教 - Part 1" }],
      }).map((row) => row.id),
    ).toEqual(["2"]);
  });

  it("matches bottom-row hermit from lighthouse OCR fixture", () => {
    expect(extractTaskNameFromOcrLine("国 酌 士 灯塔")).toBe("酌 士");
    const catalog = [
      { id: "1", name: "消失的线人" },
      { id: "2", name: "猎人之路 - 管理者" },
      { id: "3", name: "隐士" },
    ];
    const normalPass = `回 。 消失 的 线 人 灯塔
贺 。 菏 人 之 路 - 管理 者 灯塔
贺 | 肌 十 灯塔`;
    const invertPass = `辆 。 消失 的 线 人 灯塔
贺 。 落 人 之 路 - 管理 者 灯塔
国 酌 士 灯塔`;
    const lines = mergeOcrRawTexts(normalPass, invertPass);
    const hits = matchRaidPrepTasksFromOcr({ lines, catalog }).map(
      (row) => row.name,
    );
    expect(hits).toContain("消失的线人");
    expect(hits).toContain("猎人之路 - 管理者");
    expect(hits).toContain("隐士");
  });
});

describe("merge selection", () => {
  it("merges and caps", () => {
    expect(mergeRaidPrepOcrSelection(["a", "b"], ["b", "c"], 40)).toEqual([
      "a",
      "b",
      "c",
    ]);
    expect(mergeRaidPrepOcrSelection(["a"], ["b", "c"], 2)).toEqual(["a", "b"]);
  });

  it("reports only new ids", () => {
    expect(newRaidPrepOcrIds(["a", "b"], ["b", "c", "a"])).toEqual(["c"]);
  });
});
