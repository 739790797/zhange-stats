import type {
  MinecraftModFeature,
  MinecraftModTool,
  MinecraftModTools,
} from "@/api/minecraftApi";
import { MinecraftBluemapWorkspace } from "./MinecraftBluemapWorkspace";
import { MinecraftChunkyWorkspace } from "./MinecraftChunkyWorkspace";
import styles from "./MinecraftModToolCard.module.css";

export function MinecraftModFeatures({
  tool,
  data,
  canCommand,
}: {
  tool: MinecraftModTool;
  data: MinecraftModTools;
  canCommand: boolean;
}) {
  const features = tool.features || [];
  if (!features.length) return null;
  return (
    <div className={styles.section}>
      <div className={styles.sectionHead}>
        <div className={styles.sectionTitle}>模组功能</div>
      </div>
      {features.map((feature) => (
        <ModFeatureWidget
          key={feature.id}
          feature={feature}
          data={data}
          canCommand={canCommand}
        />
      ))}
    </div>
  );
}

function ModFeatureWidget({
  feature,
  data,
  canCommand,
}: {
  feature: MinecraftModFeature;
  data: MinecraftModTools;
  canCommand: boolean;
}) {
  if (feature.id === "chunky.pregenerate") {
    return (
      <MinecraftChunkyWorkspace
        data={data}
        canCommand={canCommand}
        feature={feature}
      />
    );
  }
  if (feature.id === "bluemap.render") {
    return (
      <MinecraftBluemapWorkspace
        data={data}
        canCommand={canCommand}
        feature={feature}
      />
    );
  }
  return null;
}
