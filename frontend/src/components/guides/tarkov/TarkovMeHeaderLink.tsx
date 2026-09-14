import { Link, useLocation } from "react-router-dom";
import { TARKOV_ME_PATH, tarkovMeHref } from "@/lib/tarkovHomeNav";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovMeHeaderLink.module.css";

export function TarkovMeHeaderLink() {
  const location = useLocation();
  const { pathname, search } = location;
  const loggedIn = Boolean(useAuthStore((s) => s.user));
  const active = pathname.startsWith(TARKOV_ME_PATH);

  if (!loggedIn) {
    return (
      <Link
        to="/login"
        state={{ from: location }}
        className={styles.chip}
      >
        登录
      </Link>
    );
  }

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
