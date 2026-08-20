export type MotdSpan = {
  text: string;
  color: string;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  strike?: boolean;
};

/** Java 版遗留色码，按深色列表背景。 */
export const MC_LEGACY_COLORS: Record<string, string> = {
  "0": "#000000",
  "1": "#0000aa",
  "2": "#00aa00",
  "3": "#00aaaa",
  "4": "#aa0000",
  "5": "#aa00aa",
  "6": "#ffaa00",
  "7": "#aaaaaa",
  "8": "#555555",
  "9": "#5555ff",
  a: "#55ff55",
  b: "#55ffff",
  c: "#ff5555",
  d: "#ff55ff",
  e: "#ffff55",
  f: "#ffffff",
};

/** 浅色卡片上过亮的 MOTD 色会看不清，换成更深的对应色。 */
const LIGHT_MOTD_COLORS: Record<string, string> = {
  "#ffffff": "rgba(0, 0, 0, 0.88)",
  "#ffff55": "#ad8b00",
  "#55ffff": "#08979c",
  "#55ff55": "#389e0d",
  "#aaaaaa": "#8c8c8c",
  "#000000": "rgba(0, 0, 0, 0.88)",
};

export function motdColorOnLight(color: string) {
  return LIGHT_MOTD_COLORS[color.toLowerCase()] || color;
}

const FORMAT_CODES = new Set(["k", "l", "m", "n", "o", "r"]);

function sameStyle(span: MotdSpan, next: Omit<MotdSpan, "text">) {
  return (
    span.color === next.color &&
    Boolean(span.bold) === Boolean(next.bold) &&
    Boolean(span.italic) === Boolean(next.italic) &&
    Boolean(span.underline) === Boolean(next.underline) &&
    Boolean(span.strike) === Boolean(next.strike)
  );
}

function readHexColor(raw: string, start: number): { color: string; next: number } | null {
  // §x§R§R§G§G§B§B
  if (
    start + 12 <= raw.length &&
    raw[start] === "§" &&
    raw[start + 2] === "§" &&
    raw[start + 4] === "§" &&
    raw[start + 6] === "§" &&
    raw[start + 8] === "§" &&
    raw[start + 10] === "§"
  ) {
    const hex = [
      raw[start + 1],
      raw[start + 3],
      raw[start + 5],
      raw[start + 7],
      raw[start + 9],
      raw[start + 11],
    ].join("");
    if (/^[0-9a-f]{6}$/i.test(hex)) {
      return { color: `#${hex.toLowerCase()}`, next: start + 12 };
    }
  }
  // §xRRGGBB
  const compact = raw.slice(start, start + 6);
  if (/^[0-9a-f]{6}$/i.test(compact)) {
    return { color: `#${compact.toLowerCase()}`, next: start + 6 };
  }
  return null;
}

export function parseMotdLines(raw: string): MotdSpan[][] {
  const source = (raw || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (!source) return [];

  const lines: MotdSpan[][] = [[]];
  let color = "#ffffff";
  let bold = false;
  let italic = false;
  let underline = false;
  let strike = false;

  const push = (text: string) => {
    if (!text) return;
    const chunks = text.split("\n");
    chunks.forEach((chunk, index) => {
      if (index > 0) lines.push([]);
      if (!chunk) return;
      const style = { color, bold, italic, underline, strike };
      const line = lines[lines.length - 1];
      const last = line[line.length - 1];
      if (last && sameStyle(last, style)) last.text += chunk;
      else line.push({ text: chunk, ...style });
    });
  };

  let i = 0;
  while (i < source.length) {
    if (source[i] === "§" && i + 1 < source.length) {
      const code = source[i + 1].toLowerCase();
      if (code === "x") {
        const hex = readHexColor(source, i + 2);
        if (hex) {
          color = hex.color;
          i = hex.next;
          continue;
        }
        i += 2;
        continue;
      }
      if (code in MC_LEGACY_COLORS) {
        color = MC_LEGACY_COLORS[code];
        i += 2;
        continue;
      }
      if (FORMAT_CODES.has(code)) {
        if (code === "l") bold = true;
        else if (code === "o") italic = true;
        else if (code === "n") underline = true;
        else if (code === "m") strike = true;
        else if (code === "r") {
          color = "#ffffff";
          bold = false;
          italic = false;
          underline = false;
          strike = false;
        }
        i += 2;
        continue;
      }
      i += 2;
      continue;
    }
    let j = i + 1;
    while (j < source.length && source[j] !== "§") j += 1;
    push(source.slice(i, j));
    i = j;
  }

  while (lines.length > 1 && lines[lines.length - 1].length === 0) {
    lines.pop();
  }
  return lines;
}

export function motdPlainText(raw: string) {
  return parseMotdLines(raw)
    .map((line) => line.map((span) => span.text).join(""))
    .join("\n")
    .trim();
}
