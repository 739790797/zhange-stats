import { PageHeader, type PageHeaderProps } from "@/shared/ui/PageHeader";
import { useAdminHubEmbedded } from "@/features/admin/components/adminHubContext";

/** 管理中心内复用通用标题栏，并由 admin feature 决定嵌入态展示。 */
export function AdminPageHeader(props: PageHeaderProps) {
  const compact = useAdminHubEmbedded();
  return <PageHeader {...props} compact={compact} />;
}
