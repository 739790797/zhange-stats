import { ConfigProvider } from "antd";
import { Navigate, useParams } from "react-router-dom";
import { TarkovItemsBreadcrumb } from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import { TarkovTraderPanel } from "@/components/guides/tarkov/TarkovTraderPanel";
import { TARKOV_ANTD_DARK } from "@/lib/tarkovAntdDark";
import {
  TARKOV_HOME_PATH,
  TARKOV_TRADERS,
  TARKOV_TRADERS_PATH,
} from "@/lib/tarkovHomeNav";
import styles from "@/components/guides/tarkov/TarkovItemsPageShell.module.css";

export default function TarkovTraderPage() {
  const { traderSlug = "" } = useParams<{ traderSlug: string }>();
  const known = TARKOV_TRADERS.find((item) => item.id === traderSlug);
  const crumbLabel = known?.english || traderSlug;

  if (!traderSlug) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  return (
    <div className={styles.inner}>
      <TarkovItemsBreadcrumb
        items={[
          { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
          { label: "商人", to: TARKOV_TRADERS_PATH },
          { label: crumbLabel },
        ]}
      />
      <ConfigProvider theme={TARKOV_ANTD_DARK}>
        <TarkovTraderPanel slug={traderSlug} />
      </ConfigProvider>
    </div>
  );
}
