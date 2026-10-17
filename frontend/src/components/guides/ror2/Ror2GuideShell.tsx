import { useLayoutEffect, useMemo, useRef, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { IcpBeianLink } from "@/components/IcpBeianLink";
import { focusWithoutVisibleRing } from "@/lib/focusRouteTarget";
import { useDocumentTitle } from "@/lib/documentTitle";
import {
  ROR2_HOME_PATH,
  ROR2_LICENSE,
  ROR2_WIKI_ITEMS,
  ror2Crumbs,
  ror2PageTitle,
  ror2ReplaceTerms,
  ror2SurvivorNamePairs,
} from "@/lib/ror2Home";
import { useRor2Catalog } from "@/lib/useRor2Catalog";
import { Ror2SurvivorMenu } from "./Ror2SurvivorMenu";
import { Ror2TermScope } from "./Ror2TermScope";
import styles from "./Ror2GuideShell.module.css";
import "./ror2Fonts.css";

type Props = {
  children: ReactNode;
};

export function Ror2GuideShell({ children }: Props) {
  const { pathname } = useLocation();
  const bodyRef = useRef<HTMLElement>(null);
  const catalog = useRor2Catalog();
  const terms = useMemo(
    () => ror2SurvivorNamePairs(catalog.data?.survivors ?? []),
    [catalog.data?.survivors],
  );
  const crumbs = ror2Crumbs(pathname).map((crumb) => ({ ...crumb, label: ror2ReplaceTerms(crumb.label, terms) }));
  useDocumentTitle(ror2ReplaceTerms(ror2PageTitle(pathname), terms));

  useLayoutEffect(() => {
    bodyRef.current?.scrollTo(0, 0);
    focusWithoutVisibleRing(bodyRef.current);
  }, [pathname]);

  return (
    <Ror2TermScope terms={terms}>
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#ror2-main">
        跳到正文
      </a>
      <header className={styles.topbar}>
        <div className={styles.lead}>
          <Link to={ROR2_HOME_PATH} className={styles.brand} aria-label="雨中冒险2">
            <span className={styles.brandEn}>RISK OF RAIN 2</span>
            <span className={styles.brandZh}>雨中冒险2</span>
          </Link>
          {crumbs.length > 0 ? (
            <nav className={styles.crumbNav} aria-label="面包屑">
              <ol className={styles.crumbs}>
                {crumbs.map((crumb, index) => (
                  <li key={crumb.label} className={styles.crumb}>
                    <span className={styles.sep} aria-hidden="true">
                      /
                    </span>
                    {crumb.href && index < crumbs.length - 1 ? (
                      <Link to={crumb.href}>{crumb.label}</Link>
                    ) : (
                      <span aria-current="page">{crumb.label}</span>
                    )}
                  </li>
                ))}
              </ol>
            </nav>
          ) : null}
        </div>
        <nav className={styles.topnav} aria-label="图鉴">
          <Ror2SurvivorMenu />
        </nav>
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
    </Ror2TermScope>
  );
}
