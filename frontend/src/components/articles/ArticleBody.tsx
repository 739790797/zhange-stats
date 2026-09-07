import DOMPurify from "dompurify";
import ReactMarkdown from "react-markdown";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import {
  ARTICLE_HTML_ATTRS,
  ARTICLE_HTML_TAGS,
  filterArticleClasses,
  isSafeArticleHref,
} from "@/lib/articleHtml";
import { isSafeArticleImageSrc } from "@/lib/articleImages";
import { renderArticleMathInHtml } from "@/lib/articleMath";
import "./articleRichtext.css";
import styles from "./ArticleBody.module.css";

const markdownSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    img: ["src", "alt", "title", "width", "height"],
    a: ["href", "title", "target", "rel"],
  },
};

const htmlSanitize = {
  ALLOWED_TAGS: ARTICLE_HTML_TAGS,
  ALLOWED_ATTR: ARTICLE_HTML_ATTRS,
  ALLOW_DATA_ATTR: false,
  ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto):|\/(?!\/)|#)/i,
};

let purifyHooked = false;

function ensureArticlePurify() {
  if (purifyHooked) return;
  purifyHooked = true;
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (!(node instanceof Element)) return;
    if (node.hasAttribute("class")) {
      const next = filterArticleClasses(node.getAttribute("class") || "");
      if (next) node.setAttribute("class", next);
      else node.removeAttribute("class");
    }
    if (
      node.tagName === "IMG" &&
      !isSafeArticleImageSrc(node.getAttribute("src") || "")
    ) {
      node.removeAttribute("src");
    }
    if (
      node.tagName === "A" &&
      !isSafeArticleHref(node.getAttribute("href") || "")
    ) {
      node.removeAttribute("href");
    }
  });
}

function ArticleImage({
  src,
  alt,
  title,
}: {
  src?: string;
  alt?: string;
  title?: string;
}) {
  if (!src || !isSafeArticleImageSrc(src)) return null;
  return <img src={src} alt={alt || ""} title={title} loading="lazy" />;
}

export function ArticleBody({
  body,
  format,
  className,
}: {
  body: string;
  format: string;
  className?: string;
}) {
  if (!body.trim()) {
    return <div className={styles.empty}>暂无正文</div>;
  }
  const rootClass = className ? `${styles.body} ${className}` : styles.body;
  if (format === "html") {
    ensureArticlePurify();
    return (
      <div
        className={rootClass}
        dangerouslySetInnerHTML={{
          __html: renderArticleMathInHtml(
            DOMPurify.sanitize(body, htmlSanitize),
          ),
        }}
      />
    );
  }
  return (
    <div className={rootClass}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, markdownSchema]]}
        components={{
          img: ({ src, alt, title }) => (
            <ArticleImage src={src} alt={alt} title={title} />
          ),
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
