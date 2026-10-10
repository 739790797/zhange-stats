/**
 * 实时轮询增量读游戏日志。日志只往后追加：大小与修改时间都没变就沿用上次的对象；
 * 变长了只读末个换行之后的新字节，接到旧文本后面。结果与整份 `file.text()` 一致。
 */

/** 末个换行前留多少字节做比对；对不上说明文件被改写，整份重读。 */
const PROBE_BYTES = 256;
const NEWLINE = 0x0a;

export type TarkovLogText = {
  name: string;
  text: string;
  lastModified: number;
  size: number;
};

export type TarkovLogTextEntry = {
  /** 文件没变时原样复用，下游可以按引用记住解析结果。 */
  read: TarkovLogText;
  /** 末个换行之后的字节位置。换行字节不会落在多字节字符中间，从这里切开解码与整份解码一致。 */
  lineEnd: number;
  /** read.text 里 lineEnd 之后那半行的字符数，续读时连同新字节一起重新解码。 */
  tailChars: number;
  /** lineEnd 之前最多 PROBE_BYTES 个字节。 */
  probe: Uint8Array;
};

/** 续读不是从文件开头解码，文件中途的 BOM 要原样保留；`file.text()` 只去掉开头那个。 */
function decodeFrom(bytes: Uint8Array): string {
  return new TextDecoder("utf-8", { ignoreBOM: true }).decode(bytes);
}

async function readWhole(name: string, file: File): Promise<TarkovLogTextEntry> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const text = new TextDecoder().decode(bytes);
  const lineEnd = bytes.lastIndexOf(NEWLINE) + 1;
  return {
    read: { name, text, lastModified: file.lastModified, size: file.size },
    lineEnd,
    tailChars: lineEnd > 0 ? decodeFrom(bytes.subarray(lineEnd)).length : text.length,
    probe: bytes.slice(Math.max(0, lineEnd - PROBE_BYTES), lineEnd),
  };
}

async function readAppended(
  name: string,
  file: File,
  prev: TarkovLogTextEntry,
): Promise<TarkovLogTextEntry | null> {
  const from = prev.lineEnd - prev.probe.length;
  const bytes = new Uint8Array(await file.slice(from).arrayBuffer());
  for (let i = 0; i < prev.probe.length; i += 1) {
    if (bytes[i] !== prev.probe[i]) return null;
  }
  const fresh = bytes.subarray(prev.probe.length);
  const cut = fresh.lastIndexOf(NEWLINE) + 1;
  const tail = decodeFrom(fresh.subarray(cut));
  const head = prev.read.text.slice(0, prev.read.text.length - prev.tailChars);
  const text = cut > 0 ? head + decodeFrom(fresh.subarray(0, cut)) + tail : head + tail;
  const lineEnd = prev.lineEnd + cut;
  return {
    read: { name, text, lastModified: file.lastModified, size: file.size },
    lineEnd,
    tailChars: tail.length,
    probe: bytes.slice(Math.max(0, lineEnd - PROBE_BYTES) - from, lineEnd - from),
  };
}

/** prev 是同一个文件上次读到的结果；截短、原地改写或前文对不上时整份重读。 */
export async function readTarkovLogText(
  name: string,
  file: File,
  prev?: TarkovLogTextEntry | null,
): Promise<TarkovLogTextEntry> {
  if (prev && prev.read.size === file.size && prev.read.lastModified === file.lastModified) {
    return prev;
  }
  if (prev && prev.lineEnd > 0 && file.size > prev.read.size) {
    const appended = await readAppended(name, file, prev);
    if (appended) return appended;
  }
  return readWhole(name, file);
}
