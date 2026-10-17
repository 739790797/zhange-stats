import { useState } from "react";
import styles from "./Ror2ExpansionIcon.module.css";

export function Ror2ExpansionIcon({ src, label }: { src: string; label?: string }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  return (
    <img
      className={styles.icon}
      src={src}
      alt={label ?? ""}
      title={label}
      width={18}
      height={18}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setHidden(true)}
    />
  );
}
