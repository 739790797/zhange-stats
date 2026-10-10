// 用 backend 的 Python 跑 backend/scripts/export_openapi.py，写出 src/api/generated/openapi.json。
// 解释器顺序：backend/.venv（Linux/macOS、Windows 两种布局）→ PATH 上的 python3 / python。
// 用法：node scripts/export-openapi.mjs [--dry-run]（--dry-run 只打印将执行的命令）
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const backendDir = resolve(dirname(fileURLToPath(import.meta.url)), "../../backend");
const exportScript = join("scripts", "export_openapi.py");
const dryRun = process.argv.includes("--dry-run");

function resolvePython() {
  for (const rel of [join(".venv", "bin", "python"), join(".venv", "Scripts", "python.exe")]) {
    const full = join(backendDir, rel);
    if (existsSync(full)) return full;
  }
  // Windows 自带的 python3 常是应用商店占位程序，跑起来直接失败；先试 python，并实际探一下能不能启动。
  const names = process.platform === "win32" ? ["python", "python3"] : ["python3", "python"];
  for (const name of names) {
    const probe = spawnSync(name, ["-c", "import sys"], { stdio: "ignore" });
    if (probe.status === 0) return name;
  }
  return null;
}

const python = resolvePython();
if (!python) {
  console.error(
    "export:openapi: 找不到 Python。请先在 backend/ 建好 .venv（见 docs/develop.md），或把 python3 / python 加进 PATH。",
  );
  process.exit(1);
}

console.log(`export:openapi: ${python} ${exportScript} (cwd ${backendDir})`);
if (dryRun) process.exit(0);

const result = spawnSync(python, [exportScript], { cwd: backendDir, stdio: "inherit" });
if (result.error) {
  console.error(`export:openapi: 无法启动 ${python}: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
