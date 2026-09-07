import { useQuery } from "@tanstack/react-query";
import { fetchSitePublic } from "@/api/client";

export const SITE_PUBLIC_QUERY_KEY = ["site-public"] as const;

export function useSitePublic() {
  return useQuery({
    queryKey: SITE_PUBLIC_QUERY_KEY,
    queryFn: fetchSitePublic,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
