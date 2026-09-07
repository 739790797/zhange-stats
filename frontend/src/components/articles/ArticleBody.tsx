import DOMPurify from "dompurify";
import ReactMarkdown from "react-markdown";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import styles from "./ArticleBody.module.css";

const markdownSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    img: ["src", "alt", "title"],
    a: ["href", "title", "target", "rel"],
  },
};

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
    return (
      <div
        className={rootClass}
        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(body) }}
      />
    );
  }
  return (
    <div className={rootClass}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, markdownSchema]]}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
