# 自托管攻略字体资产

攻略壳使用随 feature 提交的本地字体，不依赖运行时 Google Fonts 请求。

| Feature | 文件 | 许可/说明 |
|---|---|---|
| `tarkov/assets/fonts/` | IBM Plex Sans、IBM Plex Mono、Rajdhani 拉丁子集 | SIL Open Font License 1.1；许可文件与字体并置。
| `ror2/assets/fonts/` | Bombardier | DaFont 100% Free；`Bombardier-NOTICE.txt` 与字体并置。

Tarkov 的 CJK 字体仍由 `tarkov/components/tarkovFonts.css` 回落到本机黑体；雨中冒险 2 的汉字同样回落到本机黑体。再分发时保留对应 feature 的许可/notice 文件。
