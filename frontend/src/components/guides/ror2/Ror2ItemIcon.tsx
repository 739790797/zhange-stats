import { useState } from "react";
import theme from "./ror2Theme.module.css";

type Props = {
  src?: string | null;
  accent: string;
};

export function Ror2ItemIcon({ src, accent }: Props) {
  const [hidden, setHidden] = useState(false);
  if (!src || hidden) {
    return <span className={theme.iconFallback} style={{ borderColor: accent }} aria-hidden />;
  }
  return (
    <img
      className={theme.icon}
      src={src}
      alt=""
      width={56}
      height={56}
      style={{ borderColor: accent }}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setHidden(true)}
    />
  );
}
