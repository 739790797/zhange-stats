import { useQuery } from "@tanstack/react-query";
import { fetchRor2Catalog } from "@/api/ror2Api";

export function useRor2Catalog() {
  return useQuery({
    queryKey: ["guides-ror2-catalog"],
    queryFn: fetchRor2Catalog,
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}
