import { Navigate, useParams } from "react-router-dom";
import { TarkovItemsBreadcrumb } from "@/features/guides/tarkov/components/TarkovItemsBreadcrumb";
import { TarkovTraderPanel } from "@/features/guides/tarkov/components/TarkovTraderPanel";
import {
  TARKOV_HOME_PATH,
  TARKOV_TRADERS,
  TARKOV_TRADERS_PATH,
} from "@/features/guides/tarkov/model/tarkovHomeNav";
import styles from "@/features/guides/tarkov/components/TarkovItemsPageShell.module.css";

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
      <TarkovTraderPanel slug={traderSlug} />
    </div>
  );
}
