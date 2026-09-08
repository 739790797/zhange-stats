import { CameraOutlined } from "@ant-design/icons";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Avatar,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Modal,
  Space,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadProps } from "antd";
import { useState } from "react";
import {
  changeOwnPassword,
  changeOwnUsername,
  deleteOwnAccount,
  fetchMe,
  fetchPasswordPolicy,
  sendDeleteAccountCode,
} from "@/api/client";
import type { MemberProfile } from "@/api/types";
import { apiError } from "@/lib/apiError";
import { useAuthStore } from "@/stores/authStore";

/** 注册时自动生成的登录名，不在界面展示 */
function isAutoUsername(username: string | null | undefined) {
  return Boolean(username && /^user_[a-z0-9]+$/i.test(username));
}

type PasswordForm = {
  current_password: string;
  new_password: string;
  confirm_password: string;
};

type UsernameForm = {
  new_username: string;
  current_password: string;
};

type PersonalInfoSectionProps = {
  isLoading: boolean;
  errMsg: string | null;
  data: MemberProfile | undefined;
  displayName: string;
  beforeUpload: UploadProps["beforeUpload"];
  uploadAvatarPending: boolean;
  /** 本人个人中心才显示改用户名/改密 */
  showAccountActions?: boolean;
  onUsernameChanged?: () => void;
};

export function PersonalInfoSection({
  isLoading,
  errMsg,
  data,
  displayName,
  beforeUpload,
  uploadAvatarPending,
  showAccountActions = false,
  onUsernameChanged,
}: PersonalInfoSectionProps) {
  const setUser = useAuthStore((s) => s.setUser);
  const authUser = useAuthStore((s) => s.user);
  const username = data?.username || authUser?.username || "";
  const showUsername = Boolean(username) && !isAutoUsername(username);

  const [pwdOpen, setPwdOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteSending, setDeleteSending] = useState(false);
  const [pwdForm] = Form.useForm<PasswordForm>();
  const [userForm] = Form.useForm<UsernameForm>();
  const [deleteForm] = Form.useForm<{ code: string }>();
  const logout = useAuthStore((s) => s.logout);

  const policyQuery = useQuery({
    queryKey: ["password-policy"],
    queryFn: fetchPasswordPolicy,
    staleTime: 60_000,
    enabled: pwdOpen,
  });
  const minLen = policyQuery.data?.min_password_length || 8;

  const changePassword = useMutation({
    mutationFn: changeOwnPassword,
    onSuccess: (res) => {
      message.success(res.message || "密码已更新");
      pwdForm.resetFields();
      setPwdOpen(false);
    },
    onError: (e: unknown) => message.error(apiError(e, "修改失败")),
  });

  const changeUsername = useMutation({
    mutationFn: changeOwnUsername,
    onSuccess: async (res) => {
      message.success(res.message || "用户名已更新");
      try {
        const me = await fetchMe();
        setUser(me);
      } catch {
        if (authUser) {
          setUser({ ...authUser, username: res.username });
        }
      }
      userForm.resetFields();
      setUserOpen(false);
      onUsernameChanged?.();
    },
    onError: (e: unknown) => message.error(apiError(e, "修改失败")),
  });

  const deleteAccount = useMutation({
    mutationFn: (code: string) => deleteOwnAccount(code),
    onSuccess: (res) => {
      message.success(res.message || "账号已注销");
      logout();
      window.location.assign("/login");
    },
    onError: (e: unknown) => message.error(apiError(e, "注销失败")),
  });

  const me = useAuthStore((s) => s.user);
  const canDelete = Boolean(me?.email && me?.email_verified);

  return (
    <Card title="个人信息" loading={isLoading} style={{ marginBottom: 24 }}>
      <Space align="start" size={20} style={{ width: "100%" }}>
        <Upload
          accept="image/jpeg,image/png,image/webp,image/gif"
          showUploadList={false}
          beforeUpload={beforeUpload}
          disabled={!!errMsg || !data || uploadAvatarPending}
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
          <Typography.Title level={4} style={{ margin: "0 0 8px" }}>
            {displayName}
          </Typography.Title>
          <Descriptions column={1} size="small">
            {showUsername ? (
              <Descriptions.Item label="用户名">{username}</Descriptions.Item>
            ) : null}
            <Descriptions.Item label="邮箱">{data?.email || "未绑定"}</Descriptions.Item>
          </Descriptions>
          {showAccountActions ? (
            <Space style={{ marginTop: 12 }} wrap>
              <Button
                disabled={!!errMsg || !data}
                onClick={() => {
                  userForm.setFieldsValue({
                    new_username: showUsername ? username : "",
                    current_password: "",
                  });
                  setUserOpen(true);
                }}
              >
                修改用户名
              </Button>
              <Button
                disabled={!!errMsg || !data}
                onClick={() => {
                  pwdForm.resetFields();
                  setPwdOpen(true);
                }}
              >
                修改密码
              </Button>
              <Button
                danger
                disabled={!!errMsg || !data}
                onClick={() => {
                  deleteForm.resetFields();
                  setDeleteOpen(true);
                }}
              >
                注销账号
              </Button>
            </Space>
          ) : null}
        </div>
      </Space>

      {showAccountActions ? (
        <>
          <Modal
            title="修改用户名"
            open={userOpen}
            onCancel={() => setUserOpen(false)}
            okText="保存"
            confirmLoading={changeUsername.isPending}
            destroyOnClose
            onOk={() => userForm.submit()}
          >
            <Form
              form={userForm}
              layout="vertical"
              style={{ marginTop: 8 }}
              onFinish={(values) => {
                changeUsername.mutate({
                  new_username: values.new_username.trim(),
                  current_password: values.current_password,
                });
              }}
            >
              <Form.Item
                name="new_username"
                label="登录用户名"
                extra="用于账号密码登录；以字母开头，仅含字母/数字/下划线，3～32 位。可与显示名称不同。"
                rules={[
                  { required: true, message: "请输入用户名" },
                  {
                    pattern: /^[a-zA-Z][a-zA-Z0-9_]{2,31}$/,
                    message: "格式不符合要求",
                  },
                ]}
              >
                <Input autoComplete="username" maxLength={32} />
              </Form.Item>
              <Form.Item
                name="current_password"
                label="当前密码"
                rules={[{ required: true, message: "请输入当前密码以确认" }]}
              >
                <Input.Password autoComplete="current-password" />
              </Form.Item>
            </Form>
          </Modal>

          <Modal
            title="修改密码"
            open={pwdOpen}
            onCancel={() => setPwdOpen(false)}
            okText="更新密码"
            confirmLoading={changePassword.isPending}
            destroyOnClose
            onOk={() => pwdForm.submit()}
          >
            <Form
              form={pwdForm}
              layout="vertical"
              style={{ marginTop: 8 }}
              onFinish={(values) => {
                changePassword.mutate({
                  current_password: values.current_password,
                  new_password: values.new_password,
                });
              }}
            >
              <Form.Item
                name="current_password"
                label="当前密码"
                rules={[{ required: true, message: "请输入当前密码" }]}
              >
                <Input.Password autoComplete="current-password" />
              </Form.Item>
              <Form.Item
                name="new_password"
                label="新密码"
                rules={[
                  { required: true, message: "请输入新密码" },
                  { min: minLen, message: `至少 ${minLen} 位` },
                ]}
              >
                <Input.Password autoComplete="new-password" />
              </Form.Item>
              <Form.Item
                name="confirm_password"
                label="确认新密码"
                dependencies={["new_password"]}
                rules={[
                  { required: true, message: "请再次输入新密码" },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue("new_password") === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error("两次输入的新密码不一致"));
                    },
                  }),
                ]}
              >
                <Input.Password autoComplete="new-password" />
              </Form.Item>
            </Form>
          </Modal>

          <Modal
            title="注销账号"
            open={deleteOpen}
            onCancel={() => setDeleteOpen(false)}
            okText="确认注销"
            okButtonProps={{ danger: true, disabled: !canDelete }}
            confirmLoading={deleteAccount.isPending}
            destroyOnClose
            onOk={() => deleteForm.submit()}
          >
            {!canDelete ? (
              <Typography.Paragraph>
                请先绑定并验证邮箱，才能申请注销。处理即时完成；已发布的酒馆文章会保留，作者显示为「已注销用户」。
              </Typography.Paragraph>
            ) : (
              <>
                <Typography.Paragraph>
                  注销后无法用原邮箱登录，平台绑定会解除。已发布的酒馆文章会保留并显示「已注销用户」，草稿会删除。通常即时完成（不超过 15 日）。
                </Typography.Paragraph>
                <Form
                  form={deleteForm}
                  layout="vertical"
                  onFinish={(values) => deleteAccount.mutate(values.code.trim())}
                >
                  <Form.Item label="邮箱验证码" required>
                    <Space.Compact style={{ width: "100%" }}>
                      <Form.Item
                        name="code"
                        noStyle
                        rules={[{ required: true, message: "请输入验证码" }]}
                      >
                        <Input maxLength={16} autoComplete="one-time-code" />
                      </Form.Item>
                      <Button
                        loading={deleteSending}
                        onClick={async () => {
                          setDeleteSending(true);
                          try {
                            const res = await sendDeleteAccountCode();
                            message.success(res.message);
                          } catch (e: unknown) {
                            message.error(apiError(e, "发送失败"));
                          } finally {
                            setDeleteSending(false);
                          }
                        }}
                      >
                        发送验证码
                      </Button>
                    </Space.Compact>
                  </Form.Item>
                </Form>
              </>
            )}
          </Modal>
        </>
      ) : null}
    </Card>
  );
}
