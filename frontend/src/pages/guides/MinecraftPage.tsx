import { useAuthStore } from "@/stores/authStore";
import { PageHeader } from "@/components/PageHeader";
import { GuideTabsPage } from "@/components/guides/GuideTabsPage";
import { MinecraftLivePanel } from "@/components/guides/minecraft/MinecraftLivePanel";
import { MinecraftManagePanel } from "@/components/guides/minecraft/MinecraftManagePanel";
import { MinecraftModToolsPanel } from "@/components/guides/minecraft/MinecraftModToolsPanel";
import { isAdminUser } from "@/lib/isAdminUser";

export default function MinecraftPage() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = isAdminUser(user);

  const overview = <MinecraftLivePanel />;

  if (!isAdmin) {
    return (
      <div>
        <PageHeader title="Minecraft" />
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
