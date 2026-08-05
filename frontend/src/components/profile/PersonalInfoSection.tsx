import { CameraOutlined } from "@ant-design/icons";
import {
  Avatar,
  Button,
  Card,
  Descriptions,
  Input,
  Space,
  Upload,
} from "antd";
import type { UploadProps } from "antd";
import type { MemberProfile } from "@/api/types";

type PersonalInfoSectionProps = {
  isLoading: boolean;
  errMsg: string | null;
  data: MemberProfile | undefined;
  displayName: string;
  nameDraft: string;
  onNameDraftChange: (value: string) => void;
  saveNamePending: boolean;
  onSaveName: () => void;
  beforeUpload: UploadProps["beforeUpload"];
  uploadAvatarPending: boolean;
};

export function PersonalInfoSection({
  isLoading,
  errMsg,
  data,
  displayName,
  nameDraft,
  onNameDraftChange,
  saveNamePending,
  onSaveName,
  beforeUpload,
  uploadAvatarPending,
}: PersonalInfoSectionProps) {
  return (
    <Card title="个人信息" loading={isLoading} style={{ marginBottom: 24 }}>
      <Space align="start" size={20}>
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
          <Space.Compact style={{ width: "100%", maxWidth: 360, marginBottom: 8 }}>
            <Input
              value={nameDraft}
              onChange={(e) => onNameDraftChange(e.target.value)}
              placeholder="显示名称"
              disabled={!!errMsg || !data || saveNamePending}
              maxLength={64}
            />
            <Button
              type="primary"
              loading={saveNamePending}
              disabled={
                !!errMsg ||
                !data ||
                !nameDraft.trim() ||
                nameDraft.trim() === displayName
              }
              onClick={onSaveName}
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
  );
}
