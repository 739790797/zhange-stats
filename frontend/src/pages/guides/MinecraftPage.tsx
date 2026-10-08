/** Minecraft 页面已停用。总览、启动、管理、插件、模组留在下方注释里。 */
export default function MinecraftPage() {
  return null;
}

/*
import { lazy } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import { PageHeader } from "@/components/PageHeader";
import { GuideTabsPage } from "@/components/guides/GuideTabsPage";
import { MinecraftLivePanel } from "@/components/guides/minecraft/MinecraftLivePanel";
import { MinecraftStartupPanel } from "@/components/guides/minecraft/MinecraftStartupPanel";
import { fetchMinecraftStartup } from "@/api/minecraftApi";
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

const MinecraftPluginsPanel = lazy(() =>
  import("@/components/guides/minecraft/MinecraftPluginsPanel").then((m) => ({
    default: m.MinecraftPluginsPanel,
  })),
);

export default function MinecraftPage() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = isAdminUser(user);
  const startup = useQuery({
    queryKey: ["minecraft-startup"],
    queryFn: fetchMinecraftStartup,
    enabled: isAdmin,
    refetchInterval: 15_000,
    retry: 1,
  });

  const overview = <MinecraftLivePanel />;

  if (!isAdmin) {
    return (
      <div>
        <PageHeader title="Minecraft" subtitle="服况。" />
        {overview}
      </div>
    );
  }

  const kind = startup.data?.kind;
  const showPlugins = Boolean(startup.data?.plugins_visible);
  const pluginsReady = Boolean(startup.data?.plugins_ready);
  const showMods = kind !== "plugin";

  return (
    <GuideTabsPage
      title="Minecraft"
      defaultTab="overview"
      destroyInactiveTabPane
      tabItems={[
        { key: "overview", label: "总览", children: overview },
        { key: "startup", label: "启动", children: <MinecraftStartupPanel /> },
        { key: "manage", label: "管理", children: <MinecraftManagePanel /> },
        ...(showPlugins
          ? [
              {
                key: "plugins",
                label: (
                  <span title={pluginsReady ? undefined : "当前核心还没有成功启动过"}>
                    插件
                  </span>
                ),
                disabled: !pluginsReady,
                children: <MinecraftPluginsPanel />,
              },
            ]
          : []),
        ...(showMods
          ? [{ key: "mods", label: "模组", children: <MinecraftModToolsPanel /> }]
          : []),
      ]}
    />
  );
}
*/
