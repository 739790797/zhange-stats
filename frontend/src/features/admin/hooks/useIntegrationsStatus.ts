import { useQuery } from "@tanstack/react-query";
import { fetchIntegrationsStatus } from "@/features/admin/api/integrationsApi";

export function useIntegrationsStatus(enabled = true) {
  return useQuery({
    queryKey: ["integrations-status"],
    queryFn: fetchIntegrationsStatus,
    enabled,
    staleTime: 60_000,
  });
}
