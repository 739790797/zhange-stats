import { useQuery } from "@tanstack/react-query";
import { Badge } from "antd";
import { useAuthStore } from "@/stores/authStore";
import { PageHeader } from "@/components/PageHeader";
import { GuideTabsPage } from "@/components/guides/GuideTabsPage";
import { MinecraftAdminPanel } from "@/components/guides/minecraft/MinecraftAdminPanel";
import { MinecraftFileManager } from "@/components/guides/minecraft/MinecraftFileManager";
import { MinecraftLivePanel } from "@/components/guides/minecraft/MinecraftLivePanel";
import { MinecraftManagePanel } from "@/components/guides/minecraft/MinecraftManagePanel";
import { fetchMinecraftStatus } from "@/api/minecraftApi";
import { isAdminUser } from "@/lib/isAdminUser";

export default function MinecraftPage() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = isAdminUser(user);

  const statusQuery = useQuery({
    queryKey: ["minecraft-status"],
    queryFn: fetchMinecraftStatus,
    refetchInterval: 10_000,
    retry: 1,
  });

  const overview = <MinecraftLivePanel />;

  if (!isAdmin) {
    return (
      <div>
        <PageHeader title="Minecraft" />
        {overview}
      </div>
    );
  }

  const dirty = Boolean(statusQuery.data?.playbook_dirty);

  return (
    <GuideTabsPage
      title="Minecraft"
      defaultTab="overview"
      tabItems={[
        { key: "overview", label: "总览", children: overview },
        { key: "manage", label: "管理", children: <MinecraftManagePanel /> },
        { key: "files", label: "文件", children: <MinecraftFileManager /> },
        {
          key: "playbook",
          label: dirty ? <Badge dot>开服</Badge> : "开服",
          children: <MinecraftAdminPanel />,
        },
      ]}
    />
  );
}
