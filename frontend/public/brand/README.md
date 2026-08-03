# ZHANGE / 战鸽 Brand Marks

基于原图矢量重绘，并按使用场景做小尺寸优化。

| 文件 | 用途 | 说明 |
|------|------|------|
| logo-mark.svg | 图标独用 | 翅缝略加宽，结构贴近原图（空心头 + Z + 三翅） |
| logo-favicon.svg | 极简实心标 | 合并缝隙并填实，适合 16–32px |
| logo-horizontal.svg | 横版锁稿 | 图标 + ZHANGE（保留 A 横杠）+ 战鸽 |
| logo-stacked.svg | 竖版锁稿 | 竖排；两侧短线加粗 |
| logo-original-trace.svg | 对照参考 | 原图自动描摹 |

站点 ../favicon.svg 已换为深底 #1a2332 + 金色实心标。

字标用系统字体；印刷定稿建议在 Figma/Illustrator 转曲。

`ash
python _gen_from_original.py
node _preview_render.cjs
`
