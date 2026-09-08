import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { TarkovWorkbenchBuild } from "@/components/guides/tarkov/workbench/TarkovWorkbenchBuild";
import { TarkovWorkbenchEmpty } from "@/components/guides/tarkov/workbench/TarkovWorkbenchEmpty";
import { TarkovWorkbenchGunPickerModal } from "@/components/guides/tarkov/workbench/TarkovWorkbenchGunPickerModal";
import styles from "@/components/guides/tarkov/workbench/TarkovWorkbenchBuild.module.css";
import {
  TARKOV_WORKBENCH_PATH,
  tarkovWorkbenchHref,
} from "@/lib/tarkovHomeNav";

export default function TarkovWorkbenchPage() {
  const { gunId } = useParams<{ gunId?: string }>();
  const navigate = useNavigate();
  const [pickOpen, setPickOpen] = useState(false);

  const pickGun = (id: string) => {
    setPickOpen(false);
    navigate(tarkovWorkbenchHref(id));
  };

  return (
    <TarkovItemsPageShell
      title={gunId ? undefined : "枪械工作台"}
      crumbs={gunId ? [{ label: "改枪" }] : []}
      sectionLabel="工作台"
      sectionHref={TARKOV_WORKBENCH_PATH}
      fill
    >
      <div className={styles.stage}>
        {gunId ? (
          <TarkovWorkbenchBuild
            gunId={gunId}
            onChangeGun={() => setPickOpen(true)}
          />
        ) : (
          <TarkovWorkbenchEmpty onAdd={() => setPickOpen(true)} />
        )}
        <TarkovWorkbenchGunPickerModal
          open={pickOpen}
          onCancel={() => setPickOpen(false)}
          onPick={pickGun}
        />
      </div>
    </TarkovItemsPageShell>
  );
}
