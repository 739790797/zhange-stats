import type { CSSProperties, ReactNode } from "react";
import { parseRor2RichText, type Ror2RichNode } from "@/features/guides/ror2/model/ror2RichText";
import styles from "./Ror2RichText.module.css";
import { Ror2TokenText } from "./Ror2TokenText";
import { ror2TextContent, type Ror2TextLike } from "@/features/guides/ror2/model/ror2Text";

type Props = {
  text: Ror2TextLike;
  className?: string;
  showInfo?: boolean;
};

export function Ror2RichText({ text, className, showInfo = true }: Props) {
  const content = ror2TextContent(text);
  if (!content) return null;
  const root = className ? `${styles.rich} ${className}` : styles.rich;
  return (
    <Ror2TokenText value={text} className={root} showInfo={showInfo}>
      {renderNodes(parseRor2RichText(content))}
    </Ror2TokenText>
  );
}

function renderNodes(nodes: Ror2RichNode[]): ReactNode[] {
  return nodes.map((node, index) => renderNode(node, index));
}

function renderNode(node: Ror2RichNode, key: number): ReactNode {
  if (node.type === "text") return <span key={key}>{node.text}</span>;
  if (node.type === "sprite") {
    return (
      <span key={key} className={styles.sprite} title={node.name} aria-label={node.name}>
        {node.name}
      </span>
    );
  }
  const children = renderNodes(node.children);
  if (node.type === "color") {
    return (
      <span key={key} style={{ color: node.color }}>
        {children}
      </span>
    );
  }
  if (node.type === "bold") {
    return (
      <strong key={key} style={{ fontWeight: 700 }}>
        {children}
      </strong>
    );
  }
  if (node.type === "italic") return <em key={key}>{children}</em>;
  if (node.type === "underline") {
    return (
      <span key={key} style={{ textDecoration: "underline" }}>
        {children}
      </span>
    );
  }
  if (node.type === "strike") {
    return (
      <span key={key} style={{ textDecoration: "line-through" }}>
        {children}
      </span>
    );
  }
  if (node.type === "size") {
    return (
      <span key={key} style={{ fontSize: node.size }}>
        {children}
      </span>
    );
  }
  if (node.type === "mono") {
    return (
      <span key={key} style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" }}>
        {children}
      </span>
    );
  }
  if (node.type === "nowrap") {
    return (
      <span key={key} style={{ whiteSpace: "nowrap" }}>
        {children}
      </span>
    );
  }
  const mark: CSSProperties = { backgroundColor: node.color };
  return (
    <span key={key} style={mark}>
      {children}
    </span>
  );
}
