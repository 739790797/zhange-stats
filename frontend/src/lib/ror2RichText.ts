/** 游戏 `TMP Default Style Sheet.asset` 里的开闭定义。`<style=名字>` 先换成这两段，再画剩下的标签。 */
const TEXT_STYLES: Record<string, { open: string; close: string }> = {
  cShrine: { open: "<color=#efeb1a>", close: "</color>" },
  cEvent: { open: "<color=#8394b3>", close: "</color>" },
  cDeath: { open: "<color=#fe7c7c>", close: "</color>" },
  cWorldEvent: { open: "<color=#ffc9f5>", close: "</color>" },
  cKeyBinding: { open: "<color=#ffff00>", close: "</color>" },
  cStack: { open: "<color=#8990a7>", close: "</color>" },
  cMono: { open: "<color=#8990a7><mspace=1em>", close: "</mspace></color>" },
  cIsDamage: { open: "<color=#e5c962>", close: "</color>" },
  cIsHealing: { open: "<color=#9ce562>", close: "</color>" },
  cIsHealth: { open: "<color=#e58262>", close: "</color>" },
  cIsUtility: { open: "<color=#95cde5>", close: "</color>" },
  cUserSetting: { open: "<color=#FFFFD0>", close: "</color>" },
  cSub: { open: "<color=#ccd3e0>", close: "</color>" },
  cArtifact: { open: "<color=#8a5cc0>", close: "</color>" },
  cKeywordName: { open: "<b>[ ", close: " ]</b>" },
  cLunarObjective: { open: "<color=#b8c4ff>", close: "</color>" },
  cHumanObjective: { open: "<color=#ecfc80>", close: "</color>" },
  cIsVoid: { open: "<color=#ed7fcd>", close: "</color>" },
  cIsLunar: { open: "<color=#b8c4ff>", close: "</color>" },
  Normal: { open: "", close: "" },
  cIsTierBoss: { open: "<color=#ffeb04>", close: "</color>" },
  cIsCursed: { open: "<color=#048501>", close: "</color>" },
  cIsTemporary: { open: "<color=#8bc7d5>", close: "</color>" },
  cIsRental: { open: "<color=#fbd88b>", close: "</color>" },
};

const STYLE_BY_NAME = new Map(
  Object.entries(TEXT_STYLES).map(([name, value]) => [name.toLowerCase(), value]),
);

/** Wiki `{{Color}}` 快捷名里，和游戏样式表色值一致的。 */
const WIKI_COLOR_STYLE: Record<string, string> = {
  d: "cIsDamage",
  damage: "cIsDamage",
  h: "cIsHealing",
  heal: "cIsHealing",
  healing: "cIsHealing",
  u: "cIsUtility",
  utility: "cIsUtility",
  hp: "cIsHealth",
  health: "cIsHealth",
  death: "cDeath",
  v: "cIsVoid",
  void: "cIsVoid",
  artifact: "cArtifact",
  boss: "cIsTierBoss",
  yellow: "cIsTierBoss",
  temporary: "cIsTemporary",
  temp: "cIsTemporary",
};

/** Wiki Color 模板自己的色值，游戏样式表里没有同名样式。 */
const WIKI_COLOR_HEX: Record<string, string> = {
  hallowed: "#9368F9",
  lunar: "#307FFF",
};

const STYLE_TAG_SOURCE = "<style=([A-Za-z0-9_]+)>|<\\/style>";
const HEX = /^#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i;

export type Ror2RichNode =
  | { type: "text"; text: string }
  | { type: "color"; color: string; children: Ror2RichNode[] }
  | { type: "bold"; children: Ror2RichNode[] }
  | { type: "italic"; children: Ror2RichNode[] }
  | { type: "underline"; children: Ror2RichNode[] }
  | { type: "strike"; children: Ror2RichNode[] }
  | { type: "size"; size: string; children: Ror2RichNode[] }
  | { type: "mono"; children: Ror2RichNode[] }
  | { type: "nowrap"; children: Ror2RichNode[] }
  | { type: "mark"; color: string; children: Ror2RichNode[] }
  | { type: "sprite"; name: string };

type ParentNode = Exclude<Ror2RichNode, { type: "text" } | { type: "sprite" }>;

export function parseRor2RichText(text: string): Ror2RichNode[] {
  return parseTags(expandStyles(expandWiki(text || "")));
}

export function ror2RichTextPlain(text: string): string {
  return flatten(parseRor2RichText(text));
}

function expandWiki(text: string): string {
  if (!text.includes("{{")) return text;
  let out = "";
  let index = 0;
  while (index < text.length) {
    if (text.startsWith("{{", index)) {
      const end = wikiTemplateEnd(text, index);
      out += wikiTemplateVisible(text.slice(index + 2, Math.max(index + 2, end - 2)));
      index = end;
      continue;
    }
    out += text[index];
    index += 1;
  }
  return out;
}

function wikiTemplateEnd(text: string, start: number): number {
  let depth = 0;
  let index = start;
  while (index < text.length - 1) {
    if (text.startsWith("{{", index)) {
      depth += 1;
      index += 2;
      continue;
    }
    if (text.startsWith("}}", index)) {
      depth -= 1;
      index += 2;
      if (depth === 0) return index;
      continue;
    }
    index += 1;
  }
  return text.length;
}

function wikiTemplateVisible(inner: string): string {
  const parts = splitWikiPipes(expandWiki(inner));
  const name = (parts[0] ?? "").trim().toLowerCase();
  if (name === "color") return wikiColor(parts);
  if (name === "stack") {
    const body = (parts[1] ?? "").trim();
    return body ? `<style=cStack>${body}</style>` : "";
  }
  const visible = parts.map((part) => part.trim()).filter(Boolean);
  if (visible.length <= 1) return "";
  return visible[visible.length - 1] ?? "";
}

function wikiColor(parts: string[]): string {
  if (parts.length < 3) return "";
  const key = parts[1]?.trim() ?? "";
  const body = parts[2]?.trim() ?? "";
  const style = WIKI_COLOR_STYLE[key.toLowerCase()];
  const hex = WIKI_COLOR_HEX[key.toLowerCase()];
  let wrapped = body;
  if (style) wrapped = `<style=${style}>${body}</style>`;
  else if (hex) wrapped = `<color=${hex}>${body}</color>`;
  else if (HEX.test(key)) wrapped = `<color=${key}>${body}</color>`;
  if ((parts[3] ?? "").trim()) return `<u>${wrapped}</u>`;
  return wrapped;
}

function splitWikiPipes(text: string): string[] {
  const parts: string[] = [];
  let buf = "";
  let depth = 0;
  let index = 0;
  while (index < text.length) {
    if (text.startsWith("{{", index)) {
      depth += 1;
      buf += "{{";
      index += 2;
      continue;
    }
    if (text.startsWith("}}", index) && depth > 0) {
      depth -= 1;
      buf += "}}";
      index += 2;
      continue;
    }
    if (text[index] === "|" && depth === 0) {
      parts.push(buf);
      buf = "";
      index += 1;
      continue;
    }
    buf += text[index];
    index += 1;
  }
  parts.push(buf);
  return parts;
}

function expandStyles(text: string): string {
  const closes: string[] = [];
  let out = "";
  let last = 0;
  for (const match of text.matchAll(new RegExp(STYLE_TAG_SOURCE, "gi"))) {
    const index = match.index ?? 0;
    out += text.slice(last, index);
    last = index + match[0].length;
    const name = match[1];
    if (name) {
      const style = STYLE_BY_NAME.get(name.toLowerCase());
      out += style?.open ?? "";
      closes.push(style?.close ?? "");
      continue;
    }
    if (closes.length) out += closes.pop();
  }
  out += text.slice(last);
  while (closes.length) out += closes.pop();
  return out;
}

function parseTags(text: string): Ror2RichNode[] {
  const root: Ror2RichNode[] = [];
  const stack: { kind: string; node: ParentNode }[] = [];
  let current = root;
  let cursor = 0;
  while (cursor < text.length) {
    const start = text.indexOf("<", cursor);
    if (start < 0) {
      pushText(current, text.slice(cursor));
      break;
    }
    if (start > cursor) pushText(current, text.slice(cursor, start));
    const end = text.indexOf(">", start + 1);
    if (end < 0) {
      pushText(current, text.slice(start));
      break;
    }
    const tag = text.slice(start, end + 1);
    cursor = end + 1;
    const sprite = spriteName(tag);
    if (sprite) {
      current.push({ type: "sprite", name: sprite });
      continue;
    }
    const opened = openTag(tag);
    if (opened) {
      current.push(opened.node);
      stack.push(opened);
      current = opened.node.children;
      continue;
    }
    const closed = closeKind(tag);
    if (!closed) continue;
    const top = stack[stack.length - 1];
    if (!top || top.kind !== closed) continue;
    stack.pop();
    current = stack.length ? stack[stack.length - 1].node.children : root;
  }
  return root;
}

function spriteName(tag: string): string | null {
  const match = /^<sprite\b([^<>]*)>$/i.exec(tag);
  if (!match) return null;
  return /\bname="([^"]+)"/i.exec(match[1] ?? "")?.[1] ?? "";
}

function openTag(tag: string): { kind: string; node: ParentNode } | null {
  const short = /^<#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})>$/.exec(tag);
  if (short) return colorNode(short[1]);
  const named = /^<([A-Za-z][A-Za-z0-9]*)(?:=([^<>]*))?>$/.exec(tag);
  if (!named) return null;
  const name = named[1].toLowerCase();
  const value = (named[2] || "").trim();
  if (name === "color") {
    const color = hexColor(value);
    if (!color) return null;
    return { kind: "color", node: { type: "color", color, children: [] } };
  }
  if (name === "b") return { kind: "bold", node: { type: "bold", children: [] } };
  if (name === "i") return { kind: "italic", node: { type: "italic", children: [] } };
  if (name === "u") return { kind: "underline", node: { type: "underline", children: [] } };
  if (name === "s") return { kind: "strike", node: { type: "strike", children: [] } };
  if (name === "size") {
    const size = sizeValue(value);
    if (!size) return null;
    return { kind: "size", node: { type: "size", size, children: [] } };
  }
  if (name === "mspace") return { kind: "mono", node: { type: "mono", children: [] } };
  if (name === "nobr") return { kind: "nowrap", node: { type: "nowrap", children: [] } };
  if (name === "mark") {
    const color = hexColor(value);
    if (!color) return null;
    return { kind: "mark", node: { type: "mark", color, children: [] } };
  }
  return null;
}

function colorNode(digits: string): { kind: string; node: ParentNode } | null {
  const color = hexColor(`#${digits.replace(/^#/, "")}`);
  if (!color) return null;
  return { kind: "color", node: { type: "color", color, children: [] } };
}

function closeKind(tag: string): string | null {
  const match = /^<\/([A-Za-z][A-Za-z0-9]*)>$/.exec(tag);
  if (!match) return null;
  const name = match[1].toLowerCase();
  if (name === "color") return "color";
  if (name === "b") return "bold";
  if (name === "i") return "italic";
  if (name === "u") return "underline";
  if (name === "s") return "strike";
  if (name === "size") return "size";
  if (name === "mspace") return "mono";
  if (name === "nobr") return "nowrap";
  if (name === "mark") return "mark";
  return null;
}

function hexColor(raw: string): string | null {
  const match = HEX.exec(raw.trim());
  return match ? match[0].toLowerCase() : null;
}

function sizeValue(raw: string): string | null {
  const match = /^(\d+(?:\.\d+)?)(px|em|%)$/.exec(raw.trim());
  if (!match) return null;
  const amount = Number(match[1]);
  const unit = match[2];
  if (unit === "%" && amount >= 50 && amount <= 200) return `${match[1]}%`;
  if (unit === "em" && amount >= 0.5 && amount <= 3) return `${match[1]}em`;
  if (unit === "px" && amount >= 8 && amount <= 48) return `${match[1]}px`;
  return null;
}

function pushText(nodes: Ror2RichNode[], text: string) {
  if (!text) return;
  const last = nodes[nodes.length - 1];
  if (last?.type === "text") {
    last.text += text;
    return;
  }
  nodes.push({ type: "text", text });
}

function flatten(nodes: Ror2RichNode[]): string {
  return nodes
    .map((node) => {
      if (node.type === "text") return node.text;
      if (node.type === "sprite") return "";
      return flatten(node.children);
    })
    .join("");
}
