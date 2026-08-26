import { lazy } from "react";
import { useAuthStore } from "@/stores/authStore";
import { PageHeader } from "@/components/PageHeader";
import { GuideTabsPage } from "@/components/guides/GuideTabsPage";
import { MinecraftLivePanel } from "@/components/guides/minecraft/MinecraftLivePanel";
import { isAdminUser } from "@/lib/isAdminUser";

const MinecraftManagePanel = lazy(() =>
  import("@/components/guides/minecraft/MinecraftManagePanel").then((m) => ({
    default: m.MinecraftManagePanel,
  })),
);

const MinecraftModToolsPanel = lazy(() =>
  import("@/components/guides/minecraft/MinecraftModToolsPanel").then((m) => ({
    default: m.MinecraftModToolsPanel,
  })),
);

export default function MinecraftPage() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = isAdminUser(user);

  const overview = <MinecraftLivePanel />;

  if (!isAdmin) {
    return (
      <div>
        <PageHeader
          title="Minecraft"
          subtitle="服况与在线玩家。启停、文件与模组由管理员操作。"
        />
        {overview}
      </div>
    );
  }

  return (
    <GuideTabsPage
      title="Minecraft"
      defaultTab="overview"
      destroyInactiveTabPane
      tabItems={[
        { key: "overview", label: "总览", children: overview },
        { key: "manage", label: "管理", children: <MinecraftManagePanel /> },
        { key: "mods", label: "模组", children: <MinecraftModToolsPanel /> },
      ]}
    />
  );
}
