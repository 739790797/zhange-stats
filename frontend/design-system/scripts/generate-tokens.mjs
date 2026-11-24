import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
if (args.length > 1 || args.some((arg) => arg !== "--check")) {
  console.error("Usage: node design-system/scripts/generate-tokens.mjs [--check]");
  process.exit(2);
}
const checkOnly = args.includes("--check");

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = path.join(packageRoot, "tokens", "tarkov.json");
const tokens = JSON.parse(await readFile(sourcePath, "utf8"));

function kebab(value) {
  return value.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
}

const cssLines = [
  "/* Generated from tokens/tarkov.json. Do not edit directly. */",
  ".zhange-theme-tarkov {",
  "  color-scheme: dark;",
];
for (const [group, values] of Object.entries(tokens)) {
  if (!values || typeof values !== "object" || Array.isArray(values)) {
    if (typeof values === "string") cssLines.push(`  --zhange-${kebab(group)}: ${values};`);
    continue;
  }
  for (const [name, value] of Object.entries(values)) {
    if (typeof value === "number") continue;
    const prefix = group === "border" ? "border" : group;
    cssLines.push(`  --zhange-${prefix}-${kebab(name)}: ${value};`);
  }
}
cssLines.push(
  "",
  "  /* Compatibility aliases for legacy Tarkov app styles. */",
  "  --hb-bg: var(--zhange-color-bg);",
  "  --hb-panel: var(--zhange-color-panel);",
  "  --hb-panel-hover: var(--zhange-color-panel-hover);",
  "  --hb-border: var(--zhange-color-border);",
  "  --hb-orange: var(--zhange-color-accent);",
  "  --hb-orange-dim: var(--zhange-color-accent-dim);",
  "  --hb-green: var(--zhange-color-positive);",
  "  --hb-text: var(--zhange-color-text);",
  "  --hb-muted: var(--zhange-color-text-muted);",
  "  --hb-mono: var(--zhange-font-mono);",
  "  --hb-sans: var(--zhange-font-sans);",
  "  --hb-display: var(--zhange-font-display);",
  "}",
  "",
);

const jsOutput = `/* Generated from tokens/tarkov.json. Do not edit directly. */\nexport const TARKOV_TOKENS = ${JSON.stringify(tokens, null, 2)};\n`;

function declaration(value, depth = 0) {
  const indent = "  ".repeat(depth);
  const childIndent = "  ".repeat(depth + 1);
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const entries = Object.entries(value).map(([key, child]) => {
      const childDeclaration = declaration(child, depth + 1);
      const separator = childDeclaration.startsWith("\n") ? "" : " ";
      return `${childIndent}readonly ${JSON.stringify(key)}:${separator}${childDeclaration};`;
    });
    return `\n{\n${entries.join("\n")}\n${indent}}`;
  }
  return JSON.stringify(value);
}

const dtsOutput = `/* Generated from tokens/tarkov.json. Do not edit directly. */\nexport declare const TARKOV_TOKENS:${declaration(tokens)};\n`;

const outputs = new Map([
  [path.join(packageRoot, "src", "tokens.css"), cssLines.join("\n")],
  [path.join(packageRoot, "src", "tokens.js"), jsOutput],
  [path.join(packageRoot, "src", "tokens.d.ts"), dtsOutput],
]);

if (checkOnly) {
  const staleFiles = [];
  for (const [filePath, expected] of outputs) {
    let actual;
    try {
      actual = await readFile(filePath, "utf8");
    } catch (error) {
      if (error.code === "ENOENT") {
        staleFiles.push(path.relative(packageRoot, filePath));
        continue;
      }
      throw error;
    }

    if (actual.replace(/\r\n?/g, "\n") !== expected) {
      staleFiles.push(path.relative(packageRoot, filePath));
    }
  }

  if (staleFiles.length > 0) {
    console.error("Generated token artifacts are missing or stale:");
    for (const filePath of staleFiles) console.error(`- ${filePath}`);
    console.error("Run node design-system/scripts/generate-tokens.mjs to update them.");
    process.exitCode = 1;
  } else {
    console.log("Generated token artifacts are up to date.");
  }
} else {
  await Promise.all(
    [...outputs].map(([filePath, content]) => writeFile(filePath, content, "utf8")),
  );
  console.log("Generated token artifacts from design-system/tokens/tarkov.json.");
}
