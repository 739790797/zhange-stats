import { Link, useLocation } from "react-router-dom";
import { TARKOV_ME_PATH, tarkovMeHref } from "@/lib/tarkovHomeNav";
import styles from "./TarkovMeHeaderLink.module.css";

export function TarkovMeHeaderLink() {
  const { pathname, search } = useLocation();
  const active = pathname.startsWith(TARKOV_ME_PATH);

  return (
    <Link
      to={active ? `${pathname}${search}` : tarkovMeHref()}
      className={`${styles.chip}${active ? ` ${styles.chipOn}` : ""}`}
      aria-current={active ? "page" : undefined}
    >
      个人中心
    </Link>
  );
}
