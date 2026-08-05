import { CameraOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Descriptions,
  Input,
  Modal,
  Popconfirm,
  Space,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadProps } from "antd";
import { useEffect, useState, type ReactNode } from "react";
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
import { ExiliumBindPanel } from "@/components/ExiliumBindPanel";
import { KujiequBindPanel } from "@/components/KujiequBindPanel";
import { SklandBindPanel } from "@/components/SklandBindPanel";
import { TaygedoBindPanel } from "@/components/TaygedoBindPanel";
import { isFeatureOn } from "@/lib/platformFeatures";
import { useAuthStore } from "@/stores/authStore";

/** 避免 React StrictMode 双次挂载导致绑定回跳提示重复弹出 */
let handledSteamBindQuery: string | null = null;
let handledQqBindQuery: string | null = null;

type ProfilePayload = {
  display_name?: string;
  steam_id?: string | null;
};

function apiError(e: unknown, fallback: string) {
  const detail =
    e &&
    typeof e === "object" &&
    "response" in e &&
    (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return String(detail || (e as Error)?.message || fallback);
}

/** 绑定行标题：名称定宽，状态标签纵向对齐 */
function BindStatusTitle({
  name,
  bound,
  leading,
}: {
  name: string;
  bound: boolean;
  leading?: ReactNode;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      {leading}
      <Typography.Text
        strong
        style={{ width: "3.75em", flex: "0 0 3.75em", lineHeight: "22px" }}
      >
        {name}
      </Typography.Text>
      {bound ? <Tag color="success">已绑定</Tag> : <Tag>未绑定</Tag>}
    </div>
  );
}

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
  const [sklandModalOpen, setSklandModalOpen] = useState(false);
  const [taygedoModalOpen, setTaygedoModalOpen] = useState(false);
  const [exiliumModalOpen, setExiliumModalOpen] = useState(false);
  const [kujiequModalOpen, setKujiequModalOpen] = useState(false);
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

  const closeSklandModal = () => {
    setSklandModalOpen(false);
  };

  const closeTaygedoModal = () => {
    setTaygedoModalOpen(false);
  };

  const closeExiliumModal = () => {
    setExiliumModalOpen(false);
  };

  const closeKujiequModal = () => {
    setKujiequModalOpen(false);
  };

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

  const errMsg =
    isError && error && typeof error === "object" && "response" in error
      ? String(
          (error as { response?: { data?: { detail?: string } } }).response?.data
            ?.detail || "加载失败",
        )
      : null;

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

      <Card title="个人信息" loading={isLoading} style={{ marginBottom: 24 }}>
        <Space align="start" size={20}>
          <Upload
            accept="image/jpeg,image/png,image/webp,image/gif"
            showUploadList={false}
            beforeUpload={beforeUpload}
            disabled={!!errMsg || !data || uploadAvatar.isPending}
          >
            <button
              type="button"
              title="点击上传头像"
              style={{
                position: "relative",
                padding: 0,
                border: "none",
                background: "transparent",
                cursor: errMsg || !data ? "not-allowed" : "pointer",
                borderRadius: "50%",
              }}
            >
              <Avatar size={72} src={data?.avatar_url || undefined}>
                {displayName !== "-" ? displayName[0] : "?"}
              </Avatar>
              <span
                style={{
                  position: "absolute",
                  right: 0,
                  bottom: 0,
                  width: 24,
                  height: 24,
                  borderRadius: "50%",
                  background: "#1a2332",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12,
                  boxShadow: "0 0 0 2px #fff",
                }}
              >
                <CameraOutlined />
              </span>
            </button>
          </Upload>
          <div style={{ flex: 1, minWidth: 0 }}>
            <Space.Compact style={{ width: "100%", maxWidth: 360, marginBottom: 8 }}>
              <Input
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                placeholder="显示名称"
                disabled={!!errMsg || !data || saveName.isPending}
                maxLength={64}
              />
              <Button
                type="primary"
                loading={saveName.isPending}
                disabled={
                  !!errMsg ||
                  !data ||
                  !nameDraft.trim() ||
                  nameDraft.trim() === displayName
                }
                onClick={() => saveName.mutate(nameDraft.trim())}
              >
                保存
              </Button>
            </Space.Compact>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="邮箱">{data?.email || "未绑定"}</Descriptions.Item>
            </Descriptions>
          </div>
        </Space>
      </Card>

      <Card title="账号绑定" loading={isLoading && !errMsg}>
        {showSteam ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            padding: "16px 4px",
            borderBottom: "1px solid rgba(0,0,0,0.06)",
          }}
        >
          <div style={{ minWidth: 0 }}>
            <BindStatusTitle
              name="Steam"
              bound={steamBound}
              leading={
                steamBound ? (
                  <Avatar size={28} src={data?.steam_avatar_url || undefined}>
                    S
                  </Avatar>
                ) : null
              }
            />
            {steamBound ? (
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                  {`${data?.steam_persona_name || "已绑定"} · SteamID：${data?.steam_id}${
                    data?.steam_friends_public === false
                      ? " · 好友列表未公开（日历只能看自己）"
                      : data?.steam_friends_public
                        ? " · 好友列表已同步"
                        : ""
                  }`}
                </Typography.Text>
              </div>
            ) : null}
          </div>
          <Space>
            {steamBound ? (
              <>
                <Button
                  loading={startSteamBind.isPending}
                  disabled={!!errMsg}
                  onClick={() => startSteamBind.mutate()}
                >
                  换绑
                </Button>
                <Popconfirm
                  title="确认解除 Steam 绑定？"
                  okText="确定"
                  cancelText="取消"
                  onConfirm={() => unbindSteam.mutate()}
                >
                  <Button danger loading={unbindSteam.isPending} disabled={!!errMsg}>
                    解绑
                  </Button>
                </Popconfirm>
              </>
            ) : (
              <Button
                type="primary"
                loading={startSteamBind.isPending}
                disabled={!!errMsg}
                onClick={() => startSteamBind.mutate()}
              >
                绑定
              </Button>
            )}
          </Space>
        </div>
        ) : null}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            padding: "16px 4px",
            borderBottom: "1px solid rgba(0,0,0,0.06)",
          }}
        >
          <div style={{ minWidth: 0 }}>
            <BindStatusTitle
              name="QQ"
              bound={qqBound}
              leading={
                qqBound && data?.qq_avatar_url ? (
                  <Avatar size={28} src={data.qq_avatar_url}>
                    Q
                  </Avatar>
                ) : null
              }
            />
            {qqBound ? (
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                  {`昵称：${data?.qq_nickname || "已绑定"}`}
                </Typography.Text>
              </div>
            ) : null}
          </div>
          <Space>
            {qqBound ? (
              <>
                <Button
                  loading={startQqBind.isPending}
                  disabled={!!errMsg}
                  onClick={() => startQqBind.mutate()}
                >
                  换绑
                </Button>
                <Popconfirm
                  title="确认解除 QQ 绑定？"
                  okText="确定"
                  cancelText="取消"
                  onConfirm={() => unbindQqMut.mutate()}
                >
                  <Button danger loading={unbindQqMut.isPending} disabled={!!errMsg}>
                    解绑
                  </Button>
                </Popconfirm>
              </>
            ) : (
              <Button
                type="primary"
                loading={startQqBind.isPending}
                disabled={!!errMsg}
                onClick={() => startQqBind.mutate()}
              >
                绑定
              </Button>
            )}
          </Space>
        </div>

        {!isAdminEdit && showSkland ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              padding: "16px 4px",
            }}
          >
            <div style={{ minWidth: 0 }}>
              <BindStatusTitle name="森空岛" bound={sklandBound} />
            </div>
            <Space>
              {sklandBound ? (
                <>
                  <Button disabled={!!errMsg} onClick={() => setSklandModalOpen(true)}>
                    换绑
                  </Button>
                  <Popconfirm
                    title="确认解除森空岛绑定？"
                    okText="确定"
                    cancelText="取消"
                    onConfirm={() => unbindSklandMut.mutate()}
                  >
                    <Button
                      danger
                      loading={unbindSklandMut.isPending}
                      disabled={!!errMsg}
                    >
                      解绑
                    </Button>
                  </Popconfirm>
                </>
              ) : (
                <Button
                  type="primary"
                  disabled={!!errMsg}
                  onClick={() => setSklandModalOpen(true)}
                >
                  绑定
                </Button>
              )}
            </Space>
          </div>
        ) : null}

        {!isAdminEdit && showTaygedo ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              padding: "16px 4px",
              borderTop: "1px solid rgba(0,0,0,0.06)",
            }}
          >
            <div style={{ minWidth: 0 }}>
              <BindStatusTitle name="塔吉多" bound={taygedoBound} />
            </div>
            <Space>
              {taygedoBound ? (
                <>
                  <Button disabled={!!errMsg} onClick={() => setTaygedoModalOpen(true)}>
                    换绑
                  </Button>
                  <Popconfirm
                    title="确认解除塔吉多绑定？"
                    okText="确定"
                    cancelText="取消"
                    onConfirm={() => unbindTaygedoMut.mutate()}
                  >
                    <Button
                      danger
                      loading={unbindTaygedoMut.isPending}
                      disabled={!!errMsg}
                    >
                      解绑
                    </Button>
                  </Popconfirm>
                </>
              ) : (
                <Button
                  type="primary"
                  disabled={!!errMsg}
                  onClick={() => setTaygedoModalOpen(true)}
                >
                  绑定
                </Button>
              )}
            </Space>
          </div>
        ) : null}

        {!isAdminEdit && showExilium ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              padding: "16px 4px",
              borderTop: "1px solid rgba(0,0,0,0.06)",
            }}
          >
            <div style={{ minWidth: 0 }}>
              <BindStatusTitle name="追放" bound={exiliumBound} />
            </div>
            <Space>
              {exiliumBound ? (
                <>
                  <Button disabled={!!errMsg} onClick={() => setExiliumModalOpen(true)}>
                    换绑
                  </Button>
                  <Popconfirm
                    title="确认解除追放社区绑定？"
                    okText="确定"
                    cancelText="取消"
                    onConfirm={() => unbindExiliumMut.mutate()}
                  >
                    <Button
                      danger
                      loading={unbindExiliumMut.isPending}
                      disabled={!!errMsg}
                    >
                      解绑
                    </Button>
                  </Popconfirm>
                </>
              ) : (
                <Button
                  type="primary"
                  disabled={!!errMsg}
                  onClick={() => setExiliumModalOpen(true)}
                >
                  绑定
                </Button>
              )}
            </Space>
          </div>
        ) : null}

        {!isAdminEdit && showKujiequ ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              padding: "16px 4px",
              borderTop: "1px solid rgba(0,0,0,0.06)",
            }}
          >
            <div style={{ minWidth: 0 }}>
              <BindStatusTitle name="库街区" bound={kujiequBound} />
            </div>
            <Space>
              {kujiequBound ? (
                <>
                  <Button disabled={!!errMsg} onClick={() => setKujiequModalOpen(true)}>
                    换绑
                  </Button>
                  <Popconfirm
                    title="确认解除库街区绑定？"
                    okText="确定"
                    cancelText="取消"
                    onConfirm={() => unbindKujiequMut.mutate()}
                  >
                    <Button
                      danger
                      loading={unbindKujiequMut.isPending}
                      disabled={!!errMsg}
                    >
                      解绑
                    </Button>
                  </Popconfirm>
                </>
              ) : (
                <Button
                  type="primary"
                  disabled={!!errMsg}
                  onClick={() => setKujiequModalOpen(true)}
                >
                  绑定
                </Button>
              )}
            </Space>
          </div>
        ) : null}
      </Card>

      <Modal
        title={sklandBound ? "更换森空岛绑定" : "绑定森空岛"}
        open={sklandModalOpen && !isAdminEdit}
        footer={null}
        onCancel={closeSklandModal}
        destroyOnClose
        width={480}
      >
        {sklandModalOpen && !isAdminEdit ? (
          <SklandBindPanel
            title=""
            onSuccess={() => {
              invalidateProfile();
              queryClient.invalidateQueries({ queryKey: ["skland-logs"] });
              closeSklandModal();
            }}
          />
        ) : null}
      </Modal>

      <Modal
        title={taygedoBound ? "更换塔吉多绑定" : "绑定塔吉多"}
        open={taygedoModalOpen && !isAdminEdit}
        footer={null}
        onCancel={closeTaygedoModal}
        destroyOnClose
        width={480}
      >
        {taygedoModalOpen && !isAdminEdit ? (
          <TaygedoBindPanel
            title=""
            onSuccess={() => {
              invalidateProfile();
              queryClient.invalidateQueries({ queryKey: ["taygedo-logs"] });
              closeTaygedoModal();
            }}
          />
        ) : null}
      </Modal>

      <Modal
        title={exiliumBound ? "更换追放绑定" : "绑定追放"}
        open={exiliumModalOpen && !isAdminEdit}
        footer={null}
        onCancel={closeExiliumModal}
        destroyOnClose
        width={480}
      >
        {exiliumModalOpen && !isAdminEdit ? (
          <ExiliumBindPanel
            title=""
            onSuccess={() => {
              invalidateProfile();
              closeExiliumModal();
            }}
          />
        ) : null}
      </Modal>

      <Modal
        title={kujiequBound ? "更换库街区绑定" : "绑定库街区"}
        open={kujiequModalOpen && !isAdminEdit}
        footer={null}
        onCancel={closeKujiequModal}
        destroyOnClose
        width={480}
      >
        {kujiequModalOpen && !isAdminEdit ? (
          <KujiequBindPanel
            title=""
            onSuccess={() => {
              invalidateProfile();
              closeKujiequModal();
            }}
          />
        ) : null}
      </Modal>
    </div>
  );
}
