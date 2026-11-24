# 塔科夫设计系统

此目录由 Stats 维护。`src/index.css` 提供主题令牌、字体和基础控件，`src/tokens.js` 为 Ant Design 主题提供同一份令牌。

修改 [`tokens/tarkov.json`](tokens/tarkov.json) 后，在 `frontend/` 运行：

```bash
node design-system/scripts/generate-tokens.mjs
npm run tokens:check
```

不要手工编辑生成的 `src/tokens.css`、`src/tokens.js` 和 `src/tokens.d.ts`。静态 Release 将 [`licenses/fonts/`](licenses/fonts/) 中的许可证放入同名目录。
