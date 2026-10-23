import { Extension, Mark, Node, mergeAttributes } from "@tiptap/core";
import Image from "@tiptap/extension-image";
import { TableKit } from "@tiptap/extension-table";
import { NodeSelection, Plugin, PluginKey } from "@tiptap/pm/state";
import StarterKit from "@tiptap/starter-kit";
import {
  ARTICLE_ALIGN,
  ARTICLE_INDENT_MAX,
  articleAlignClass,
  articleColorClass,
  articleIndentClass,
  articleMarkClass,
  isSafeArticleHref,
  isSafeArticleImageUrl,
  cssStyleProp,
  parseArticleAlign,
  parseArticleColor,
  parseArticleIndent,
  parseArticleMark,
  type ArticleAlign as ArticleAlignValue,
} from "./articleHtml";
import { articleAttachmentHtml } from "./articleImages";
import {
  ARTICLE_MATH_BLOCK_CLASS,
  ARTICLE_MATH_INLINE_CLASS,
  normalizeArticleMath,
  renderArticleMathHtml,
} from "./articleMath";

const ALIGN_TYPES = ["paragraph", "heading", "blockquote"] as const;
const INDENT_TYPES = ["paragraph", "heading", "blockquote"] as const;

function elementAttr(element: unknown, name: string): string {
  if (element && typeof element === "object" && "getAttribute" in element) {
    return (
      (element as { getAttribute: (key: string) => string | null }).getAttribute(
        name,
      ) || ""
    );
  }
  return "";
}

function cssName(name: string): string {
  return name.replace(/[A-Z]/g, (ch) => `-${ch.toLowerCase()}`);
}

function elementStyle(element: unknown, name: string): string {
  if (element && typeof element === "object" && "style" in element) {
    const style = (element as { style?: Record<string, string> }).style;
    if (style?.[name]) return style[name];
    const kebab = cssName(name);
    if (style?.[kebab]) return style[kebab];
  }
  return (
    cssStyleProp(elementAttr(element, "style"), cssName(name)) ||
    cssStyleProp(elementAttr(element, "style"), name)
  );
}

function elementText(element: unknown): string {
  if (element && typeof element === "object" && "textContent" in element) {
    return String((element as { textContent?: string }).textContent || "");
  }
  return "";
}

function paintArticleMath(dom: HTMLElement, latex: string, display: boolean) {
  const { html, error } = renderArticleMathHtml(latex, display);
  if (error) {
    dom.textContent = latex || "?";
    dom.classList.add("article-math-error");
    dom.title = error;
    return;
  }
  dom.classList.remove("article-math-error");
  dom.removeAttribute("title");
  dom.innerHTML = html;
}

export type ArticleMathEdit = {
  latex: string;
  display: boolean;
};

function articleMathNodeView(display: boolean) {
  return ({
    node,
    getPos,
    editor,
  }: {
    node: { attrs: { latex?: string } };
    getPos: () => number | undefined;
    editor: import("@tiptap/core").Editor;
  }) => {
    const dom = document.createElement(display ? "div" : "span");
    dom.className = display ? ARTICLE_MATH_BLOCK_CLASS : ARTICLE_MATH_INLINE_CLASS;
    dom.contentEditable = "false";
    paintArticleMath(dom, String(node.attrs.latex || ""), display);
    const open = () => {
      editor.storage.articleMath?.onEdit?.({
        latex: String(node.attrs.latex || ""),
        display,
      });
      if (typeof getPos === "function") {
        const pos = getPos();
        if (typeof pos === "number") {
          editor.commands.setNodeSelection(pos);
        }
      }
    };
    dom.addEventListener("click", (event) => {
      event.preventDefault();
      open();
    });
    return {
      dom,
      ignoreMutation: () => true,
      update(updated: { type: { name: string }; attrs: { latex?: string } }) {
        const name = display ? "articleMathBlock" : "articleMath";
        if (updated.type.name !== name) return false;
        paintArticleMath(dom, String(updated.attrs.latex || ""), display);
        return true;
      },
    };
  };
}

function elementHighlightStyle(element: unknown): string {
  return (
    elementStyle(element, "backgroundColor") ||
    elementStyle(element, "background-color") ||
    cssStyleProp(elementAttr(element, "style"), "background")
  );
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    articleFigure: {
      insertArticleImage: (attrs: { src: string; alt?: string }) => ReturnType;
    };
    articleAttachment: {
      insertArticleAttachment: (attrs: {
        href: string;
        title: string;
      }) => ReturnType;
    };
    articleAlign: {
      setArticleAlign: (align: ArticleAlignValue | null) => ReturnType;
    };
    articleIndent: {
      indentArticle: () => ReturnType;
      outdentArticle: () => ReturnType;
    };
    articleColor: {
      setArticleColor: (color: string | null) => ReturnType;
    };
    articleHighlight: {
      setArticleHighlight: (mark: string | null) => ReturnType;
    };
    articleMath: {
      setArticleMath: (attrs: { latex: string; display: boolean }) => ReturnType;
    };
  }
  interface Storage {
    articleMath: {
      onEdit?: (payload: { latex: string; display: boolean }) => void;
    };
  }
}

export const ArticleImage = Image.extend({
  addAttributes() {
    return {
      src: {
        default: null,
        parseHTML: (element) => {
          const src = elementAttr(element, "src");
          return isSafeArticleImageUrl(src) ? src : null;
        },
      },
      alt: { default: null },
      title: { default: null },
      width: { default: null },
      height: { default: null },
    };
  },
  parseHTML() {
    return [
      {
        tag: "img[src]",
        getAttrs: (element) => {
          const src = elementAttr(element, "src");
          return isSafeArticleImageUrl(src) ? {} : false;
        },
      },
    ];
  },
});

export const ArticleFigcaption = Node.create({
  name: "figcaption",
  content: "inline*",
  isolating: true,
  parseHTML() {
    return [{ tag: "figcaption" }];
  },
  renderHTML({ HTMLAttributes }) {
    return ["figcaption", mergeAttributes(HTMLAttributes), 0];
  },
});

export const ArticleFigure = Node.create({
  name: "figure",
  group: "block",
  content: "image figcaption?",
  draggable: true,
  isolating: true,
  parseHTML() {
    return [{ tag: "figure" }];
  },
  renderHTML({ HTMLAttributes }) {
    return ["figure", mergeAttributes(HTMLAttributes), 0];
  },
  addCommands() {
    return {
      insertArticleImage:
        (attrs) =>
        ({ chain }) => {
          if (!attrs?.src || !isSafeArticleImageUrl(attrs.src)) return false;
          return chain()
            .insertContent({
              type: this.name,
              content: [
                {
                  type: "image",
                  attrs: { src: attrs.src, alt: attrs.alt || null },
                },
              ],
            })
            .run();
        },
    };
  },
});

export const ArticleAttachment = Extension.create({
  name: "articleAttachment",
  addCommands() {
    return {
      insertArticleAttachment:
        (attrs) =>
        ({ chain }) => {
          const href = (attrs?.href || "").trim();
          const title = attrs?.title || "";
          if (!href || !isSafeArticleHref(href)) return false;
          return chain().insertContent(articleAttachmentHtml(href, title)).run();
        },
    };
  },
});

export const ArticleMath = Node.create({
  name: "articleMath",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  addStorage() {
    return { onEdit: undefined as ((payload: ArticleMathEdit) => void) | undefined };
  },
  addAttributes() {
    return {
      latex: {
        default: "",
        parseHTML: (element) => normalizeArticleMath(elementText(element)),
        renderHTML: () => ({}),
      },
    };
  },
  parseHTML() {
    return [{ tag: `span.${ARTICLE_MATH_INLINE_CLASS}` }];
  },
  renderHTML({ node }) {
    return [
      "span",
      { class: ARTICLE_MATH_INLINE_CLASS },
      node.attrs.latex || "",
    ];
  },
  addNodeView() {
    return articleMathNodeView(false);
  },
  addCommands() {
    return {
      setArticleMath:
        ({ latex, display }) =>
        ({ editor, chain }) => {
          const src = normalizeArticleMath(latex);
          if (!src) return false;
          const nextType = display ? "articleMathBlock" : "articleMath";
          const inline = editor.isActive("articleMath");
          const block = editor.isActive("articleMathBlock");
          if ((inline && display) || (block && !display)) {
            return chain()
              .deleteSelection()
              .insertContent({ type: nextType, attrs: { latex: src } })
              .run();
          }
          if (inline) {
            return chain().updateAttributes("articleMath", { latex: src }).run();
          }
          if (block) {
            return chain()
              .updateAttributes("articleMathBlock", { latex: src })
              .run();
          }
          return chain()
            .insertContent({ type: nextType, attrs: { latex: src } })
            .run();
        },
    };
  },
});

export const ArticleMathBlock = Node.create({
  name: "articleMathBlock",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes() {
    return {
      latex: {
        default: "",
        parseHTML: (element) => normalizeArticleMath(elementText(element)),
        renderHTML: () => ({}),
      },
    };
  },
  parseHTML() {
    return [{ tag: `div.${ARTICLE_MATH_BLOCK_CLASS}` }];
  },
  renderHTML({ node }) {
    return [
      "div",
      { class: ARTICLE_MATH_BLOCK_CLASS },
      node.attrs.latex || "",
    ];
  },
  addNodeView() {
    return articleMathNodeView(true);
  },
});

export const ArticleAlign = Extension.create({
  name: "articleAlign",
  addGlobalAttributes() {
    return [
      {
        types: [...ALIGN_TYPES],
        attributes: {
          articleAlign: {
            default: null,
            parseHTML: (element) =>
              parseArticleAlign(
                elementAttr(element, "class"),
                elementStyle(element, "textAlign") || elementStyle(element, "text-align"),
              ),
            renderHTML: (attributes) => {
              const cls = articleAlignClass(attributes.articleAlign);
              return cls ? { class: cls } : {};
            },
          },
        },
      },
    ];
  },
  addCommands() {
    return {
      setArticleAlign:
        (align) =>
        ({ editor, commands }) => {
          const next = align && ARTICLE_ALIGN.includes(align) ? align : null;
          let ran = false;
          for (const type of ALIGN_TYPES) {
            if (editor.isActive(type)) {
              ran = commands.updateAttributes(type, { articleAlign: next }) || ran;
            }
          }
          return ran;
        },
    };
  },
});

export const ArticleIndent = Extension.create({
  name: "articleIndent",
  addGlobalAttributes() {
    return [
      {
        types: [...INDENT_TYPES],
        attributes: {
          articleIndent: {
            default: null,
            parseHTML: (element) => parseArticleIndent(elementAttr(element, "class")),
            renderHTML: (attributes) => {
              const cls = articleIndentClass(attributes.articleIndent);
              return cls ? { class: cls } : {};
            },
          },
        },
      },
    ];
  },
  addCommands() {
    return {
      indentArticle:
        () =>
        ({ editor, commands }) => {
          let ran = false;
          for (const type of INDENT_TYPES) {
            if (!editor.isActive(type)) continue;
            const current = Number(editor.getAttributes(type).articleIndent || 0);
            const next = Math.min(ARTICLE_INDENT_MAX, current + 1);
            ran =
              commands.updateAttributes(type, {
                articleIndent: next || null,
              }) || ran;
          }
          return ran;
        },
      outdentArticle:
        () =>
        ({ editor, commands }) => {
          let ran = false;
          for (const type of INDENT_TYPES) {
            if (!editor.isActive(type)) continue;
            const current = Number(editor.getAttributes(type).articleIndent || 0);
            const next = Math.max(0, current - 1);
            ran =
              commands.updateAttributes(type, {
                articleIndent: next || null,
              }) || ran;
          }
          return ran;
        },
    };
  },
});

export const ArticleColor = Mark.create({
  name: "articleColor",
  addAttributes() {
    return {
      color: {
        default: null,
        parseHTML: (element) =>
          parseArticleColor(
            elementAttr(element, "class"),
            elementStyle(element, "color") || elementAttr(element, "color"),
          ),
        renderHTML: (attributes) => {
          const cls = articleColorClass(attributes.color);
          return cls ? { class: cls } : {};
        },
      },
    };
  },
  parseHTML() {
    return [
      {
        tag: "span",
        getAttrs: (element) => {
          const color = parseArticleColor(
            elementAttr(element, "class"),
            elementStyle(element, "color") || elementAttr(element, "color"),
          );
          return color ? { color } : false;
        },
      },
      {
        tag: "font",
        getAttrs: (element) => {
          const color = parseArticleColor(
            elementAttr(element, "class"),
            elementStyle(element, "color") || elementAttr(element, "color"),
          );
          return color ? { color } : false;
        },
      },
    ];
  },
  renderHTML({ HTMLAttributes }) {
    return ["span", mergeAttributes(HTMLAttributes), 0];
  },
  addCommands() {
    return {
      setArticleColor:
        (color) =>
        ({ commands }) => {
          if (!color || !articleColorClass(color)) {
            return commands.unsetMark(this.name);
          }
          return commands.setMark(this.name, { color });
        },
    };
  },
});

export const ArticleHighlight = Mark.create({
  name: "articleHighlight",
  addAttributes() {
    return {
      mark: {
        default: null,
        parseHTML: (element) =>
          parseArticleMark(
            elementAttr(element, "class"),
            elementHighlightStyle(element),
          ),
        renderHTML: (attributes) => {
          const cls = articleMarkClass(attributes.mark);
          return cls ? { class: cls } : {};
        },
      },
    };
  },
  parseHTML() {
    return [
      {
        tag: "mark",
        getAttrs: (element) => {
          const mark =
            parseArticleMark(
              elementAttr(element, "class"),
              elementHighlightStyle(element),
            ) || "yellow";
          return { mark };
        },
      },
      {
        tag: "span",
        getAttrs: (element) => {
          const mark = parseArticleMark(
            elementAttr(element, "class"),
            elementHighlightStyle(element),
          );
          return mark ? { mark } : false;
        },
      },
    ];
  },
  renderHTML({ HTMLAttributes }) {
    return ["mark", mergeAttributes(HTMLAttributes), 0];
  },
  addCommands() {
    return {
      setArticleHighlight:
        (mark) =>
        ({ commands }) => {
          if (!mark || !articleMarkClass(mark)) {
            return commands.unsetMark(this.name);
          }
          return commands.setMark(this.name, { mark });
        },
    };
  },
});

export const ArticleDragHandle = Extension.create({
  name: "articleDragHandle",
  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey("articleDragHandle"),
        view(view) {
          const parent = view.dom.parentElement;
          if (!parent) return { destroy() {} };
          const handle = document.createElement("div");
          handle.className = "article-drag-handle";
          handle.textContent = "⋮⋮";
          handle.draggable = true;
          handle.setAttribute("aria-label", "拖拽段落");
          parent.appendChild(handle);
          let nodePos: number | null = null;

          const hide = () => {
            handle.style.display = "none";
            nodePos = null;
          };

          const onMove = (event: MouseEvent) => {
            if (event.buttons) return;
            const coords = view.posAtCoords({
              left: event.clientX + 28,
              top: event.clientY,
            });
            if (!coords) {
              hide();
              return;
            }
            const $pos = view.state.doc.resolve(
              coords.inside >= 0 ? coords.inside : coords.pos,
            );
            if ($pos.depth < 1) {
              hide();
              return;
            }
            const start = $pos.before(1);
            const dom = view.nodeDOM(start);
            if (!(dom instanceof HTMLElement)) {
              hide();
              return;
            }
            const rect = dom.getBoundingClientRect();
            const parentRect = parent.getBoundingClientRect();
            nodePos = start;
            handle.style.display = "flex";
            handle.style.top = `${rect.top - parentRect.top + parent.scrollTop}px`;
            handle.style.left = `${Math.max(0, rect.left - parentRect.left - 22)}px`;
          };

          handle.addEventListener("mousedown", () => {
            if (nodePos == null) return;
            view.dispatch(
              view.state.tr.setSelection(
                NodeSelection.create(view.state.doc, nodePos),
              ),
            );
            view.focus();
          });

          handle.addEventListener("dragstart", (event) => {
            if (nodePos == null) {
              event.preventDefault();
              return;
            }
            const selection = NodeSelection.create(view.state.doc, nodePos);
            view.dispatch(view.state.tr.setSelection(selection));
            view.dragging = { slice: selection.content(), move: true };
            if (event.dataTransfer) {
              event.dataTransfer.setData("text/plain", " ");
              event.dataTransfer.effectAllowed = "move";
              event.dataTransfer.setDragImage(handle, 8, 12);
            }
            handle.style.cursor = "grabbing";
          });
          handle.addEventListener("dragend", () => {
            handle.style.cursor = "grab";
            view.dragging = null;
          });

          view.dom.addEventListener("mousemove", onMove);
          parent.addEventListener("mouseleave", hide);
          return {
            destroy() {
              view.dom.removeEventListener("mousemove", onMove);
              parent.removeEventListener("mouseleave", hide);
              handle.remove();
            },
          };
        },
      }),
    ];
  },
});

export function articleSchemaExtensions() {
  return [
    StarterKit.configure({
      heading: { levels: [1, 2, 3, 4, 5, 6] },
      link: {
        openOnClick: false,
        autolink: true,
        defaultProtocol: "https",
        HTMLAttributes: { rel: "noopener noreferrer" },
        isAllowedUri: (url) => isSafeArticleHref(url || ""),
      },
    }),
    ArticleAttachment,
    ArticleImage,
    ArticleFigcaption,
    ArticleFigure,
    TableKit.configure({
      table: { resizable: false },
    }),
    ArticleAlign,
    ArticleIndent,
    ArticleColor,
    ArticleHighlight,
    ArticleMath,
    ArticleMathBlock,
  ];
}

export type ArticleSlashItem = {
  id: string;
  title: string;
  keywords: string;
  run: (editor: import("@tiptap/core").Editor) => boolean;
};

export function articleSlashItems(): ArticleSlashItem[] {
  return [
    {
      id: "paragraph",
      title: "正文",
      keywords: "正文 paragraph p",
      run: (editor) => editor.chain().focus().setParagraph().run(),
    },
    {
      id: "h2",
      title: "标题 2",
      keywords: "标题 h2 heading",
      run: (editor) => editor.chain().focus().toggleHeading({ level: 2 }).run(),
    },
    {
      id: "h3",
      title: "标题 3",
      keywords: "标题 h3 heading",
      run: (editor) => editor.chain().focus().toggleHeading({ level: 3 }).run(),
    },
    {
      id: "h4",
      title: "标题 4",
      keywords: "标题 h4 heading",
      run: (editor) => editor.chain().focus().toggleHeading({ level: 4 }).run(),
    },
    {
      id: "quote",
      title: "引用",
      keywords: "引用 quote blockquote",
      run: (editor) => editor.chain().focus().toggleBlockquote().run(),
    },
    {
      id: "code",
      title: "代码块",
      keywords: "代码 code",
      run: (editor) => editor.chain().focus().toggleCodeBlock().run(),
    },
    {
      id: "ul",
      title: "无序列表",
      keywords: "列表 ul bullet",
      run: (editor) => editor.chain().focus().toggleBulletList().run(),
    },
    {
      id: "ol",
      title: "有序列表",
      keywords: "列表 ol numbered",
      run: (editor) => editor.chain().focus().toggleOrderedList().run(),
    },
    {
      id: "table",
      title: "表格",
      keywords: "表格 table",
      run: (editor) =>
        editor
          .chain()
          .focus()
          .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
          .run(),
    },
    {
      id: "hr",
      title: "分隔线",
      keywords: "分隔 hr line",
      run: (editor) => editor.chain().focus().setHorizontalRule().run(),
    },
    {
      id: "math",
      title: "行内公式",
      keywords: "公式 math latex 行内",
      run: (editor) => {
        const onEdit = editor.storage.articleMath?.onEdit;
        if (onEdit) {
          onEdit({ latex: "", display: false });
          return true;
        }
        return editor
          .chain()
          .focus()
          .setArticleMath({ latex: "E=mc^2", display: false })
          .run();
      },
    },
    {
      id: "math-block",
      title: "独立公式",
      keywords: "公式 math latex 块",
      run: (editor) => {
        const onEdit = editor.storage.articleMath?.onEdit;
        if (onEdit) {
          onEdit({ latex: "", display: true });
          return true;
        }
        return editor
          .chain()
          .focus()
          .setArticleMath({ latex: "E=mc^2", display: true })
          .run();
      },
    },
  ];
}

export function filterArticleSlashItems(
  items: ArticleSlashItem[],
  query: string,
): ArticleSlashItem[] {
  const q = (query || "").trim().toLowerCase();
  if (!q) return items;
  return items.filter(
    (item) =>
      item.title.toLowerCase().includes(q) ||
      item.keywords.toLowerCase().includes(q),
  );
}
