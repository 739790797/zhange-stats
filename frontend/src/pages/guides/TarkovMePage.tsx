import { useSearchParams } from "react-router-dom";
import { TarkovMePanel } from "@/components/guides/tarkov/TarkovMePanel";
import { TarkovLoginPrompt } from "@/components/guides/tarkov/TarkovLoginPrompt";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { resolveTarkovMeTab } from "@/lib/tarkovHomeNav";
import { useAuthStore } from "@/stores/authStore";

export default function TarkovMePage() {
  const user = useAuthStore((s) => s.user);
  const [searchParams] = useSearchParams();
  const fill = resolveTarkovMeTab(searchParams.get("tab")) === "collection";
  if (!user) {
    return (
      <TarkovItemsPageShell crumbs={[]} sectionLabel="个人中心">
        <TarkovLoginPrompt feature="个人中心（任务进度、钥匙、收集、藏身处规划与日志）" />
      </TarkovItemsPageShell>
    );
  }
  return (
    <TarkovItemsPageShell
      crumbs={[]}
      sectionLabel="个人中心"
      fill={fill}
      fillPagePad={fill}
    >
      <TarkovMePanel />
    </TarkovItemsPageShell>
  );
}
