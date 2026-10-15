import type { CSSProperties, ReactNode } from "react";
import { parseRor2RichText, type Ror2RichNode } from "@/lib/ror2RichText";
import styles from "./Ror2RichText.module.css";

type Props = {
  text: string;
  className?: string;
};

export function Ror2RichText({ text, className }: Props) {
  if (!text) return null;
  const root = className ? `${styles.rich} ${className}` : styles.rich;
  return <span className={root}>{renderNodes(parseRor2RichText(text))}</span>;
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
