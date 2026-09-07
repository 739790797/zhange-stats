import { Extension } from "@tiptap/core";
import { Placeholder } from "@tiptap/extension-placeholder";
import type { Editor } from "@tiptap/react";
import {
  EditorContent,
  ReactRenderer,
  useEditor,
  useEditorState,
} from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import Suggestion, { type SuggestionProps } from "@tiptap/suggestion";
import {
  BoldOutlined,
  ItalicOutlined,
  LinkOutlined,
  UnderlineOutlined,
} from "@ant-design/icons";
import { Button, Input, Popover, Space } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  articleToEditorHtml,
  composerHtmlToBody,
} from "@/lib/articleComposer";
import { bindArticleHotkeys } from "@/lib/articleHotkeys";
import { isSafeArticleHref } from "@/lib/articleHtml";
import {
  filesFromClipboard,
  filesFromList,
  imageFilesFromList,
  type ArticleBodyFormat,
  type ArticleUploadedAsset,
} from "@/lib/articleImages";
import {
  ArticleDragHandle,
  articleSchemaExtensions,
  articleSlashItems,
  filterArticleSlashItems,
  type ArticleMathEdit,
  type ArticleSlashItem,
} from "@/lib/articleTiptap";
import { ArticleMathModal } from "./ArticleMathModal";
import { ArticleSlashMenu, type ArticleSlashMenuHandle } from "./ArticleSlashMenu";
import { ArticleToolbar } from "./ArticleToolbar";
import "./articleRichtext.css";
import styles from "./TavernEdit.module.css";

function createSlashExtension(onPickImage: () => void) {
  const items = [
    ...articleSlashItems(),
    {
      id: "image",
      title: "图片",
      keywords: "图片 image",
      run: () => {
        onPickImage();
        return true;
      },
    } satisfies ArticleSlashItem,
  ];
  return Extension.create({
    name: "articleSlash",
    addProseMirrorPlugins() {
      return [
        Suggestion<ArticleSlashItem, ArticleSlashItem>({
          editor: this.editor,
          char: "/",
          allowSpaces: false,
          items: ({ query }) => filterArticleSlashItems(items, query),
          command: ({ editor, range, props }) => {
            editor.chain().focus().deleteRange(range).run();
            props.run(editor);
          },
          render: () => {
            let renderer: ReactRenderer<ArticleSlashMenuHandle> | null = null;
            let unmount: (() => void) | null = null;
            return {
              onStart: (props: SuggestionProps<ArticleSlashItem, ArticleSlashItem>) => {
                renderer = new ReactRenderer(ArticleSlashMenu, {
                  editor: props.editor,
                  props,
                });
                unmount = props.mount(renderer.element);
              },
              onUpdate: (props) => {
                renderer?.updateProps(props);
              },
              onKeyDown: (props) => renderer?.ref?.onKeyDown(props) ?? false,
              onExit: () => {
                unmount?.();
                renderer?.destroy();
                unmount = null;
                renderer = null;
              },
            };
          },
        }),
      ];
    },
  });
}

function BubbleTools({
  editor,
  disabled,
}: {
  editor: Editor;
  disabled?: boolean;
}) {
  const [linkOpen, setLinkOpen] = useState(false);
  const [href, setHref] = useState("");
  const state = useEditorState({
    editor,
    selector: ({ editor: current }) => ({
      bold: current.isActive("bold"),
      italic: current.isActive("italic"),
      underline: current.isActive("underline"),
      link: current.isActive("link"),
    }),
  });
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
  return (
    <div className={styles.bubble}>
      <Button
        type="text"
        size="small"
        disabled={disabled}
        className={state.bold ? styles.toolActive : undefined}
        onClick={() => editor.chain().focus().toggleBold().run()}
      >
        <BoldOutlined />
      </Button>
      <Button
        type="text"
        size="small"
        disabled={disabled}
        className={state.italic ? styles.toolActive : undefined}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      >
        <ItalicOutlined />
      </Button>
      <Button
        type="text"
        size="small"
        disabled={disabled}
        className={state.underline ? styles.toolActive : undefined}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
      >
        <UnderlineOutlined />
      </Button>
      <Popover
        trigger="click"
        open={linkOpen}
        onOpenChange={(open) => {
          setLinkOpen(open);
          if (open) setHref(editor.getAttributes("link").href || "");
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
        <Button
          type="text"
          size="small"
          disabled={disabled}
          className={state.link ? styles.toolActive : undefined}
        >
          <LinkOutlined />
        </Button>
      </Popover>
    </div>
  );
}

export function ArticleComposer({
  value,
  onChange,
  format,
  disabled,
  uploadFiles,
  toolbarHost,
  onSave,
}: {
  value?: string;
  onChange?: (next: string) => void;
  format: ArticleBodyFormat;
  disabled?: boolean;
  uploadFiles: (files: File[]) => Promise<ArticleUploadedAsset[]>;
  toolbarHost?: HTMLElement | null;
  onSave?: () => void;
}) {
  const lastBody = useRef<string | undefined>(undefined);
  const pickImage = useRef<() => void>(() => undefined);
  const uploading = useRef(false);
  const applying = useRef(false);
  const editorRef = useRef<Editor | null>(null);
  const uploadRef = useRef(uploadFiles);
  const onChangeRef = useRef(onChange);
  const onSaveRef = useRef(onSave);
  const onFindRef = useRef<() => void>(() => undefined);
  const onLinkRef = useRef<() => void>(() => undefined);
  const onMathRef = useRef<(payload: ArticleMathEdit) => void>(() => undefined);
  uploadRef.current = uploadFiles;
  onChangeRef.current = onChange;
  onSaveRef.current = onSave;
  const embedRef = useRef<(files: File[]) => Promise<void>>(async () => undefined);
  const [mathEdit, setMathEdit] = useState<ArticleMathEdit | null>(null);

  const extensions = useMemo(
    () => [
      ...articleSchemaExtensions(),
      Placeholder.configure({
        placeholder: "开始写作。输入 / 插入块，可粘贴或拖入图片和附件。",
      }),
      createSlashExtension(() => pickImage.current()),
      ArticleDragHandle,
    ],
    [],
  );

  const editor = useEditor({
    extensions,
    immediatelyRender: false,
    editable: !disabled,
    content: articleToEditorHtml(value || "", format),
    editorProps: {
      attributes: {
        class: styles.composerSurface,
      },
      transformPastedHTML: (html) =>
        (html || "").replace(/<input\b[^>]*>/gi, ""),
      handlePaste: (_view, event) => {
        const files = filesFromClipboard(event.clipboardData);
        if (!files.length) return false;
        event.preventDefault();
        void embedRef.current(files);
        return true;
      },
      handleDrop: (_view, event) => {
        const files = filesFromList(event.dataTransfer?.files);
        if (!files.length) return false;
        event.preventDefault();
        void embedRef.current(files);
        return true;
      },
      handleDOMEvents: {
        dragover: (_view, event) => {
          if (event.dataTransfer?.types?.includes("Files")) {
            event.preventDefault();
          }
          return false;
        },
      },
    },
    onCreate: ({ editor: current }) => {
      lastBody.current = composerHtmlToBody(current.getHTML());
    },
    onUpdate: ({ editor: current }) => {
      if (applying.current) return;
      const next = composerHtmlToBody(current.getHTML());
      lastBody.current = next;
      onChangeRef.current?.(next);
    },
  });

  editorRef.current = editor;
  onMathRef.current = (payload) => setMathEdit(payload);
  if (editor) {
    editor.storage.articleMath = {
      ...(editor.storage.articleMath || {}),
      onEdit: (payload: ArticleMathEdit) => setMathEdit(payload),
    };
  }

  embedRef.current = async (files: File[]) => {
    const current = editorRef.current;
    if (!files.length || disabled || uploading.current || !current) return;
    uploading.current = true;
    try {
      const rows = await uploadRef.current(files);
      for (const row of rows) {
        if (row.kind === "image") {
          current.chain().focus().insertArticleImage({ src: row.url }).run();
        } else {
          current
            .chain()
            .focus()
            .insertArticleAttachment({ href: row.url, title: row.name })
            .run();
        }
      }
    } finally {
      uploading.current = false;
    }
  };

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!disabled);
  }, [disabled, editor]);

  useEffect(() => {
    if (!editor) return;
    const next = articleToEditorHtml(value || "", format);
    const normalized = composerHtmlToBody(next);
    if (normalized === lastBody.current) return;
    applying.current = true;
    lastBody.current = normalized;
    editor.commands.setContent(next || "", { emitUpdate: false });
    lastBody.current = composerHtmlToBody(editor.getHTML());
    applying.current = false;
  }, [editor, value, format]);

  useEffect(() => {
    return bindArticleHotkeys({
      getEditor: () => editorRef.current,
      onSave: () => onSaveRef.current?.(),
      onFind: () => onFindRef.current(),
      onLink: () => onLinkRef.current(),
      disabled: () => Boolean(disabled),
    });
  }, [disabled]);

  useEffect(() => {
    pickImage.current = () => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = "image/*";
      input.multiple = true;
      input.onchange = () => {
        const files = imageFilesFromList(input.files);
        if (files.length) void embedRef.current(files);
      };
      input.click();
    };
  });

  if (!editor) return null;

  const toolbar = (
    <ArticleToolbar
      editor={editor}
      disabled={disabled}
      onFindRef={onFindRef}
      onLinkRef={onLinkRef}
      onMathRef={onMathRef}
      uploadFiles={uploadFiles}
    />
  );

  return (
    <>
      {toolbarHost ? createPortal(toolbar, toolbarHost) : (
        <div className={styles.formatbar}>{toolbar}</div>
      )}
      {editor && (
        <BubbleMenu editor={editor} options={{ placement: "top" }}>
          <BubbleTools editor={editor} disabled={disabled} />
        </BubbleMenu>
      )}
      <div className={styles.composer}>
        <EditorContent editor={editor} />
      </div>
      <ArticleMathModal
        open={mathEdit != null}
        latex={mathEdit?.latex || ""}
        display={Boolean(mathEdit?.display)}
        onCancel={() => setMathEdit(null)}
        onOk={(next) => {
          editor.chain().focus().setArticleMath(next).run();
          setMathEdit(null);
        }}
      />
    </>
  );
}
