import { ConfigProvider } from "antd";
import { Navigate, useParams } from "react-router-dom";
import { TarkovGuideShell } from "@/components/guides/tarkov/TarkovGuideShell";
import { TarkovItemsBreadcrumb } from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import { TarkovBossPanel } from "@/components/guides/tarkov/TarkovBossPanel";
import { TARKOV_ANTD_DARK } from "@/lib/tarkovAntdDark";
import {
  TARKOV_BOSSES,
  TARKOV_BOSSES_PATH,
  TARKOV_HOME_PATH,
} from "@/lib/tarkovHomeNav";
import styles from "@/components/guides/tarkov/TarkovItemsPageShell.module.css";

export default function TarkovBossPage() {
  const { bossSlug = "" } = useParams<{ bossSlug: string }>();
  const known = TARKOV_BOSSES.find((item) => item.id === bossSlug);
  const crumbLabel =
    known?.label ||
    bossSlug
      .split("-")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");

  if (!bossSlug) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  return (
    <TarkovGuideShell>
      <div className={styles.inner}>
        <TarkovItemsBreadcrumb
          items={[
            { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
            { label: "BOSS", to: TARKOV_BOSSES_PATH },
            { label: crumbLabel },
          ]}
        />
        <ConfigProvider theme={TARKOV_ANTD_DARK}>
          <TarkovBossPanel slug={bossSlug} />
        </ConfigProvider>
      </div>
    </TarkovGuideShell>
  );
}
