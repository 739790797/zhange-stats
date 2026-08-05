import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Upload, message } from "antd";
import type { UploadProps } from "antd";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  fetchMemberProfile,
  fetchMyProfile,
  fetchPlatformFeaturesEffective,
  startQqOAuthBind,
  startSteamOpenIdBind,
  unbindQq,
  unbindSkland,
  unbindTaygedo,
  unbindExilium,
  unbindKujiequ,
  updateMemberProfile,
  updateMyProfile,
  uploadMemberAvatar,
  uploadMyAvatar,
} from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";
import { PersonalInfoSection } from "@/components/profile/PersonalInfoSection";
import { PlatformBindsSection } from "@/components/profile/PlatformBindsSection";
import { useBindRedirectEffects } from "@/components/profile/useBindRedirectEffects";
import { isFeatureOn } from "@/lib/platformFeatures";
import { useAuthStore } from "@/stores/authStore";

type ProfilePayload = {
  display_name?: string;
  steam_id?: string | null;
};

export default function ProfileSettingsPage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const targetMemberId = id ? Number(id) : NaN;
  const isAdminEdit = Number.isFinite(targetMemberId);

  const queryClient = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const authUser = useAuthStore((s) => s.user);
  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: 30_000,
  });
  const showSteam = isFeatureOn(featuresQuery.data, "steam");
  const showSkland = isFeatureOn(featuresQuery.data, "skland");
  const showTaygedo = isFeatureOn(featuresQuery.data, "taygedo");
  const showExilium = isFeatureOn(featuresQuery.data, "exilium");
  const showKujiequ = isFeatureOn(featuresQuery.data, "kujiequ");
  const [nameDraft, setNameDraft] = useState("");

  const profileQueryKey = isAdminEdit
    ? (["member-profile", targetMemberId] as const)
    : (["profile-me"] as const);

  const { data, isLoading, error, isError } = useQuery({
    queryKey: profileQueryKey,
    queryFn: () =>
      isAdminEdit ? fetchMemberProfile(targetMemberId) : fetchMyProfile(),
    enabled: !isAdminEdit || Number.isFinite(targetMemberId),
    retry: false,
  });

  useBindRedirectEffects({
    searchParams,
    setSearchParams,
    profileQueryKey,
    isAdminEdit,
    authUser,
    setUser,
  });

  const saveProfilePatch = (payload: ProfilePayload) =>
    isAdminEdit
      ? updateMemberProfile(targetMemberId, payload)
      : updateMyProfile(payload);

  const invalidateProfile = () => {
    queryClient.invalidateQueries({ queryKey: profileQueryKey });
    queryClient.invalidateQueries({ queryKey: ["auth-me"] });
    if (isAdminEdit) {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["members"] });
    }
  };

  const applyProfileLocally = (profile: {
    display_name?: string | null;
    nickname?: string;
    avatar_url?: string | null;
    steam_id?: string | null;
  }) => {
    if (isAdminEdit || !authUser) return;
    setUser({
      ...authUser,
      display_name:
        profile.display_name || profile.nickname || authUser.display_name,
      avatar_url: profile.avatar_url ?? null,
      steam_id: profile.steam_id ?? null,
    });
  };

  useEffect(() => {
    if (!data) return;
    setNameDraft(data.display_name || data.nickname || "");
  }, [data]);

  const saveName = useMutation({
    mutationFn: async (name: string) => saveProfilePatch({ display_name: name }),
    onSuccess: (profile) => {
      message.success("显示名称已更新");
      invalidateProfile();
      applyProfileLocally(profile);
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const startSteamBind = useMutation({
    mutationFn: async () =>
      startSteamOpenIdBind(isAdminEdit ? targetMemberId : undefined),
    onSuccess: ({ url }) => {
      window.location.href = url;
    },
    onError: (e: unknown) => message.error(apiError(e, "无法跳转 Steam 登录")),
  });

  const startQqBind = useMutation({
    mutationFn: async () =>
      startQqOAuthBind(isAdminEdit ? targetMemberId : undefined),
    onSuccess: ({ url }) => {
      window.location.href = url;
    },
    onError: (e: unknown) => message.error(apiError(e, "无法跳转 QQ 绑定")),
  });

  const unbindSteam = useMutation({
    mutationFn: async () => saveProfilePatch({ steam_id: null }),
    onSuccess: (profile) => {
      message.success("已解除 Steam 绑定");
      invalidateProfile();
      applyProfileLocally(profile);
    },
    onError: (e: unknown) => message.error(apiError(e, "解绑失败")),
  });

  const unbindQqMut = useMutation({
    mutationFn: async () =>
      unbindQq(isAdminEdit ? targetMemberId : undefined),
    onSuccess: () => {
      message.success("已解除 QQ 绑定");
      invalidateProfile();
    },
    onError: (e: unknown) => message.error(apiError(e, "解绑失败")),
  });

  const unbindSklandMut = useMutation({
    mutationFn: unbindSkland,
    onSuccess: () => {
      message.success("已解除森空岛绑定");
      invalidateProfile();
      queryClient.invalidateQueries({ queryKey: ["skland-status"] });
      queryClient.invalidateQueries({ queryKey: ["skland-logs"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "解绑失败")),
  });

  const unbindTaygedoMut = useMutation({
    mutationFn: unbindTaygedo,
    onSuccess: () => {
      message.success("已解除塔吉多绑定");
      invalidateProfile();
      queryClient.invalidateQueries({ queryKey: ["taygedo-status"] });
      queryClient.invalidateQueries({ queryKey: ["taygedo-logs"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "解绑失败")),
  });

  const unbindExiliumMut = useMutation({
    mutationFn: unbindExilium,
    onSuccess: () => {
      message.success("已解除追放社区绑定");
      invalidateProfile();
      queryClient.invalidateQueries({ queryKey: ["exilium-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "解绑失败")),
  });

  const unbindKujiequMut = useMutation({
    mutationFn: unbindKujiequ,
    onSuccess: () => {
      message.success("已解除库街区绑定");
      invalidateProfile();
      queryClient.invalidateQueries({ queryKey: ["kujiequ-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "解绑失败")),
  });

  const uploadAvatar = useMutation({
    mutationFn: async (file: File) =>
      isAdminEdit
        ? uploadMemberAvatar(targetMemberId, file)
        : uploadMyAvatar(file),
    onSuccess: (profile) => {
      message.success("头像已更新");
      invalidateProfile();
      applyProfileLocally(profile);
    },
    onError: (e: unknown) => message.error(apiError(e, "头像上传失败")),
  });

  const beforeUpload: UploadProps["beforeUpload"] = (file) => {
    const okType = ["image/jpeg", "image/png", "image/webp", "image/gif"].includes(
      file.type,
    );
    if (!okType) {
      message.error("仅支持 JPG / PNG / WebP / GIF");
      return Upload.LIST_IGNORE;
    }
    if (file.size > 5 * 1024 * 1024) {
      message.error("头像不能超过 5MB");
      return Upload.LIST_IGNORE;
    }
    uploadAvatar.mutate(file);
    return false;
  };

  const errMsg = isError ? apiError(error, "加载失败") : null;

  const steamBound = Boolean(data?.steam_id);
  const qqBound = Boolean(data?.qq_bound);
  const sklandBound = Boolean(data?.skland_bound);
  const taygedoBound = Boolean(data?.taygedo_bound);
  const exiliumBound = Boolean(data?.exilium_bound);
  const kujiequBound = Boolean(data?.kujiequ_bound);
  const displayName =
    data?.display_name ||
    data?.nickname ||
    "-";
  const subjectLabel =
    data?.display_name ||
    data?.nickname ||
    data?.email ||
    `成员 #${targetMemberId}`;

  return (
    <div>
      <PageHeader
        title={isAdminEdit ? "编辑成员个人中心" : "个人中心"}
        subtitle={
          isAdminEdit
            ? `正在编辑：${subjectLabel}（管理员代操作：需用目标 Steam 账号完成登录）`
            : "绑定 Steam / 森空岛；头像可自行上传"
        }
        extra={
          isAdminEdit ? <Link to="/settings/users">返回用户管理</Link> : undefined
        }
      />

      {isAdminEdit ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="管理员模式：跳转 Steam 登录后，将把「当前登录的 Steam 账号」绑定到该成员"
        />
      ) : null}

      {errMsg ? (
        <Alert type="warning" showIcon message={errMsg} style={{ marginBottom: 16 }} />
      ) : null}

      <PersonalInfoSection
        isLoading={isLoading}
        errMsg={errMsg}
        data={data}
        displayName={displayName}
        nameDraft={nameDraft}
        onNameDraftChange={setNameDraft}
        saveNamePending={saveName.isPending}
        onSaveName={() => saveName.mutate(nameDraft.trim())}
        beforeUpload={beforeUpload}
        uploadAvatarPending={uploadAvatar.isPending}
      />

      <PlatformBindsSection
        isLoading={isLoading}
        errMsg={errMsg}
        isAdminEdit={isAdminEdit}
        data={data}
        showSteam={showSteam}
        showSkland={showSkland}
        showTaygedo={showTaygedo}
        showExilium={showExilium}
        showKujiequ={showKujiequ}
        steamBound={steamBound}
        qqBound={qqBound}
        sklandBound={sklandBound}
        taygedoBound={taygedoBound}
        exiliumBound={exiliumBound}
        kujiequBound={kujiequBound}
        startSteamBindPending={startSteamBind.isPending}
        unbindSteamPending={unbindSteam.isPending}
        onStartSteamBind={() => startSteamBind.mutate()}
        onUnbindSteam={() => unbindSteam.mutate()}
        startQqBindPending={startQqBind.isPending}
        unbindQqPending={unbindQqMut.isPending}
        onStartQqBind={() => startQqBind.mutate()}
        onUnbindQq={() => unbindQqMut.mutate()}
        unbindSklandPending={unbindSklandMut.isPending}
        onUnbindSkland={() => unbindSklandMut.mutate()}
        unbindTaygedoPending={unbindTaygedoMut.isPending}
        onUnbindTaygedo={() => unbindTaygedoMut.mutate()}
        unbindExiliumPending={unbindExiliumMut.isPending}
        onUnbindExilium={() => unbindExiliumMut.mutate()}
        unbindKujiequPending={unbindKujiequMut.isPending}
        onUnbindKujiequ={() => unbindKujiequMut.mutate()}
        invalidateProfile={invalidateProfile}
      />
    </div>
  );
}
