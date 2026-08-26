import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  fetchRoleMembershipTree,
  replaceRoleMemberships,
  type CheckinPlatformKey,
} from "@/api/roleMembershipApi";
import { RoleMembershipTreeModal } from "@/components/RoleMembershipTreeModal";

const STATUS_QUERY_KEY: Record<CheckinPlatformKey, string[]> = {
  skland: ["skland-status"],
  taygedo: ["taygedo-status"],
  exilium: ["exilium-status"],
  kujiequ: ["kujiequ-status"],
  mihoyo: ["mihoyo-status"],
};

/**
 * 绑定成功后弹出「选择加入本站角色」。
 *
 * 注意：弹窗状态须挂在「绑定成功后仍会保持挂载」的父级（页面 / PlatformBindsSection），
 * 不要只放在会随 needsBind 卸载的 BindPanel 内，否则绑定成功瞬间弹窗会被一起卸掉。
 */
export function useRoleMembershipPicker(platform: CheckinPlatformKey) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const openPicker = useCallback(() => setOpen(true), []);
  const closePicker = useCallback(() => setOpen(false), []);

  const loadTree = useCallback(
    () => fetchRoleMembershipTree(platform),
    [platform],
  );

  const saveMemberships = useCallback(
    async (
      roles: Array<{ game_code: string; role_uid: string; included: boolean }>,
    ) => {
      await replaceRoleMemberships(platform, roles);
      await queryClient.invalidateQueries({
        queryKey: STATUS_QUERY_KEY[platform],
      });
      await queryClient.invalidateQueries({ queryKey: ["my-daily-tasks"] });
      await queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    },
    [platform, queryClient],
  );

  const modal = (
    <RoleMembershipTreeModal
      open={open}
      platform={platform}
      loadTree={loadTree}
      saveMemberships={saveMemberships}
      onClose={closePicker}
    />
  );

  return { openPicker, closePicker, modal, open };
}
