import { useSearchParams } from "react-router-dom";
import { TarkovMePanel } from "@/features/guides/tarkov/components/TarkovMePanel";
import { TarkovLoginPrompt } from "@/features/guides/tarkov/components/TarkovLoginPrompt";
import { TarkovItemsPageShell } from "@/features/guides/tarkov/components/TarkovItemsPageShell";
import { isAssistantBodyPane } from "@/shared/lib/assistantShell";
import { resolveTarkovMeTab } from "@/features/guides/tarkov/model/tarkovHomeNav";
import { useAuthStore } from "@/features/auth/model/authStore";

export default function TarkovMePage() {
  const user = useAuthStore((s) => s.user);
  const [searchParams] = useSearchParams();
  const fill = resolveTarkovMeTab(searchParams.get("tab")) === "collection";
  const bodyPane = isAssistantBodyPane();
  if (!user) {
    return (
      <TarkovItemsPageShell
        crumbs={[]}
        sectionLabel="个人中心"
        hideHead={bodyPane}
      >
        <TarkovLoginPrompt feature="个人中心（任务进度、钥匙、收集、藏身处规划与日志）" />
      </TarkovItemsPageShell>
    );
  }
  return (
    <TarkovItemsPageShell
      crumbs={[]}
      sectionLabel="个人中心"
      hideHead={bodyPane}
      fill={fill}
      fillPagePad={fill}
    >
      <TarkovMePanel />
    </TarkovItemsPageShell>
  );
}
