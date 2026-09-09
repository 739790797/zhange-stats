import { describe, expect, it } from "vitest";
import {
  crossCheckSaveError,
  groupOcrProfileOptions,
} from "@/lib/ocrSettings";

describe("groupOcrProfileOptions", () => {
  it("groups by hint and skips empty ids", () => {
    const groups = groupOcrProfileOptions([
      { id: "v6_small", label: "multi_PP-OCRv6_rec_small", hint: "PP-OCRv6" },
      { id: "v5_server", label: "ch_PP-OCRv5_rec_server", hint: "PP-OCRv5" },
      { id: "v5_mobile_en", label: "en_PP-OCRv5_rec_mobile", hint: "PP-OCRv5" },
      { id: "  ", label: "nope", hint: "PP-OCRv5" },
      { id: "v4_mobile", label: "ch_PP-OCRv4_rec_mobile" },
    ]);
    expect(groups.map((row) => row.label)).toEqual([
      "PP-OCRv6",
      "PP-OCRv5",
      "PP-OCR",
    ]);
    expect(groups[1].options).toEqual([
      { value: "v5_server", label: "ch_PP-OCRv5_rec_server" },
      { value: "v5_mobile_en", label: "en_PP-OCRv5_rec_mobile" },
    ]);
  });
});

describe("crossCheckSaveError", () => {
  it("requires two enabled families when cross-check is on", () => {
    expect(
      crossCheckSaveError({
        engines: { paddle: true, easyocr: false },
        useCases: {
          tarkov_keys: { engines: ["paddle", "easyocr"], cross_check: true },
        },
        labels: { tarkov_keys: "塔科夫钥匙箱" },
      }),
    ).toContain("塔科夫钥匙箱");
  });

  it("allows one family when cross-check is off", () => {
    expect(
      crossCheckSaveError({
        engines: { paddle: true, easyocr: false },
        useCases: {
          general: { engines: ["paddle"], cross_check: false },
        },
      }),
    ).toBeNull();
  });
});
