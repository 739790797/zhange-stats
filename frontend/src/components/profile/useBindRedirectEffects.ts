import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { message } from "antd";
import { useEffect } from "react";
import type { SetURLSearchParams } from "react-router-dom";
import type { MemberProfile } from "@/api/types";
import {
  OAUTH_RETURN_PARAMS,
  oauthFailureMessage,
  type OauthReturnFlow,
} from "@/lib/oauthReturnReason";

/** 避免 React StrictMode 双次挂载导致绑定回跳提示重复弹出 */
let handledSteamBindQuery: string | null = null;
let handledQqBindQuery: string | null = null;

type ProfileQueryKey = readonly ["member-profile", number] | readonly ["profile-me"];

type UseBindRedirectEffectsParams = {
  searchParams: URLSearchParams;
  setSearchParams: SetURLSearchParams;
  profileQueryKey: ProfileQueryKey;
  isAdminEdit: boolean;
};

/** 绑定后的昵称只从资料接口取，回跳地址里的参数一律不展示。 */
async function refetchProfile(queryClient: QueryClient, key: ProfileQueryKey) {
  await queryClient.invalidateQueries({ queryKey: key, exact: true });
  return queryClient.getQueryData<MemberProfile>(key);
}

function withoutReturnParams(searchParams: URLSearchParams, flow: OauthReturnFlow) {
  const next = new URLSearchParams(searchParams);
  next.delete(flow);
  for (const key of OAUTH_RETURN_PARAMS) next.delete(key);
  return next;
}

function showBindFailure(flow: OauthReturnFlow, key: string, reason: string | null) {
  const content = oauthFailureMessage(flow, reason);
  if (reason === "cancelled") message.info({ key, content });
  else message.error({ key, content });
}

export function useBindRedirectEffects({
  searchParams,
  setSearchParams,
  profileQueryKey,
  isAdminEdit,
}: UseBindRedirectEffectsParams) {
  const queryClient = useQueryClient();

  useEffect(() => {
    const status = searchParams.get("steam_bind");
    if (!status) return;
    const bindKey = searchParams.toString();
    if (handledSteamBindQuery === bindKey) return;
    handledSteamBindQuery = bindKey;

    const reason = searchParams.get("reason");
    setSearchParams(withoutReturnParams(searchParams, "steam_bind"), { replace: true });

    if (status === "ok") {
      message.success({ key: "steam-bind", content: "Steam 绑定成功" });
      void refetchProfile(queryClient, profileQueryKey).then((profile) => {
        const name = profile?.steam_persona_name?.trim();
        if (name) message.success({ key: "steam-bind", content: `已绑定 Steam：${name}` });
      });
      queryClient.invalidateQueries({ queryKey: ["auth-me"] });
      if (isAdminEdit) {
        queryClient.invalidateQueries({ queryKey: ["users"] });
        queryClient.invalidateQueries({ queryKey: ["members"] });
      }
    } else if (status === "error") {
      showBindFailure("steam_bind", "steam-bind", reason);
    }
  }, [searchParams, setSearchParams, queryClient, profileQueryKey, isAdminEdit]);

  useEffect(() => {
    const status = searchParams.get("qq_bind");
    if (!status) return;
    const bindKey = `qq:${searchParams.toString()}`;
    if (handledQqBindQuery === bindKey) return;
    handledQqBindQuery = bindKey;

    const reason = searchParams.get("reason");
    setSearchParams(withoutReturnParams(searchParams, "qq_bind"), { replace: true });

    if (status === "ok") {
      message.success({ key: "qq-bind", content: "QQ 绑定成功" });
      void refetchProfile(queryClient, profileQueryKey).then((profile) => {
        const name = profile?.qq_nickname?.trim();
        if (name) message.success({ key: "qq-bind", content: `已绑定 QQ：${name}` });
      });
      queryClient.invalidateQueries({ queryKey: ["auth-me"] });
    } else if (status === "error") {
      showBindFailure("qq_bind", "qq-bind", reason);
    }
  }, [searchParams, setSearchParams, queryClient, profileQueryKey]);
}
