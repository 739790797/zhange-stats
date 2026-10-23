import { createContext, useContext } from "react";

/** 子页在 `AdminHubLayout` 内时隐藏 H3，只留 subtitle / extra。 */
export const AdminHubEmbeddedContext = createContext(false);

export function useAdminHubEmbedded(): boolean {
  return useContext(AdminHubEmbeddedContext);
}
