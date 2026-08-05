import { useQueryClient } from "@tanstack/react-query";
import { message } from "antd";
import { useEffect } from "react";
import type { SetURLSearchParams } from "react-router-dom";
import type { User } from "@/api/types";

/** 避免 React StrictMode 双次挂载导致绑定回跳提示重复弹出 */
let handledSteamBindQuery: string | null = null;
let handledQqBindQuery: string | null = null;

type UseBindRedirectEffectsParams = {
  searchParams: URLSearchParams;
  setSearchParams: SetURLSearchParams;
  profileQueryKey: readonly ["member-profile", number] | readonly ["profile-me"];
  isAdminEdit: boolean;
  authUser: User | null;
  setUser: (user: User) => void;
};

export function useBindRedirectEffects({
  searchParams,
  setSearchParams,
  profileQueryKey,
  isAdminEdit,
  authUser,
  setUser,
}: UseBindRedirectEffectsParams) {
  const queryClient = useQueryClient();

  useEffect(() => {
    const status = searchParams.get("steam_bind");
    if (!status) return;
    const bindKey = searchParams.toString();
    if (handledSteamBindQuery === bindKey) return;
    handledSteamBindQuery = bindKey;

    const detail = searchParams.get("detail");
    const name = searchParams.get("name");
    const next = new URLSearchParams(searchParams);
    next.delete("steam_bind");
    next.delete("detail");
    next.delete("name");
    setSearchParams(next, { replace: true });

    if (status === "ok") {
      message.success({
        key: "steam-bind",
        content: name ? `已绑定 Steam：${name}` : "Steam 绑定成功",
      });
      queryClient.invalidateQueries({ queryKey: profileQueryKey });
      queryClient.invalidateQueries({ queryKey: ["auth-me"] });
      if (isAdminEdit) {
        queryClient.invalidateQueries({ queryKey: ["users"] });
        queryClient.invalidateQueries({ queryKey: ["members"] });
      }
    } else if (status === "error") {
      message.error({
        key: "steam-bind",
        content: detail || "Steam 绑定失败",
      });
    }
  }, [
    searchParams,
    setSearchParams,
    queryClient,
    profileQueryKey,
    isAdminEdit,
    authUser,
    setUser,
  ]);

  useEffect(() => {
    const status = searchParams.get("qq_bind");
    if (!status) return;
    const bindKey = `qq:${searchParams.toString()}`;
    if (handledQqBindQuery === bindKey) return;
    handledQqBindQuery = bindKey;

    const detail = searchParams.get("detail");
    const name = searchParams.get("name");
    const next = new URLSearchParams(searchParams);
    next.delete("qq_bind");
    next.delete("detail");
    next.delete("name");
    setSearchParams(next, { replace: true });

    if (status === "ok") {
      message.success({
        key: "qq-bind",
        content: name ? `已绑定 QQ：${name}` : "QQ 绑定成功",
      });
      queryClient.invalidateQueries({ queryKey: profileQueryKey });
      queryClient.invalidateQueries({ queryKey: ["auth-me"] });
    } else if (status === "error") {
      message.error({
        key: "qq-bind",
        content: detail || "QQ 绑定失败",
      });
    }
  }, [searchParams, setSearchParams, queryClient, profileQueryKey]);
}
