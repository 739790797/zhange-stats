import type { Editor } from "@tiptap/core";

export type ArticleHotkeyAction =
  | "save"
  | "bold"
  | "italic"
  | "underline"
  | "strike"
  | "code"
  | "undo"
  | "redo"
  | "link"
  | "find"
  | "bullet"
  | "ordered"
  | "quote"
  | "codeBlock"
  | "heading2"
  | "heading3"
  | "heading4"
  | "paragraph"
  | "alignLeft"
  | "alignCenter"
  | "alignRight"
  | "indent"
  | "outdent"
  | "consume";

export type ArticleHotkeyEvent = {
  key: string;
  code?: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
};

export function hasArticleHotkeyMod(event: ArticleHotkeyEvent): boolean {
  return event.ctrlKey || event.metaKey;
}

function keyName(event: ArticleHotkeyEvent): string {
  return (event.key || "").length === 1
    ? event.key.toLowerCase()
    : (event.key || "").toLowerCase();
}

export function matchArticleHotkey(
  event: ArticleHotkeyEvent,
): ArticleHotkeyAction | null {
  if (!hasArticleHotkeyMod(event)) return null;
  const key = keyName(event);
  const code = event.code || "";
  const shift = event.shiftKey;
  const alt = event.altKey;

  if (alt && !shift) {
    if (key === "2" || code === "Digit2") return "heading2";
    if (key === "3" || code === "Digit3") return "heading3";
    if (key === "4" || code === "Digit4") return "heading4";
    if (key === "0" || code === "Digit0") return "paragraph";
    if (key === "c") return "codeBlock";
    return null;
  }

  if (shift) {
    if (key === "z") return "redo";
    if (key === "s" || key === "x") return "strike";
    if (key === "7" || code === "Digit7") return "ordered";
    if (key === "8" || code === "Digit8") return "bullet";
    if (key === "b") return "quote";
    return null;
  }

  if (key === "s") return "save";
  if (key === "b") return "bold";
  if (key === "i") return "italic";
  if (key === "u") return "underline";
  if (key === "z") return "undo";
  if (key === "y") return "redo";
  if (key === "k") return "link";
  if (key === "f" || key === "h" || key === "g") return "find";
  if (key === "l") return "alignLeft";
  if (key === "e") return "alignCenter";
  if (key === "r") return "alignRight";
  if (key === "]" || code === "BracketRight") return "indent";
  if (key === "[" || code === "BracketLeft") return "outdent";
  if (key === "`") return "code";
  if (key === "p" || key === "d" || key === "j" || key === "o") return "consume";
  return null;
}

export function isArticleHotkeyNativeTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.closest(".ProseMirror")) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

export function runArticleHotkey(
  editor: Editor,
  action: ArticleHotkeyAction,
): boolean {
  const chain = editor.chain().focus();
  if (action === "bold") return chain.toggleBold().run();
  if (action === "italic") return chain.toggleItalic().run();
  if (action === "underline") return chain.toggleUnderline().run();
  if (action === "strike") return chain.toggleStrike().run();
  if (action === "code") return chain.toggleCode().run();
  if (action === "undo") return chain.undo().run();
  if (action === "redo") return chain.redo().run();
  if (action === "bullet") return chain.toggleBulletList().run();
  if (action === "ordered") return chain.toggleOrderedList().run();
  if (action === "quote") return chain.toggleBlockquote().run();
  if (action === "codeBlock") return chain.toggleCodeBlock().run();
  if (action === "heading2") return chain.toggleHeading({ level: 2 }).run();
  if (action === "heading3") return chain.toggleHeading({ level: 3 }).run();
  if (action === "heading4") return chain.toggleHeading({ level: 4 }).run();
  if (action === "paragraph") return chain.setParagraph().run();
  if (action === "alignLeft") return chain.setArticleAlign("left").run();
  if (action === "alignCenter") return chain.setArticleAlign("center").run();
  if (action === "alignRight") return chain.setArticleAlign("right").run();
  if (action === "indent") return chain.indentArticle().run();
  if (action === "outdent") return chain.outdentArticle().run();
  return false;
}

export function bindArticleHotkeys(options: {
  getEditor: () => Editor | null;
  onSave: () => void;
  onFind: () => void;
  onLink: () => void;
  disabled?: () => boolean;
}): () => void {
  const consume = (event: KeyboardEvent) => {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  };
  const onKeyDown = (event: KeyboardEvent) => {
    const action = matchArticleHotkey(event);
    if (!action) return;
    if (options.disabled?.()) {
      consume(event);
      if (action === "save") options.onSave();
      return;
    }
    if (action === "save") {
      consume(event);
      options.onSave();
      return;
    }
    if (action === "find") {
      consume(event);
      options.onFind();
      return;
    }
    if (action === "link") {
      consume(event);
      options.onLink();
      return;
    }
    if (action === "consume") {
      consume(event);
      return;
    }
    if (isArticleHotkeyNativeTarget(event.target)) {
      consume(event);
      return;
    }
    const editor = options.getEditor();
    if (!editor || editor.isDestroyed) {
      consume(event);
      return;
    }
    consume(event);
    runArticleHotkey(editor, action);
  };
  window.addEventListener("keydown", onKeyDown, true);
  return () => window.removeEventListener("keydown", onKeyDown, true);
}
