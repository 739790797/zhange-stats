/**
 * 实时轮询增量读游戏日志。日志只往后追加：大小与修改时间都没变就沿用上次的对象；
 * 变长了只读末个换行之后的新字节，接到旧文本后面。结果与整份 `file.text()` 一致。
 *
 * `output.log` 例外：战局里这份 Unity 日志会涨到几百 MB，而解析只用其中的
 * `GameStopping()` 行。整份留在字符串里会把房间页撑到 Out of Memory，所以按块
 * 扫过去，文本里只留这些行。
 */

/** 末个换行前留多少字节做比对；对不上说明文件被改写，整份重读。 */
const PROBE_BYTES = 256;
const NEWLINE = 0x0a;
/** 和 tarkovGameLogs 的 output.log 判定一致。放这里是为了不和解析模块循环引用。 */
const OUTPUT_LOG_RE = /(?:^|[\\/ ])output(?:_\d+)?\.log$/i;
const OUTPUT_MARKER = "GameStopping()";
const OUTPUT_MARKER_BYTES = new TextEncoder().encode(OUTPUT_MARKER);
/** 没有换行的超长行只留标记可能跨过的尾巴，避免一条垃圾行就把整份文件留在内存里。 */
const OUTPUT_LINE_KEEP = 8192;
const OUTPUT_CHUNK = 256 * 1024;

function isOutputLogName(name: string): boolean {
  return OUTPUT_LOG_RE.test((name || "").trim());
}

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

/** 续读出来的新对象 → 它接着的那份旧对象。解析缓存按对象记，靠这条链接着上次的扫描状态续扫。 */
const grownFrom = new WeakMap<object, TarkovLogText>();

/** 这份文本是不是从某个旧对象往后追加出来的（是就回旧对象）；整份重读或没变过时为空。 */
export function logTextGrownFrom(read: object): TarkovLogText | undefined {
  return grownFrom.get(read);
}

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
  const read = { name, text, lastModified: file.lastModified, size: file.size };
  grownFrom.set(read, prev.read);
  return {
    read,
    lineEnd,
    tailChars: tail.length,
    probe: bytes.slice(Math.max(0, lineEnd - PROBE_BYTES) - from, lineEnd - from),
  };
}

function concatBytes(a: Uint8Array, b: Uint8Array): Uint8Array {
  if (!a.length) return b;
  if (!b.length) return a;
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

function rollProbe(probe: Uint8Array, bytes: Uint8Array): Uint8Array {
  if (!bytes.length) return probe;
  const source =
    bytes.length >= PROBE_BYTES
      ? bytes.subarray(bytes.length - PROBE_BYTES)
      : concatBytes(probe, bytes);
  const tail =
    source.length > PROBE_BYTES
      ? source.subarray(source.length - PROBE_BYTES)
      : source;
  const out = new Uint8Array(tail.length);
  out.set(tail);
  return out;
}

function lineHasMarker(line: Uint8Array): boolean {
  const needle = OUTPUT_MARKER_BYTES;
  if (line.length < needle.length) return false;
  const last = line.length - needle.length;
  for (let i = 0; i <= last; i += 1) {
    let found = true;
    for (let j = 0; j < needle.length; j += 1) {
      if (line[i + j] !== needle[j]) {
        found = false;
        break;
      }
    }
    if (found) return true;
  }
  return false;
}

/**
 * 从 start 扫到文件末尾。完整行里没有 GameStopping 的直接丢掉；
 * 没写完的最后一行留到下次，不放进文本。
 */
async function scanOutputLog(
  file: File,
  start: number,
): Promise<{ lines: string[]; lineEnd: number; probe: Uint8Array }> {
  let offset = start;
  let pending = new Uint8Array(0);
  let consumed = 0;
  let probe = new Uint8Array(0);
  const lines: string[] = [];
  const takeLine = (line: Uint8Array, newline: boolean) => {
    if (lineHasMarker(line)) {
      const sample = line.length > 2048 ? line.subarray(0, 2048) : line;
      lines.push(decodeFrom(sample));
    }
    const tailLen = Math.min(line.length, PROBE_BYTES);
    const tail = line.subarray(line.length - tailLen);
    probe = new Uint8Array(
      rollProbe(probe, newline ? concatBytes(tail, Uint8Array.of(NEWLINE)) : tail),
    );
    consumed += line.length + (newline ? 1 : 0);
  };
  while (offset < file.size) {
    const end = Math.min(file.size, offset + OUTPUT_CHUNK);
    const chunk = new Uint8Array(await file.slice(offset, end).arrayBuffer());
    offset = end;
    const data = pending.length ? concatBytes(pending, chunk) : chunk;
    let lineStart = 0;
    for (let i = 0; i < data.length; i += 1) {
      if (data[i] !== NEWLINE) continue;
      takeLine(data.subarray(lineStart, i), true);
      lineStart = i + 1;
    }
    pending = data.slice(lineStart);
    if (pending.length > OUTPUT_LINE_KEEP && !lineHasMarker(pending)) {
      const keep = OUTPUT_MARKER_BYTES.length - 1;
      const drop = pending.length - keep;
      probe = new Uint8Array(rollProbe(probe, pending.subarray(0, drop)));
      consumed += drop;
      pending = pending.slice(drop);
    }
  }
  return { lines, lineEnd: start + consumed, probe };
}

function outputEntry(
  name: string,
  file: File,
  text: string,
  lineEnd: number,
  probe: Uint8Array,
  prev: TarkovLogText | null,
): TarkovLogTextEntry {
  const read = { name, text, lastModified: file.lastModified, size: file.size };
  if (prev) grownFrom.set(read, prev);
  return { read, lineEnd, tailChars: 0, probe };
}

async function outputProbeMatches(file: File, prev: TarkovLogTextEntry): Promise<boolean> {
  const from = prev.lineEnd - prev.probe.length;
  if (from < 0) return false;
  const bytes = new Uint8Array(await file.slice(from, prev.lineEnd).arrayBuffer());
  if (bytes.length !== prev.probe.length) return false;
  for (let i = 0; i < bytes.length; i += 1) {
    if (bytes[i] !== prev.probe[i]) return false;
  }
  return true;
}

async function readOutputLog(
  name: string,
  file: File,
  prev?: TarkovLogTextEntry | null,
): Promise<TarkovLogTextEntry> {
  if (
    prev &&
    prev.lineEnd > 0 &&
    file.size > prev.read.size &&
    (await outputProbeMatches(file, prev))
  ) {
    const scanned = await scanOutputLog(file, prev.lineEnd);
    const text = scanned.lines.length
      ? `${prev.read.text}${scanned.lines.join("\n")}\n`
      : prev.read.text;
    return outputEntry(name, file, text, scanned.lineEnd, scanned.probe, prev.read);
  }
  const scanned = await scanOutputLog(file, 0);
  const text = scanned.lines.length ? `${scanned.lines.join("\n")}\n` : "";
  return outputEntry(name, file, text, scanned.lineEnd, scanned.probe, null);
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
  if (isOutputLogName(name)) return readOutputLog(name, file, prev);
  if (prev && prev.lineEnd > 0 && file.size > prev.read.size) {
    const appended = await readAppended(name, file, prev);
    if (appended) return appended;
  }
  return readWhole(name, file);
}
