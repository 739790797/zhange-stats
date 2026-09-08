import { describe, expect, it } from "vitest";
import { parseKeyOcrNdjsonLine } from "./tarkovKeyOcrProgress";

describe("parseKeyOcrNdjsonLine", () => {
  it("reads progress percent and message", () => {
    expect(
      parseKeyOcrNdjsonLine(
        '{"event":"progress","message":"第 1/2 块 · 熊猫 OCR · 正图","percent":20,"phase":"ocr"}',
      ),
    ).toEqual({
      event: "progress",
      message: "第 1/2 块 · 熊猫 OCR · 正图",
      percent: 20,
      phase: "ocr",
    });
  });

  it("clamps percent and fills empty message", () => {
    expect(
      parseKeyOcrNdjsonLine('{"event":"progress","message":"","percent":140}'),
    ).toEqual({
      event: "progress",
      message: "识别中…",
      percent: 100,
      phase: undefined,
    });
  });

  it("returns done result and error detail", () => {
    expect(
      parseKeyOcrNdjsonLine(
        '{"event":"done","result":{"matches":[],"tile_count":1}}',
      ),
    ).toEqual({
      event: "done",
      result: { matches: [], tile_count: 1 },
    });
    expect(
      parseKeyOcrNdjsonLine(
        '{"event":"error","status_code":503,"detail":"模型未就绪"}',
      ),
    ).toEqual({
      event: "error",
      status_code: 503,
      detail: "模型未就绪",
    });
  });

  it("ignores blank and invalid lines", () => {
    expect(parseKeyOcrNdjsonLine("")).toBeNull();
    expect(parseKeyOcrNdjsonLine("not-json")).toBeNull();
    expect(parseKeyOcrNdjsonLine('{"event":"other"}')).toBeNull();
  });
});
