import { describe, expect, it } from "vitest";
import {
  filenameFromDisposition,
  fileAllRootRows,
  fileBrowseUp,
  formatBytes,
  formatPercent,
  isFileBrowseLocked,
  joinFileRel,
  parentFileRel,
  stackDiskUsage,
} from "./fileManager";

describe("fileManager", () => {
  it("formats byte sizes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(3 * 1024 ** 2)).toBe("3.00 MB");
    expect(formatBytes(Number.NaN)).toBe("—");
  });

  it("computes disk percent", () => {
    expect(formatPercent(25, 100)).toBe(25);
    expect(formatPercent(1, 0)).toBe(0);
  });

  it("locks sensitive or missing browse rows", () => {
    expect(isFileBrowseLocked({ name: "..", sensitive: true })).toBe(false);
    expect(isFileBrowseLocked({ name: ".env", sensitive: true })).toBe(true);
    expect(isFileBrowseLocked({ name: ".git", sensitive: true })).toBe(true);
    expect(isFileBrowseLocked({ name: "backend", missing: true })).toBe(true);
    expect(isFileBrowseLocked({ name: "backend" })).toBe(false);
  });

  it("joins and splits relative paths", () => {
    expect(joinFileRel("", "data")).toBe("data");
    expect(joinFileRel("data", "rapidocr")).toBe("data/rapidocr");
    expect(joinFileRel("data\\rapidocr", "det.onnx")).toBe("data/rapidocr/det.onnx");
    expect(parentFileRel("data/rapidocr/det.onnx")).toBe("data/rapidocr");
    expect(parentFileRel("data")).toBe("");
    expect(parentFileRel("")).toBe("");
  });

  it("goes up from a browse root to the all-roots view", () => {
    expect(fileBrowseUp("var", "cache/pycache")).toEqual({
      root: "var",
      path: "cache",
    });
    expect(fileBrowseUp("var", "cache")).toEqual({ root: "var", path: "" });
    expect(fileBrowseUp("var", "")).toEqual({ root: "", path: "" });
  });

  it("lists every browse root as a folder row", () => {
    expect(
      fileAllRootRows([
        { id: "var", label: "运行时 var/", exists: true },
        { id: "hf_cache", label: "Hugging Face 缓存", exists: false },
      ]),
    ).toEqual([
      {
        key: "var",
        name: "运行时 var/",
        is_dir: true,
        size: 0,
        modified_at: null,
        sensitive: false,
        downloadable: false,
        browseRootId: "var",
        missing: false,
      },
      {
        key: "hf_cache",
        name: "Hugging Face 缓存",
        is_dir: true,
        size: 0,
        modified_at: null,
        sensitive: false,
        downloadable: false,
        browseRootId: "hf_cache",
        missing: true,
      },
    ]);
  });

  it("parses content-disposition filenames", () => {
    expect(
      filenameFromDisposition(
        "attachment; filename*=UTF-8''%E6%9D%83%E9%87%8D.onnx",
        "x",
      ),
    ).toBe("权重.onnx");
    expect(
      filenameFromDisposition('attachment; filename="plain.bin"', "x"),
    ).toBe("plain.bin");
  });

  it("stacks site vs other vs free on the install volume", () => {
    expect(
      stackDiskUsage(5, [
        {
          id: "vol_install",
          path: "D:\\",
          total_bytes: 100,
          used_bytes: 47,
          free_bytes: 53,
        },
        {
          id: "vol_huggingface",
          path: "C:\\hf",
          total_bytes: 200,
          used_bytes: 170,
          free_bytes: 30,
        },
      ]),
    ).toEqual({
      totalBytes: 100,
      siteBytes: 5,
      otherBytes: 42,
      freeBytes: 53,
      path: "D:\\",
    });
  });

  it("clamps site usage when it exceeds the chosen disk", () => {
    const stack = stackDiskUsage(80, [
      {
        id: "vol_data",
        path: "/",
        total_bytes: 100,
        used_bytes: 50,
        free_bytes: 50,
      },
    ]);
    expect(stack?.siteBytes).toBe(50);
    expect(stack?.otherBytes).toBe(0);
    expect(stack?.freeBytes).toBe(50);
  });

  it("returns null without a usable volume", () => {
    expect(stackDiskUsage(10, [])).toBeNull();
    expect(
      stackDiskUsage(10, [
        {
          id: "vol_install",
          path: "D:\\",
          total_bytes: 0,
          used_bytes: 0,
          free_bytes: 0,
        },
      ]),
    ).toBeNull();
  });
});
