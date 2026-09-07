import {
  AlignCenterOutlined,
  AlignLeftOutlined,
  AlignRightOutlined,
  BoldOutlined,
  CodeOutlined,
  FontColorsOutlined,
  HighlightOutlined,
  ItalicOutlined,
  LinkOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MinusOutlined,
  OrderedListOutlined,
  PaperClipOutlined,
  PictureOutlined,
  RedoOutlined,
  SearchOutlined,
  StrikethroughOutlined,
  TableOutlined,
  UnderlineOutlined,
  UndoOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import type { Editor } from "@tiptap/react";
import { useEditorState } from "@tiptap/react";
import {
  Button,
  Dropdown,
  Input,
  Modal,
  Popover,
  Space,
  Tooltip,
} from "antd";
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import {
  ARTICLE_COLORS,
  ARTICLE_MARKS,
  findTextRanges,
  isSafeArticleHref,
  type ArticleAlign,
} from "@/lib/articleHtml";
import {
  ARTICLE_ATTACHMENT_ACCEPT,
  type ArticleUploadedAsset,
} from "@/lib/articleImages";
import type { ArticleMathEdit } from "@/lib/articleTiptap";
import styles from "./TavernEdit.module.css";

function currentMathEdit(editor: Editor): ArticleMathEdit {
  if (editor.isActive("articleMath")) {
    return {
      latex: String(editor.getAttributes("articleMath").latex || ""),
      display: false,
    };
  }
  if (editor.isActive("articleMathBlock")) {
    return {
      latex: String(editor.getAttributes("articleMathBlock").latex || ""),
      display: true,
    };
  }
  return {
    latex: editor.state.doc
      .textBetween(editor.state.selection.from, editor.state.selection.to, "")
      .trim(),
    display: false,
  };
}

function hotkeyTitle(label: string, keys: string): string {
  const mac =
    typeof navigator !== "undefined" &&
    /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  return `${label}（${keys.replace(/Ctrl/g, mac ? "⌘" : "Ctrl")}）`;
}

function Tool({
  title,
  active,
  disabled,
  onClick,
  children,
}: {
  title: string;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <Tooltip title={title}>
      <Button
        type="text"
        size="small"
        disabled={disabled}
        className={active ? styles.toolActive : undefined}
        onClick={onClick}
      >
        {children}
      </Button>
    </Tooltip>
  );
}

export function ArticleToolbar({
  editor,
  disabled,
  uploadFiles,
  onFindRef,
  onLinkRef,
  onMathRef,
}: {
  editor: Editor;
  disabled?: boolean;
  uploadFiles: (files: File[]) => Promise<ArticleUploadedAsset[]>;
  onFindRef?: MutableRefObject<() => void>;
  onLinkRef?: MutableRefObject<() => void>;
  onMathRef?: MutableRefObject<(payload: ArticleMathEdit) => void>;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const attachRef = useRef<HTMLInputElement>(null);
  const [linkOpen, setLinkOpen] = useState(false);
  const [href, setHref] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [replaceWith, setReplaceWith] = useState("");
  const [findHint, setFindHint] = useState("");
  const state = useEditorState({
    editor,
    selector: ({ editor: current }) => ({
      bold: current.isActive("bold"),
      italic: current.isActive("italic"),
      underline: current.isActive("underline"),
      strike: current.isActive("strike"),
      code: current.isActive("code"),
      bullet: current.isActive("bulletList"),
      ordered: current.isActive("orderedList"),
      quote: current.isActive("blockquote"),
      codeBlock: current.isActive("codeBlock"),
      link: current.isActive("link"),
      table: current.isActive("table"),
      heading: current.isActive("heading")
        ? Number(current.getAttributes("heading").level || 0)
        : 0,
      align: (current.getAttributes("paragraph").articleAlign ||
        current.getAttributes("heading").articleAlign ||
        current.getAttributes("blockquote").articleAlign ||
        null) as ArticleAlign | null,
      color: (current.getAttributes("articleColor").color || null) as
        | string
        | null,
      mark: (current.getAttributes("articleHighlight").mark || null) as
        | string
        | null,
      math:
        current.isActive("articleMath") || current.isActive("articleMathBlock"),
    }),
  });

  const locked = Boolean(disabled);

  useEffect(() => {
    if (onFindRef) {
      onFindRef.current = () => setFindOpen(true);
    }
    if (onLinkRef) {
      onLinkRef.current = () => {
        setHref(editor.getAttributes("link").href || "");
        setLinkOpen(true);
      };
    }
    return () => {
      if (onFindRef) onFindRef.current = () => undefined;
      if (onLinkRef) onLinkRef.current = () => undefined;
    };
  }, [editor, onFindRef, onLinkRef]);

  const headingValue = state.heading === 2 || state.heading === 3 || state.heading === 4
    ? String(state.heading)
    : "p";

  const applyLink = () => {
    const next = href.trim();
    if (!next) {
      editor.chain().focus().unsetLink().run();
      setLinkOpen(false);
      return;
    }
    if (!isSafeArticleHref(next)) return;
    editor
      .chain()
      .focus()
      .setLink({ href: next, rel: "noopener noreferrer" })
      .run();
    setLinkOpen(false);
  };

  const collectChunks = () => {
    const chunks: { pos: number; text: string }[] = [];
    editor.state.doc.descendants((node, pos) => {
      if (node.isText && node.text) chunks.push({ pos, text: node.text });
    });
    return chunks;
  };

  const findNext = () => {
    const ranges = findTextRanges(collectChunks(), findQuery);
    if (!ranges.length) {
      setFindHint("未找到");
      return;
    }
    const from = editor.state.selection.to;
    const next = ranges.find((row) => row.from >= from) || ranges[0];
    editor.chain().focus().setTextSelection(next).run();
    setFindHint(`找到 ${ranges.length} 处`);
  };

  const replaceOne = () => {
    const { from, to } = editor.state.selection;
    const selected = editor.state.doc.textBetween(from, to);
    if (findQuery && selected === findQuery) {
      editor.chain().focus().insertContent(replaceWith).run();
    }
    findNext();
  };

  const replaceAll = () => {
    const ranges = findTextRanges(collectChunks(), findQuery);
    if (!ranges.length) {
      setFindHint("未找到");
      return;
    }
    let chain = editor.chain().focus();
    for (const range of [...ranges].reverse()) {
      chain = chain.insertContentAt(range, replaceWith);
    }
    chain.run();
    setFindHint(`已替换 ${ranges.length} 处`);
  };

  return (
    <div className={styles.formatbarInner}>
      <Tool
        title={hotkeyTitle("撤销", "Ctrl+Z")}
        disabled={locked || !editor.can().undo()}
        onClick={() => editor.chain().focus().undo().run()}
      >
        <UndoOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("重做", "Ctrl+Y")}
        disabled={locked || !editor.can().redo()}
        onClick={() => editor.chain().focus().redo().run()}
      >
        <RedoOutlined />
      </Tool>
      <span className={styles.toolSplit} />
      <Dropdown
        trigger={["click"]}
        disabled={locked}
        menu={{
          selectedKeys: [headingValue],
          items: [
            {
              key: "p",
              label: "正文",
              onClick: () => editor.chain().focus().setParagraph().run(),
            },
            {
              key: "2",
              label: "标题 2",
              onClick: () =>
                editor.chain().focus().setHeading({ level: 2 }).run(),
            },
            {
              key: "3",
              label: "标题 3",
              onClick: () =>
                editor.chain().focus().setHeading({ level: 3 }).run(),
            },
            {
              key: "4",
              label: "标题 4",
              onClick: () =>
                editor.chain().focus().setHeading({ level: 4 }).run(),
            },
          ],
        }}
      >
        <span>
          <Tool
            title={hotkeyTitle("段落样式", "Ctrl+Alt+0 / 2 / 3 / 4")}
            active={headingValue !== "p"}
            disabled={locked}
          >
            {headingValue === "2"
              ? "标题 2"
              : headingValue === "3"
                ? "标题 3"
                : headingValue === "4"
                  ? "标题 4"
                  : "正文"}
          </Tool>
        </span>
      </Dropdown>
      <Tool
        title={hotkeyTitle("加粗", "Ctrl+B")}
        active={state.bold}
        disabled={locked}
        onClick={() => editor.chain().focus().toggleBold().run()}
      >
        <BoldOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("斜体", "Ctrl+I")}
        active={state.italic}
        disabled={locked}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      >
        <ItalicOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("下划线", "Ctrl+U")}
        active={state.underline}
        disabled={locked}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
      >
        <UnderlineOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("删除线", "Ctrl+Shift+S")}
        active={state.strike}
        disabled={locked}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      >
        <StrikethroughOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("行内代码", "Ctrl+`")}
        active={state.code}
        disabled={locked}
        onClick={() => editor.chain().focus().toggleCode().run()}
      >
        <CodeOutlined />
      </Tool>
      <Dropdown
        trigger={["click"]}
        disabled={locked}
        menu={{
          items: [
            {
              key: "clear",
              label: "默认颜色",
              onClick: () => editor.chain().focus().setArticleColor(null).run(),
            },
            ...ARTICLE_COLORS.map((row) => ({
              key: row.key,
              label: (
                <span className={styles.swatchRow}>
                  <span
                    className={styles.swatch}
                    style={{ background: row.value }}
                  />
                  {row.label}
                </span>
              ),
              onClick: () => editor.chain().focus().setArticleColor(row.key).run(),
            })),
          ],
        }}
      >
        <span>
          <Tool title="文字颜色" active={Boolean(state.color)} disabled={locked}>
            <FontColorsOutlined />
          </Tool>
        </span>
      </Dropdown>
      <Dropdown
        trigger={["click"]}
        disabled={locked}
        menu={{
          items: [
            {
              key: "clear",
              label: "清除高亮",
              onClick: () => editor.chain().focus().setArticleHighlight(null).run(),
            },
            ...ARTICLE_MARKS.map((row) => ({
              key: row.key,
              label: (
                <span className={styles.swatchRow}>
                  <span
                    className={styles.swatchMark}
                    style={{ background: row.value }}
                  />
                  {row.label}
                </span>
              ),
              onClick: () =>
                editor.chain().focus().setArticleHighlight(row.key).run(),
            })),
          ],
        }}
      >
        <span>
          <Tool title="高亮" active={Boolean(state.mark)} disabled={locked}>
            <HighlightOutlined />
          </Tool>
        </span>
      </Dropdown>
      <span className={styles.toolSplit} />
      <Tool
        title={hotkeyTitle("无序列表", "Ctrl+Shift+8")}
        active={state.bullet}
        disabled={locked}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        <UnorderedListOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("有序列表", "Ctrl+Shift+7")}
        active={state.ordered}
        disabled={locked}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        <OrderedListOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("引用", "Ctrl+Shift+B")}
        active={state.quote}
        disabled={locked}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      >
        ”
      </Tool>
      <Tool
        title={hotkeyTitle("代码块", "Ctrl+Alt+C")}
        active={state.codeBlock}
        disabled={locked}
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
      >
        {"</>"}
      </Tool>
      <Tool
        title="分隔线"
        disabled={locked}
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
      >
        <MinusOutlined />
      </Tool>
      <span className={styles.toolSplit} />
      <Tool
        title={hotkeyTitle("左对齐", "Ctrl+L")}
        active={state.align === "left"}
        disabled={locked}
        onClick={() => editor.chain().focus().setArticleAlign("left").run()}
      >
        <AlignLeftOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("居中", "Ctrl+E")}
        active={state.align === "center"}
        disabled={locked}
        onClick={() => editor.chain().focus().setArticleAlign("center").run()}
      >
        <AlignCenterOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("右对齐", "Ctrl+R")}
        active={state.align === "right"}
        disabled={locked}
        onClick={() => editor.chain().focus().setArticleAlign("right").run()}
      >
        <AlignRightOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("减少缩进", "Ctrl+[")}
        disabled={locked}
        onClick={() => editor.chain().focus().outdentArticle().run()}
      >
        <MenuFoldOutlined />
      </Tool>
      <Tool
        title={hotkeyTitle("增加缩进", "Ctrl+]")}
        disabled={locked}
        onClick={() => editor.chain().focus().indentArticle().run()}
      >
        <MenuUnfoldOutlined />
      </Tool>
      <span className={styles.toolSplit} />
      <Popover
        trigger="click"
        open={linkOpen}
        onOpenChange={(open) => {
          setLinkOpen(open);
          if (open) {
            setHref(editor.getAttributes("link").href || "");
          }
        }}
        content={
          <Space.Compact>
            <Input
              size="small"
              value={href}
              placeholder="https:// 或 / 站内路径"
              onChange={(event) => setHref(event.target.value)}
              onPressEnter={applyLink}
            />
            <Button size="small" type="primary" onClick={applyLink}>
              确定
            </Button>
          </Space.Compact>
        }
      >
        <span>
          <Tool title={hotkeyTitle("链接", "Ctrl+K")} active={state.link} disabled={locked}>
            <LinkOutlined />
          </Tool>
        </span>
      </Popover>
      <Tool
        title="图片"
        disabled={locked}
        onClick={() => fileRef.current?.click()}
      >
        <PictureOutlined />
      </Tool>
      <Tool
        title="附件"
        disabled={locked}
        onClick={() => attachRef.current?.click()}
      >
        <PaperClipOutlined />
      </Tool>
      <Tool
        title="插入公式"
        active={state.math}
        disabled={locked}
        onClick={() => {
          const payload = currentMathEdit(editor);
          onMathRef?.current(payload);
          editor.storage.articleMath?.onEdit?.(payload);
        }}
      >
        f(x)
      </Tool>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className={styles.fileInput}
        tabIndex={-1}
        multiple
        onChange={(event) => {
          const files = Array.from(event.target.files || []);
          event.target.value = "";
          if (!files.length) return;
          void uploadFiles(files).then((rows) => {
            for (const row of rows) {
              if (row.kind === "image") {
                editor.chain().focus().insertArticleImage({ src: row.url }).run();
              }
            }
          });
        }}
      />
      <input
        ref={attachRef}
        type="file"
        accept={ARTICLE_ATTACHMENT_ACCEPT}
        className={styles.fileInput}
        tabIndex={-1}
        multiple
        onChange={(event) => {
          const files = Array.from(event.target.files || []);
          event.target.value = "";
          if (!files.length) return;
          void uploadFiles(files).then((rows) => {
            for (const row of rows) {
              if (row.kind === "file") {
                editor
                  .chain()
                  .focus()
                  .insertArticleAttachment({ href: row.url, title: row.name })
                  .run();
              } else if (row.kind === "image") {
                editor.chain().focus().insertArticleImage({ src: row.url }).run();
              }
            }
          });
        }}
      />
      <Dropdown
        trigger={["click"]}
        disabled={locked}
        menu={{
          items: [
            {
              key: "insert",
              label: "插入表格",
              onClick: () =>
                editor
                  .chain()
                  .focus()
                  .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
                  .run(),
            },
            {
              key: "addRow",
              label: "下方加行",
              disabled: !state.table,
              onClick: () => editor.chain().focus().addRowAfter().run(),
            },
            {
              key: "addCol",
              label: "右侧加列",
              disabled: !state.table,
              onClick: () => editor.chain().focus().addColumnAfter().run(),
            },
            {
              key: "merge",
              label: "合并单元格",
              disabled: !state.table,
              onClick: () => editor.chain().focus().mergeCells().run(),
            },
            {
              key: "split",
              label: "拆分单元格",
              disabled: !state.table,
              onClick: () => editor.chain().focus().splitCell().run(),
            },
            {
              key: "delete",
              label: "删除表格",
              disabled: !state.table,
              onClick: () => editor.chain().focus().deleteTable().run(),
            },
          ],
        }}
      >
        <span>
          <Tool title="表格" active={state.table} disabled={locked}>
            <TableOutlined />
          </Tool>
        </span>
      </Dropdown>
      <Tool
        title={hotkeyTitle("查找替换", "Ctrl+F")}
        disabled={locked}
        onClick={() => setFindOpen(true)}
      >
        <SearchOutlined />
      </Tool>
      <Modal
        title="查找替换"
        open={findOpen}
        onCancel={() => setFindOpen(false)}
        footer={null}
        width="min(420px, calc(100vw - 24px))"
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input
            size="small"
            value={findQuery}
            placeholder="查找"
            onChange={(event) => setFindQuery(event.target.value)}
            onPressEnter={findNext}
          />
          <Input
            size="small"
            value={replaceWith}
            placeholder="替换为"
            onChange={(event) => setReplaceWith(event.target.value)}
          />
          <Space>
            <Button size="small" onClick={findNext}>
              查找下一个
            </Button>
            <Button size="small" onClick={replaceOne}>
              替换
            </Button>
            <Button size="small" onClick={replaceAll}>
              全部替换
            </Button>
          </Space>
          {findHint ? <span className={styles.mutedHint}>{findHint}</span> : null}
        </Space>
      </Modal>
    </div>
  );
}
