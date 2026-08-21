"""One-shot writer for Minecraft setup picker icons."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "public" / "minecraft-icons"

ICONS = {
    "vanilla.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path fill="#6fb83e" d="M32 6 58 19 32 32 6 19Z"/>
  <path fill="#3e7a22" d="M6 19 32 32v4L6 23Z"/>
  <path fill="#7a4a22" d="M6 19 32 32v26L6 45Z"/>
  <path fill="#5c3718" d="M32 32 58 19v26L32 58Z"/>
</svg>
""",
    "snapshot.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path fill="#f0b429" d="M32 6 58 19 32 32 6 19Z"/>
  <path fill="#c47a14" d="M6 19 32 32v26L6 45Z"/>
  <path fill="#a65f10" d="M32 32 58 19v26L32 58Z"/>
  <rect x="24" y="22" width="16" height="10" rx="1.5" fill="#ffe08a"/>
  <rect x="27" y="34" width="10" height="6" rx="1" fill="#6b3f0d"/>
</svg>
""",
    "old.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path fill="#b0b0b0" d="M32 6 58 19 32 32 6 19Z"/>
  <path fill="#6e6e6e" d="M6 19 32 32v26L6 45Z"/>
  <path fill="#555" d="M32 32 58 19v26L32 58Z"/>
</svg>
""",
    "fool.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <rect x="12" y="28" width="40" height="20" rx="2" fill="#f2d6de"/>
  <rect x="12" y="44" width="40" height="4" fill="#e8b4c4"/>
  <rect x="10" y="24" width="44" height="6" rx="2" fill="#fff7ea"/>
  <rect x="28" y="14" width="8" height="12" rx="1" fill="#c45c7a"/>
  <circle cx="32" cy="14" r="5" fill="#e8789a"/>
</svg>
""",
    "fabric.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#1b1814"/>
  <g fill="none" stroke-linecap="round">
    <ellipse cx="32" cy="34" rx="16" ry="12" stroke="#cfc0a8" stroke-width="5"/>
    <ellipse cx="32" cy="30" rx="12" ry="9" stroke="#e8dcc8" stroke-width="4"/>
    <path d="M24 22c8-8 18-6 22 2" stroke="#d7c4a6" stroke-width="5"/>
    <path d="M20 36c4 10 20 12 26 2" stroke="#b9a78c" stroke-width="4"/>
  </g>
  <circle cx="38" cy="24" r="3" fill="#f0e6d4"/>
</svg>
""",
    "forge.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#2b241c"/>
  <path fill="#e6c07b" d="M12 20h40l-6 8H18z"/>
  <path fill="#d4a45a" d="M22 28h20v7H22z"/>
  <path fill="#c4923e" d="M26 35h12v12H26z"/>
  <path fill="#e8d5a3" d="M16 47h32v5H16z"/>
</svg>
""",
    "neoforge.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#f6f1ea"/>
  <path fill="#e07828" d="M18 28 24 8l10 18"/>
  <path fill="#c45e18" d="M46 28 40 8 30 26"/>
  <ellipse cx="32" cy="38" rx="18" ry="16" fill="#f08a32"/>
  <ellipse cx="32" cy="45" rx="10" ry="8" fill="#f4d7b8"/>
  <circle cx="26" cy="36" r="2.4" fill="#2a1810"/>
  <circle cx="38" cy="36" r="2.4" fill="#2a1810"/>
  <ellipse cx="32" cy="42.5" rx="2.2" ry="1.5" fill="#2a1810"/>
</svg>
""",
    "spigot.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#1e1e1e"/>
  <path fill="#d8d8d8" d="M14 22h16v8H14z"/>
  <path fill="#c0c0c0" d="M26 26h18v8H26z"/>
  <path fill="#e8a317" d="M42 24h8v12h-4l-4 8h-6l4-8h-2z"/>
  <circle cx="22" cy="18" r="5" fill="#bcbcbc"/>
  <rect x="20" y="12" width="4" height="8" rx="1" fill="#9a9a9a"/>
</svg>
""",
    "purpur.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#2a1638"/>
  <path fill="#c48ae8" d="M32 8 52 24 32 28 12 24Z"/>
  <path fill="#8d4ec2" d="M12 24 32 28v26L12 40Z"/>
  <path fill="#6b34a0" d="M32 28 52 24v16L32 54Z"/>
  <path fill="#e0b4ff" opacity=".7" d="M32 8 42 16 32 20 22 16Z"/>
</svg>
""",
    "mohist.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#f4efe9"/>
  <path fill="#c56d3d" d="M14 48V16h12l6 14 6-14h12v32H40V30l-8 14-8-14v18H14z"/>
</svg>
""",
    "arclight.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#16132a"/>
  <path d="M16 42c8-18 24-18 32 0" fill="none" stroke="#7dd3fc" stroke-width="4" stroke-linecap="round"/>
  <path d="M20 36c6-12 18-12 24 0" fill="none" stroke="#c4b5fd" stroke-width="3" stroke-linecap="round"/>
  <circle cx="32" cy="22" r="6" fill="#fde68a"/>
  <path d="M32 28v10" stroke="#fde68a" stroke-width="3" stroke-linecap="round"/>
</svg>
""",
    "youer.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#1b1814"/>
  <path fill="#e8d5c0" d="M14 48V16h12l6 14 6-14h12v32H40V30l-8 14-8-14v18H14z"/>
  <circle cx="50" cy="50" r="7" fill="#db2777"/>
</svg>
""",
    "banner.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#3b2a18"/>
  <rect x="18" y="10" width="4" height="44" rx="1" fill="#d6c4a8"/>
  <path fill="#c45c3a" d="M22 14h24l-6 10 6 10H22z"/>
  <path fill="#e8c36a" d="M26 18h12v4H26z"/>
</svg>
""",
    "catserver.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#fff6ea"/>
  <path fill="#f0a020" d="M16 28 24 10l10 16M48 28 40 10 30 26"/>
  <ellipse cx="32" cy="38" rx="18" ry="16" fill="#f2b84a"/>
  <ellipse cx="32" cy="44" rx="9" ry="7" fill="#ffe4b8"/>
  <circle cx="26" cy="36" r="2.2" fill="#3a2410"/>
  <circle cx="38" cy="36" r="2.2" fill="#3a2410"/>
  <ellipse cx="32" cy="42" rx="2" ry="1.4" fill="#3a2410"/>
</svg>
""",
    "kind-mod.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#efe6d8"/>
  <path fill="#d4b07a" d="M16 18h32l4 8H12z"/>
  <path fill="#c9a36a" d="M12 26h40v24H12z"/>
  <path fill="#a67c42" d="M12 26h40v8H12z"/>
  <path fill="#8a6230" d="M30 34h4v10h-4z"/>
</svg>
""",
    "kind-plugin.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#eef6e4"/>
  <rect x="16" y="12" width="28" height="40" rx="3" fill="#7db53a"/>
  <rect x="20" y="18" width="20" height="4" rx="1" fill="#eef6e4"/>
  <rect x="20" y="26" width="16" height="3" rx="1" fill="#d7e8b0"/>
  <rect x="20" y="32" width="16" height="3" rx="1" fill="#d7e8b0"/>
  <circle cx="46" cy="44" r="10" fill="#f0c040"/>
  <path fill="#c99212" d="M44 38h4v14h-4z"/>
</svg>
""",
    "kind-hybrid.svg": """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#ece7f4"/>
  <path fill="#2b241c" d="M8 8h24v48H8z"/>
  <path fill="#e6c07b" d="M12 20h16l-3 6H15z"/>
  <path fill="#d4a45a" d="M18 26h8v14h-8z"/>
  <path fill="#8fbf3a" d="M32 8h24v48H32z"/>
  <rect x="38" y="16" width="12" height="4" rx="1" fill="#eef6e4"/>
  <rect x="38" y="24" width="10" height="3" rx="1" fill="#d7e8b0"/>
  <circle cx="50" cy="44" r="7" fill="#f0c040"/>
</svg>
""",
}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, svg in ICONS.items():
        (ROOT / name).write_text(svg.strip() + "\n", encoding="utf-8")
        print(name)


if __name__ == "__main__":
    main()
