import {
  articleAttachmentHtml,
  articleAttachmentLabel,
  articleFileExt,
  articleImageMarkup,
  classifyArticleUpload,
  filesFromClipboard,
  imageFilesFromClipboard,
  insertArticleImage,
  isSafeArticleImageSrc,
  rejectArticleAttachmentFile,
  rejectArticleImageFile,
  rejectArticleUploadFile,
} from "./articleImages";
import { describe, expect, it } from "vitest";

describe("articleImages", () => {
  it("allows http(s) and same-origin article paths", () => {
    expect(isSafeArticleImageSrc("/uploads/articles/halo/a.png")).toBe(true);
    expect(isSafeArticleImageSrc("https://cdn.example/a.png")).toBe(true);
    expect(isSafeArticleImageSrc("http://cdn.example/a.png")).toBe(true);
    expect(isSafeArticleImageSrc("//evil.example/a.png")).toBe(false);
    expect(isSafeArticleImageSrc("javascript:alert(1)")).toBe(false);
    expect(isSafeArticleImageSrc("/uploads/../etc/passwd")).toBe(false);
    expect(isSafeArticleImageSrc("data:image/png;base64,xx")).toBe(false);
  });

  it("builds format-specific embed markup", () => {
    expect(articleImageMarkup("/uploads/articles/a.png", "markdown")).toBe(
      "![](/uploads/articles/a.png)\n",
    );
    expect(articleImageMarkup("/uploads/articles/a.png", "html", "图")).toBe(
      '<figure><img src="/uploads/articles/a.png" alt="图"></figure>\n',
    );
    expect(articleImageMarkup('"><x>', "html")).toContain("&quot;");
  });

  it("appends an embed after existing body", () => {
    expect(insertArticleImage("", "/u.png", "markdown")).toBe("![](/u.png)\n");
    expect(insertArticleImage("hello", "/u.png", "markdown")).toBe(
      "hello\n\n![](/u.png)\n",
    );
    expect(insertArticleImage("hello\n", "/u.png", "html")).toBe(
      "hello\n\n<figure><img src=\"/u.png\" alt=\"\"></figure>\n",
    );
  });

  it("picks image files from clipboard-like data", () => {
    const file = new File(["x"], "a.png", { type: "image/png" });
    const data = {
      files: [file],
      items: [],
    } as unknown as DataTransfer;
    expect(imageFilesFromClipboard(data)).toEqual([file]);
    expect(imageFilesFromClipboard(null)).toEqual([]);
  });

  it("classifies pasted images and attachments", () => {
    const image = new File(["x"], "a.png", { type: "image/png" });
    const pdf = new File(["%PDF"], "说明.pdf", { type: "application/pdf" });
    const exe = new File(["MZ"], "a.exe", { type: "application/octet-stream" });
    expect(classifyArticleUpload(image)).toBe("image");
    expect(classifyArticleUpload(pdf)).toBe("file");
    expect(classifyArticleUpload(exe)).toBeNull();
    expect(articleFileExt("pack.tar.gz")).toBe(".tgz");
    expect(articleAttachmentLabel("C:\\\\tmp\\\\a<>.lml")).toBe("a.lml");
    expect(articleAttachmentHtml("/uploads/articles/a.pdf", "说明.pdf")).toBe(
      '<p><a href="/uploads/articles/a.pdf" rel="noopener noreferrer">说明.pdf</a></p>',
    );
    expect(rejectArticleAttachmentFile(pdf)).toBeNull();
    expect(rejectArticleUploadFile(exe)).toBe("不支持的文件类型");
    const data = {
      files: [pdf],
      items: [],
    } as unknown as DataTransfer;
    expect(filesFromClipboard(data)).toEqual([pdf]);
  });

  it("rejects non-image or oversized files", () => {
    expect(
      rejectArticleImageFile(new File(["x"], "a.txt", { type: "text/plain" })),
    ).toBe("请选择图片文件");
    const huge = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "a.png", {
      type: "image/png",
    });
    expect(rejectArticleImageFile(huge)).toBe("图片不能超过 5MB");
    expect(
      rejectArticleImageFile(new File(["x"], "a.png", { type: "image/png" })),
    ).toBeNull();
  });
});
