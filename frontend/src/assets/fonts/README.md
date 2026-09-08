# 自托管拉丁字体（SIL OFL）

塔科夫壳用的拉丁子集 woff2，**不**再走 Google Fonts。

| 文件 | 字体 | 许可 |
|------|------|------|
| `ibm-plex-sans-latin-*.woff2` | [IBM Plex Sans](https://github.com/IBM/plex) | SIL Open Font License 1.1 |
| `ibm-plex-mono-latin-*.woff2` | [IBM Plex Mono](https://github.com/IBM/plex) | SIL Open Font License 1.1 |
| `rajdhani-latin-*.woff2` | [Rajdhani](https://github.com/itfoundry/rajdhani) | SIL Open Font License 1.1 |

仅 `TarkovGuideShell` 引入；汉字仍由 `tarkovFonts.css` 的 CJK `@font-face` 走本机黑体。

再分发时附带本目录 `IBM-Plex-LICENSE.txt` 与 `Rajdhani-OFL.txt`（SIL OFL 1.1 全文）。
