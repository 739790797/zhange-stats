# 钥匙识别实图夹具

跑的是弹窗同一条路：`recognizeKeyboxScreenshot`（找格 → 图标/颜色匹配 → 撞图才读短名 OCR）。

图标指纹：`npx vite-node scripts/build-key-icon-index.mts` 生成 `src/lib/tarkovKeyIconIndex.json`。

| 文件 | 来源 |
|---|---|
| `01-thirdparty-keybox.png` | 第三方钥匙箱（绿勾、10/10） |
| `02-native-keybox.png` | 游戏原生钥匙箱 11/11 |
| `03-customs-storage.png` | 钥匙收纳 · 海关1 |
| `04-mixed-keybox.png` | 原生钥匙箱（停车场 / RB / 宿舍混装） |

```bash
# frontend/
npx vite-node scripts/ocr-key-corpus/run.mts
# 连跑：
# $env:OCR_REPEAT=5; npx vite-node scripts/ocr-key-corpus/repeat.mts
```

`expected.json`：`expect` 必须勾上，`forbid` 不能误勾，`stretch` 是图上有但当前分辨率经常读不出的（不挡回归）。

`prepare.py` 只用来画调试叠图，**不参与打分**。
