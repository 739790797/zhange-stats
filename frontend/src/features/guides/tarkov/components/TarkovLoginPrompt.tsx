import { Link, useLocation } from "react-router-dom";
import styles from "./TarkovLoginPrompt.module.css";

export function TarkovLoginPrompt({
  feature,
}: {
  feature: string;
}) {
  const location = useLocation();
  return (
    <div className={styles.box} role="status">
      <p className={styles.text}>{feature}需要登录后使用。</p>
      <Link
        className={styles.cta}
        to="/login"
        state={{ from: location }}
      >
        登录
      </Link>
    </div>
  );
}
