import { useEffect, useMemo, useRef, useState } from "react";
import type { Ror2Survivor } from "@/api/ror2Api";
import { apiError } from "@/lib/apiError";
import { ror2SurvivorSections } from "@/lib/ror2Home";
import { useRor2Catalog } from "@/lib/useRor2Catalog";
import styles from "./Ror2SurvivorMenu.module.css";
import theme from "./ror2Theme.module.css";

export function Ror2SurvivorMenu() {
  const catalog = useRor2Catalog();
  const rootRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState(false);
  const [pinned, setPinned] = useState(false);
  const open = hover || pinned;
  const survivors = catalog.data?.survivors;
  const sections = useMemo(() => ror2SurvivorSections(survivors ?? []), [survivors]);
  const error = catalog.isError ? apiError(catalog.error, "图鉴暂时拉不下来，请稍后再试") : "";

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setPinned(false);
      setHover(false);
      const active = document.activeElement;
      if (active instanceof HTMLElement && rootRef.current?.contains(active)) active.blur();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div
      ref={rootRef}
      className={open ? `${styles.menu} ${styles.menuOpen}` : styles.menu}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={(event) => {
        const next = event.relatedTarget;
        if (!(next instanceof Node) || !event.currentTarget.contains(next)) setPinned(false);
      }}
    >
      <button
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls="ror2-survivor-pop"
        onClick={() => setPinned((value) => !value)}
      >
        幸存者
      </button>
      <div id="ror2-survivor-pop" className={styles.pop} role="region" aria-label="幸存者">
        {catalog.isPending ? <p className={styles.note}>正在读取图鉴</p> : null}
        {!catalog.isPending && error ? (
          <div className={styles.feedback}>
            <p className={styles.note}>{error}</p>
            <button type="button" className={theme.wikiBtn} onClick={() => void catalog.refetch()}>
              重试
            </button>
          </div>
        ) : null}
        {!catalog.isPending && !error && !sections.length ? (
          <p className={styles.note}>暂时没有幸存者</p>
        ) : null}
        {!catalog.isPending && !error
          ? sections.map((section) => (
              <section key={section.id} className={`${theme.frame} ${styles.group}`}>
                <h2 className={styles.groupTitle}>{section.label}</h2>
                <ul className={styles.roster}>
                  {section.survivors.map((survivor, index) => (
                    <li key={`${section.id}-${index}-${survivor.name}`}>
                      <SurvivorFace survivor={survivor} />
                    </li>
                  ))}
                </ul>
              </section>
            ))
          : null}
      </div>
    </div>
  );
}

function SurvivorFace({ survivor }: { survivor: Ror2Survivor }) {
  const [hidden, setHidden] = useState(false);
  const src = survivor.image_url;
  return (
    <figure className={styles.face}>
      {src && !hidden ? (
        <img
          className={styles.portrait}
          src={src}
          alt=""
          width={36}
          height={36}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setHidden(true)}
        />
      ) : (
        <span className={styles.fallback} aria-hidden />
      )}
      <figcaption className={styles.name}>{survivor.name}</figcaption>
    </figure>
  );
}
