/** @vitest-environment happy-dom */
import {
  bindArticleHotkeys,
  hasArticleHotkeyMod,
  isArticleHotkeyNativeTarget,
  matchArticleHotkey,
} from "./articleHotkeys";
import { describe, expect, it, vi } from "vitest";

function ev(
  key: string,
  extras: Partial<{
    code: string;
    ctrlKey: boolean;
    metaKey: boolean;
    altKey: boolean;
    shiftKey: boolean;
  }> = {},
) {
  return {
    key,
    code: extras.code,
    ctrlKey: extras.ctrlKey ?? true,
    metaKey: extras.metaKey ?? false,
    altKey: extras.altKey ?? false,
    shiftKey: extras.shiftKey ?? false,
  };
}

describe("articleHotkeys", () => {
  it("requires a modifier", () => {
    expect(hasArticleHotkeyMod(ev("s", { ctrlKey: false }))).toBe(false);
    expect(matchArticleHotkey(ev("s", { ctrlKey: false }))).toBeNull();
    expect(matchArticleHotkey(ev("s", { ctrlKey: false, metaKey: true }))).toBe(
      "save",
    );
  });

  it("maps save find and formatting", () => {
    expect(matchArticleHotkey(ev("s"))).toBe("save");
    expect(matchArticleHotkey(ev("b"))).toBe("bold");
    expect(matchArticleHotkey(ev("i"))).toBe("italic");
    expect(matchArticleHotkey(ev("u"))).toBe("underline");
    expect(matchArticleHotkey(ev("z"))).toBe("undo");
    expect(matchArticleHotkey(ev("y"))).toBe("redo");
    expect(matchArticleHotkey(ev("z", { shiftKey: true }))).toBe("redo");
    expect(matchArticleHotkey(ev("k"))).toBe("link");
    expect(matchArticleHotkey(ev("f"))).toBe("find");
    expect(matchArticleHotkey(ev("s", { shiftKey: true }))).toBe("strike");
    expect(matchArticleHotkey(ev("8", { shiftKey: true, code: "Digit8" }))).toBe(
      "bullet",
    );
    expect(matchArticleHotkey(ev("7", { shiftKey: true, code: "Digit7" }))).toBe(
      "ordered",
    );
  });

  it("maps headings and alignment instead of browser chrome", () => {
    expect(matchArticleHotkey(ev("2", { altKey: true, code: "Digit2" }))).toBe(
      "heading2",
    );
    expect(matchArticleHotkey(ev("l"))).toBe("alignLeft");
    expect(matchArticleHotkey(ev("e"))).toBe("alignCenter");
    expect(matchArticleHotkey(ev("r"))).toBe("alignRight");
    expect(matchArticleHotkey(ev("p"))).toBe("consume");
    expect(matchArticleHotkey(ev("d"))).toBe("consume");
    expect(matchArticleHotkey(ev("o"))).toBe("consume");
  });

  it("leaves copy paste and plain keys alone", () => {
    expect(matchArticleHotkey(ev("c"))).toBeNull();
    expect(matchArticleHotkey(ev("v"))).toBeNull();
    expect(matchArticleHotkey(ev("x"))).toBeNull();
    expect(matchArticleHotkey(ev("a"))).toBeNull();
    expect(matchArticleHotkey(ev("Enter"))).toBeNull();
  });

  it("detects native fields outside the editor", () => {
    const input = document.createElement("input");
    const area = document.createElement("div");
    area.className = "ProseMirror";
    const inner = document.createElement("p");
    area.append(inner);
    expect(isArticleHotkeyNativeTarget(input)).toBe(true);
    expect(isArticleHotkeyNativeTarget(inner)).toBe(false);
    expect(isArticleHotkeyNativeTarget(null)).toBe(false);
  });

  it("binds window capture and blocks the browser save shortcut", () => {
    const onSave = vi.fn();
    const onFind = vi.fn();
    const unbind = bindArticleHotkeys({
      getEditor: () => null,
      onSave,
      onFind,
      onLink: () => undefined,
    });
    const event = new KeyboardEvent("keydown", {
      key: "s",
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    expect(onSave).toHaveBeenCalledTimes(1);
    const findEvent = new KeyboardEvent("keydown", {
      key: "f",
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    window.dispatchEvent(findEvent);
    expect(findEvent.defaultPrevented).toBe(true);
    expect(onFind).toHaveBeenCalledTimes(1);
    unbind();
  });
});
