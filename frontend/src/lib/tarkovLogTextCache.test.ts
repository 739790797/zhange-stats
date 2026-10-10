import { describe, expect, it } from "vitest";
import { readTarkovLogText, type TarkovLogTextEntry } from "./tarkovLogTextCache";

const encoder = new TextEncoder();

function bytesOf(...parts: Array<string | number[]>): Uint8Array<ArrayBuffer> {
  const chunks = parts.map((part) =>
    typeof part === "string" ? encoder.encode(part) : Uint8Array.from(part),
  );
  const out = new Uint8Array(chunks.reduce((sum, chunk) => sum + chunk.length, 0));
  let at = 0;
  for (const chunk of chunks) {
    out.set(chunk, at);
    at += chunk.length;
  }
  return out;
}

/** 记下每次从哪个字节开始读，用来确认续读没有回头读整份文件。 */
function trackedFile(bytes: Uint8Array<ArrayBuffer>, lastModified: number) {
  const file = new File([bytes], "application.log", { lastModified });
  const reads: number[] = [];
  const view = {
    name: file.name,
    size: file.size,
    lastModified,
    arrayBuffer: () => {
      reads.push(0);
      return file.arrayBuffer();
    },
    slice: (start?: number) => {
      reads.push(start ?? 0);
      return file.slice(start);
    },
  } as unknown as File;
  return { file: view, reads, text: () => file.text() };
}

async function step(
  bytes: Uint8Array<ArrayBuffer>,
  lastModified: number,
  prev?: TarkovLogTextEntry | null,
) {
  const tracked = trackedFile(bytes, lastModified);
  const entry = await readTarkovLogText("application.log", tracked.file, prev);
  return { entry, reads: tracked.reads, expected: await tracked.text() };
}

describe("readTarkovLogText", () => {
  it("matches file.text() on a first read", async () => {
    for (const bytes of [
      bytesOf(""),
      bytesOf("no newline yet"),
      bytesOf("line one\nline two\n"),
      bytesOf([0xef, 0xbb, 0xbf], "带 BOM 的开头\r\n第二行"),
      bytesOf("emoji 🎯 and 中文\n", [0xe4, 0xb8]),
      bytesOf("bad byte ", [0xff], " here\n"),
    ]) {
      const { entry, expected } = await step(bytes, 1);
      expect(entry.read.text).toBe(expected);
      expect(entry.read.size).toBe(bytes.length);
    }
  });

  it("returns the previous entry untouched when size and mtime match", async () => {
    const first = await step(bytesOf("a\nb\n"), 10);
    const again = await step(bytesOf("a\nb\n"), 10, first.entry);
    expect(again.entry).toBe(first.entry);
    expect(again.reads).toEqual([]);
  });

  it("reads only the bytes after the last full line when the file grows", async () => {
    const prefix = Array.from({ length: 400 }, (_, i) => `2024-02-05 19:00:${i}|line ${i}\n`).join("");
    const first = await step(bytesOf(prefix, "partial"), 1);
    const grown = bytesOf(prefix, "partial line done\nnext");
    const second = await step(grown, 2, first.entry);
    expect(second.entry.read.text).toBe(second.expected);
    expect(second.reads).toHaveLength(1);
    expect(second.reads[0]).toBeGreaterThan(encoder.encode(prefix).length - 300);
    expect(second.entry.read).not.toBe(first.entry.read);
  });

  it("re-decodes a multibyte character split at the previous end", async () => {
    const emoji = encoder.encode("🎯");
    const first = await step(bytesOf("head\n", Array.from(emoji.subarray(0, 2))), 1);
    expect(first.entry.read.text).toBe(first.expected);
    expect(first.entry.read.text.endsWith("\uFFFD")).toBe(true);
    const second = await step(bytesOf("head\n", Array.from(emoji), " tail\n"), 2, first.entry);
    expect(second.entry.read.text).toBe("head\n🎯 tail\n");
    expect(second.entry.read.text).toBe(second.expected);
  });

  it("keeps a BOM that shows up mid-file but drops the leading one", async () => {
    const bom = [0xef, 0xbb, 0xbf];
    const first = await step(bytesOf(bom, "first\n"), 1);
    const second = await step(bytesOf(bom, "first\n", bom, "second\n"), 2, first.entry);
    expect(second.entry.read.text).toBe("first\n\uFEFFsecond\n");
    expect(second.entry.read.text).toBe(second.expected);
  });

  it("falls back to a full read when the file was truncated or rewritten", async () => {
    const long = Array.from({ length: 50 }, (_, i) => `row ${i}\n`).join("");
    const first = await step(bytesOf(long), 1);

    const truncated = await step(bytesOf("row 0\n"), 2, first.entry);
    expect(truncated.entry.read.text).toBe("row 0\n");
    expect(truncated.reads).toEqual([0]);

    const rewritten = await step(bytesOf(long.replace("row 49", "ROW 49"), "more\n"), 3, first.entry);
    expect(rewritten.entry.read.text).toBe(rewritten.expected);
    expect(rewritten.reads[rewritten.reads.length - 1]).toBe(0);

    const sameSize = await step(bytesOf(long.replace("row 1\n", "row X\n")), 4, first.entry);
    expect(sameSize.entry.read.text).toBe(sameSize.expected);
    expect(sameSize.reads).toEqual([0]);
  });

  it("stays identical to file.text() across random appends", async () => {
    let seed = 20260830;
    const random = () => {
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const pieces = [
      "2024-02-05 19:00:00.000|x|Info|application|GameStarted\r\n",
      "中文行\n",
      "🎯🎯",
      "\n",
      "plain ascii without newline ",
      "\uFEFF",
      "Got notification | ChatMessageReceived\n{ \"type\": 10 }\n",
    ];
    for (let round = 0; round < 20; round += 1) {
      const chunks: number[] = [];
      for (let i = 0; i < 40; i += 1) {
        if (random() < 0.08) chunks.push(0xff);
        chunks.push(...encoder.encode(pieces[Math.floor(random() * pieces.length)]));
      }
      let prev: TarkovLogTextEntry | null = null;
      let size = 0;
      let clock = 1;
      while (size < chunks.length) {
        size = Math.min(chunks.length, size + 1 + Math.floor(random() * 37));
        const result = await step(Uint8Array.from(chunks.slice(0, size)), clock, prev);
        expect(result.entry.read.text).toBe(result.expected);
        prev = result.entry;
        clock += 1;
      }
    }
  });
});
