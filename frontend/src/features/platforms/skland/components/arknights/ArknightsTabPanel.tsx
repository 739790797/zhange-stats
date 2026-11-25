import { CalendarOutlined, DeploymentUnitOutlined, TeamOutlined } from "@ant-design/icons";
import { ConfigProvider } from "antd";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useDocumentTitle } from "@/shared/hooks/documentTitle";
import type { SklandStatus } from "@/features/platforms/skland/api/types";
import { SklandGameEventsPanel } from "@/features/platforms/skland/components/skland/SklandGameEventsPanel";
import { ArknightsBoxCompare } from "./ArknightsBoxCompare";
import { ArknightsStrongholdPanel } from "./ArknightsStrongholdPanel";
import styles from "./Arknights.module.css";

const panes = [
  { key: "calendar", label: "活动日历", Icon: CalendarOutlined },
  { key: "compare", label: "干员信息", Icon: TeamOutlined },
  { key: "protocol", label: "卫戍协议", Icon: DeploymentUnitOutlined },
] as const;

const arknightsTheme = {
  token: {
    colorPrimary: "#303741",
    colorLink: "#a23f1b",
    colorText: "#17191c",
    colorTextSecondary: "#575e65",
    colorBorder: "#c8cbcf",
    borderRadius: 2,
  },
};

export function ArknightsTabPanel({
  bound,
  bindFallback,
  strongholdEnabled,
  roles,
}: {
  bound: boolean;
  bindFallback: ReactNode;
  strongholdEnabled: boolean;
  roles?: SklandStatus["roles"];
}) {
  const [params] = useSearchParams();
  const available = panes.filter(({ key }) => key !== "protocol" || strongholdEnabled);
  const current = available.find(({ key }) => key === params.get("pane")) ?? panes[0];
  useDocumentTitle(`${current.label} · 明日方舟`);

  return (
    <ConfigProvider theme={arknightsTheme}>
      <section className={styles.shell} aria-label="明日方舟" data-pane={current.key}>
        <header className={styles.hero}>
          <div className={styles.heroTitle}>
            <p className={styles.heroLabel} lang="en">
              ARKNIGHTS
            </p>
            <h1>明日方舟</h1>
          </div>
          <div className={styles.heroPattern} aria-hidden="true" />
        </header>
        <nav className={styles.navigation} aria-label="明日方舟功能">
          {available.map(({ key, label, Icon }) => (
            <Link
              key={key}
              className={styles.navLink}
              to={{ search: key === "calendar" ? "?tab=arknights" : `?tab=arknights&pane=${key}` }}
              aria-current={current.key === key ? "page" : undefined}
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className={styles.content}>
          {current.key !== "protocol" ? (
            <header className={styles.sectionHeader}>
              <h2>{current.label}</h2>
            </header>
          ) : null}
          {current.key === "protocol" ? (
            <ArknightsStrongholdPanel bound={bound} roles={roles} bindFallback={bindFallback} />
          ) : !bound ? (
            bindFallback
          ) : current.key === "compare" ? (
            <ArknightsBoxCompare />
          ) : (
            <SklandGameEventsPanel game="arknights" variant="arknights" />
          )}
        </div>
      </section>
    </ConfigProvider>
  );
}
