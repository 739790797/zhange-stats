// 只读：列出 src 下 *.module.css 里没有任何导入方引用的类，以及导入方引用了、模块里却没定义的类（渲染成 undefined）。
// 用法：node scripts/find-unused-css-modules.mjs [--verbose]
// 动态取类（styles[expr]）按导入方里的字符串字面量 / 模板前后缀从宽认定，仍需人工看一眼 --verbose 的列表。
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const srcRoot = join(frontendRoot, "src");
const verbose = process.argv.includes("--verbose");

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

function blankComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
}

function stripGlobal(selector) {
  let out = "";
  let i = 0;
  while (i < selector.length) {
    if (selector.startsWith(":global(", i)) {
      let depth = 0;
      let j = i + ":global".length;
      for (; j < selector.length; j++) {
        if (selector[j] === "(") depth++;
        else if (selector[j] === ")" && --depth === 0) break;
      }
      i = j + 1;
      continue;
    }
    out += selector[i++];
  }
  return out;
}

function selectorClasses(selector) {
  const s = stripGlobal(selector)
    .replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, '""')
    .replace(/\[[^\]]*\]/g, "");
  return [...s.matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)].map((m) => m[1]);
}

/** 类名 → 首次出现的行号；只看规则选择器，不看声明值。 */
function cssClasses(css) {
  const text = blankComments(css);
  const classes = new Map();
  let prelude = "";
  let preludeLine = 1;
  let line = 1;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"' || ch === "'") {
      const end = text.indexOf(ch, i + 1);
      const chunk = text.slice(i, end < 0 ? text.length : end + 1);
      prelude += chunk;
      line += chunk.split("\n").length - 1;
      i += chunk.length - 1;
      continue;
    }
    if (ch === "{") {
      const head = prelude.trim();
      if (head && !head.startsWith("@")) {
        for (const name of selectorClasses(head)) {
          if (!classes.has(name)) classes.set(name, preludeLine);
        }
      }
      prelude = "";
    } else if (ch === "}" || ch === ";") {
      prelude = "";
    } else {
      if (!prelude.trim() && ch.trim()) preludeLine = line;
      prelude += ch;
    }
    if (ch === "\n") line++;
  }
  return classes;
}

function matchingBracket(text, open) {
  let depth = 0;
  for (let i = open; i < text.length; i++) {
    if (text[i] === "[") depth++;
    else if (text[i] === "]" && --depth === 0) return i;
  }
  return -1;
}

function templatePattern(body) {
  const parts = body.split(/\$\{[^}]*\}/);
  const escaped = parts.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return new RegExp(`^${escaped.join("[\\w-]*")}$`);
}

function lineOf(text, index) {
  return text.slice(0, index).split("\n").length;
}

/** 收集导入方对某个 CSS 模块对象的取用：静态名、模板模式、其余动态表达式、整体外传。 */
function collectUsage(code, id) {
  const usage = { names: new Set(), patterns: [], dynamic: [], escapes: [] };
  const re = new RegExp(`(?<![\\w$.])${id}(?![\\w$])`, "g");
  for (const m of code.matchAll(re)) {
    const at = m.index + id.length;
    const rest = code.slice(at);
    const prop = /^\s*(?:\?\.|\.)\s*([A-Za-z_$][\w$]*)/.exec(rest);
    if (prop) {
      usage.names.add(prop[1]);
      continue;
    }
    const bracket = /^\s*(?:\?\.)?\s*\[/.exec(rest);
    if (bracket) {
      const open = at + bracket[0].length - 1;
      const close = matchingBracket(code, open);
      const expr = code.slice(open + 1, close).trim();
      const literal = /^(["'])([^"'\\]*)\1$/.exec(expr) ?? /^`([^`$]*)`$/.exec(expr);
      if (literal) usage.names.add(literal[2] ?? literal[1]);
      else if (/^`[^`]*`$/.test(expr)) usage.patterns.push({ re: templatePattern(expr.slice(1, -1)), line: lineOf(code, m.index), expr });
      else usage.dynamic.push({ line: lineOf(code, m.index), expr });
      continue;
    }
    const before = code.slice(Math.max(0, m.index - 7), m.index);
    if (before === "import ") continue;
    // 同名的 JSX 属性 / 对象键（如 antd 的 styles={{...}}）不是模块对象。
    if (/^\s*(?:=(?!=)|:)/.test(rest)) continue;
    usage.escapes.push({ line: lineOf(code, m.index), snippet: code.slice(m.index, m.index + 60).split("\n")[0] });
  }
  return usage;
}

function stringLiterals(code) {
  const out = new Set();
  for (const m of code.matchAll(/(["'`])([A-Za-z_-][\w-]*)\1/g)) out.add(m[2]);
  return out;
}

const files = walk(srcRoot);
const modules = new Map();
for (const file of files.filter((f) => f.endsWith(".module.css"))) {
  modules.set(file, { classes: cssClasses(readFileSync(file, "utf8")), importers: [] });
}

const importRe = /import\s+([A-Za-z_$][\w$]*)\s+from\s+["']([^"']+\.module\.css)["']/g;
for (const file of files.filter((f) => /\.(tsx?|jsx?|mts)$/.test(f))) {
  const code = readFileSync(file, "utf8");
  for (const m of code.matchAll(importRe)) {
    const spec = m[2];
    const target = spec.startsWith("@/") ? join(srcRoot, spec.slice(2)) : resolve(dirname(file), spec);
    const mod = modules.get(target);
    if (!mod) continue;
    mod.importers.push({ file, id: m[1], code, usage: collectUsage(code, m[1]) });
  }
}

let unusedTotal = 0;
let classTotal = 0;
const rows = [];
const missing = [];
for (const [file, mod] of [...modules].sort(([a], [b]) => a.localeCompare(b))) {
  const rel = relative(frontendRoot, file);
  classTotal += mod.classes.size;
  const used = new Set();
  const viaLiteral = new Set();
  const notes = [];
  for (const imp of mod.importers) {
    const where = relative(frontendRoot, imp.file);
    for (const name of imp.usage.names) {
      used.add(name);
      if (!mod.classes.has(name)) missing.push(`${where}: ${imp.id}.${name} (not in ${rel})`);
    }
    for (const p of imp.usage.patterns) {
      for (const name of mod.classes.keys()) if (p.re.test(name)) used.add(name);
      notes.push(`  pattern ${where}:${p.line} ${imp.id}[${p.expr}]`);
    }
    if (imp.usage.dynamic.length || imp.usage.escapes.length) {
      const literals = stringLiterals(imp.code);
      for (const name of mod.classes.keys()) if (literals.has(name)) viaLiteral.add(name);
    }
    for (const d of imp.usage.dynamic) notes.push(`  dynamic ${where}:${d.line} ${imp.id}[${d.expr}]`);
    for (const e of imp.usage.escapes) notes.push(`  escapes ${where}:${e.line} ${e.snippet}`);
  }
  const unused = [...mod.classes].filter(([name]) => !used.has(name) && !viaLiteral.has(name));
  const literalOnly = [...mod.classes.keys()].filter((name) => !used.has(name) && viaLiteral.has(name));
  unusedTotal += unused.length;
  if (!mod.importers.length) notes.unshift("  (no importers)");
  if (unused.length || (verbose && (notes.length || literalOnly.length))) {
    rows.push(`${rel}: ${unused.length}/${mod.classes.size} unused`);
    for (const [name, line] of unused) rows.push(`  .${name} (line ${line})`);
    if (verbose) {
      if (literalOnly.length) rows.push(`  kept via string literal in importer: ${literalOnly.join(", ")}`);
      rows.push(...notes);
    }
  }
}

if (missing.length) rows.push("referenced but not defined:", ...missing.map((m) => `  ${m}`));
console.log(rows.join("\n"));
console.log(`\n${modules.size} modules, ${classTotal} classes, ${unusedTotal} unused, ${missing.length} undefined references`);
process.exitCode = unusedTotal || missing.length ? 1 : 0;
