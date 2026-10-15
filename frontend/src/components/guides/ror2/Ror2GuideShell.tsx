import { useLayoutEffect, useRef, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { IcpBeianLink } from "@/components/IcpBeianLink";
import { focusWithoutVisibleRing } from "@/lib/focusRouteTarget";
import { useDocumentTitle } from "@/lib/documentTitle";
import {
  ROR2_HOME_PATH,
  ROR2_LICENSE,
  ROR2_WIKI_ITEMS,
  ror2PageTitle,
} from "@/lib/ror2Home";
import styles from "./Ror2GuideShell.module.css";
import "./ror2Fonts.css";

type Props = {
  children: ReactNode;
};

export function Ror2GuideShell({ children }: Props) {
  const { pathname } = useLocation();
  const bodyRef = useRef<HTMLElement>(null);
  useDocumentTitle(ror2PageTitle(pathname));

  useLayoutEffect(() => {
    bodyRef.current?.scrollTo(0, 0);
    focusWithoutVisibleRing(bodyRef.current);
  }, [pathname]);

  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#ror2-main">
        跳到正文
      </a>
      <header className={styles.topbar}>
        <Link to={ROR2_HOME_PATH} className={styles.brand} aria-label="雨中冒险2">
          <span className={styles.brandEn}>RISK OF RAIN 2</span>
          <span className={styles.brandZh}>雨中冒险2</span>
        </Link>
      </header>
      <main ref={bodyRef} id="ror2-main" tabIndex={-1} className={styles.body}>
        <div className={styles.page}>{children}</div>
        <footer className={styles.footer}>
          <p>
            图鉴文字来自{" "}
            <a href={ROR2_WIKI_ITEMS} target="_blank" rel="noreferrer">
              Risk of Rain 2 Wiki
            </a>
            ，许可为{" "}
            <a href={ROR2_LICENSE} target="_blank" rel="noreferrer">
              CC BY-SA 4.0
            </a>
            。
          </p>
          <IcpBeianLink light />
        </footer>
      </main>
    </div>
  );
}
