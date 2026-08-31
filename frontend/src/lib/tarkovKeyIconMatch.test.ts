import { describe, expect, it } from "vitest";
import {
  encodeIconGray,
  finalizeIconSample,
  KEY_ICON_TEMPLATE_SIZE,
  matchKeyIcon,
  sampleIconFromRgba,
  templateFromIndexItem,
} from "./tarkovKeyIconMatch";

function paintRect(
  width: number,
  height: number,
  fill: [number, number, number],
  mark?: { x: number; y: number; w: number; h: number; color: [number, number, number] },
): Uint8ClampedArray {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = fill[0];
    data[i + 1] = fill[1];
    data[i + 2] = fill[2];
    data[i + 3] = 255;
  }
  if (mark) {
    for (let y = mark.y; y < mark.y + mark.h; y += 1) {
      for (let x = mark.x; x < mark.x + mark.w; x += 1) {
        const i = (y * width + x) * 4;
        data[i] = mark.color[0];
        data[i + 1] = mark.color[1];
        data[i + 2] = mark.color[2];
      }
    }
  }
  return data;
}

function templateFromPixels(
  id: string,
  data: Uint8ClampedArray,
  width: number,
  height: number,
) {
  const sample = sampleIconFromRgba(data, width, height, {
    x: 0,
    y: 0,
    width,
    height,
  });
  if (!sample) throw new Error("sample failed");
  return { id, ...sample };
}

describe("matchKeyIcon", () => {
  it("picks a uniquely colored card", () => {
    const blue = paintRect(48, 48, [20, 20, 24], {
      x: 8,
      y: 10,
      w: 32,
      h: 24,
      color: [40, 90, 190],
    });
    const yellow = paintRect(48, 48, [20, 20, 24], {
      x: 8,
      y: 10,
      w: 32,
      h: 24,
      color: [200, 170, 40],
    });
    const templates = [
      { ...templateFromPixels("blue", blue, 48, 48), short_name: "蓝卡" },
      { ...templateFromPixels("yellow", yellow, 48, 48), short_name: "黄卡" },
    ];
    const shot = sampleIconFromRgba(blue, 48, 48, { x: 2, y: 2, width: 44, height: 44 });
    const hit = matchKeyIcon(shot, templates);
    expect(hit.kind).toBe("unique");
    if (hit.kind === "unique") expect(hit.hit.id).toBe("blue");
  });

  it("clusters identical icons instead of guessing", () => {
    const key = paintRect(48, 48, [22, 22, 22], {
      x: 14,
      y: 12,
      w: 20,
      h: 16,
      color: [180, 170, 130],
    });
    const templates = [
      templateFromPixels("k114", key, 48, 48),
      templateFromPixels("k214", key, 48, 48),
    ];
    const shot = sampleIconFromRgba(key, 48, 48, { x: 0, y: 0, width: 48, height: 48 });
    const hit = matchKeyIcon(shot, templates);
    expect(hit.kind).toBe("cluster");
    if (hit.kind === "cluster") {
      expect(hit.hits.map((row) => row.id).sort()).toEqual(["k114", "k214"]);
    }
  });

  it("skips empty dark cells", () => {
    const dark = paintRect(40, 40, [18, 18, 18]);
    const sample = sampleIconFromRgba(dark, 40, 40, { x: 2, y: 2, width: 36, height: 36 });
    expect(matchKeyIcon(sample, []).kind).toBe("empty");
  });

  it("ignores a green check overlay on a colored card", () => {
    const card = paintRect(48, 48, [20, 20, 24], {
      x: 8,
      y: 10,
      w: 32,
      h: 24,
      color: [40, 90, 190],
    });
    const checked = new Uint8ClampedArray(card);
    for (let y = 2; y < 12; y += 1) {
      for (let x = 36; x < 46; x += 1) {
        const i = (y * 48 + x) * 4;
        checked[i] = 40;
        checked[i + 1] = 170;
        checked[i + 2] = 50;
      }
    }
    const templates = [{ ...templateFromPixels("blue", card, 48, 48), short_name: "蓝卡" }];
    const shot = sampleIconFromRgba(checked, 48, 48, { x: 2, y: 2, width: 44, height: 44 });
    const hit = matchKeyIcon(shot, templates);
    expect(hit.kind).toBe("unique");
    if (hit.kind === "unique") expect(hit.hit.id).toBe("blue");
  });

  it("prefers a standard lab card over the A.P. variant", () => {
    const blue = paintRect(48, 48, [20, 20, 24], {
      x: 8,
      y: 10,
      w: 32,
      h: 24,
      color: [40, 90, 190],
    });
    const templates = [
      { ...templateFromPixels("blue", blue, 48, 48), short_name: "蓝卡" },
      { ...templateFromPixels("ap", blue, 48, 48), short_name: "A.P.蓝" },
    ];
    const shot = sampleIconFromRgba(blue, 48, 48, { x: 2, y: 2, width: 44, height: 44 });
    const hit = matchKeyIcon(shot, templates);
    expect(hit.kind).toBe("unique");
    if (hit.kind === "unique") expect(hit.hit.id).toBe("blue");
  });

  it("round-trips index bytes", () => {
    const gray = new Float32Array(KEY_ICON_TEMPLATE_SIZE * KEY_ICON_TEMPLATE_SIZE);
    for (let i = 0; i < gray.length; i += 1) gray[i] = (i * 3) % 256;
    const sample = finalizeIconSample(gray, 10, 20, 30);
    const tmpl = templateFromIndexItem({
      id: "x",
      gray: encodeIconGray(sample.gray),
      r: 10,
      g: 20,
      b: 30,
      chromaRatio: 0,
    });
    expect(tmpl?.id).toBe("x");
    expect(tmpl?.gray.length).toBe(gray.length);
    expect(tmpl?.gray[3]).toBe(9);
  });
});
