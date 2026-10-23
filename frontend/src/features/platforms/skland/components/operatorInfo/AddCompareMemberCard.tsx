import { useState } from "react";
import { Avatar, Button, Modal, Select, Space, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";

export type OperatorCompareCandidate = {
  member_id: number;
  nickname: string;
  avatar_url?: string | null;
  game_role_name?: string | null;
  is_self: boolean;
  skland_bound: boolean;
};

export function AddCompareMemberCard({
  gameName,
  disabled,
  loading,
  candidates,
  onAdd,
}: {
  gameName: string;
  disabled?: boolean;
  loading?: boolean;
  candidates: OperatorCompareCandidate[];
  onAdd: (memberId: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<number | null>(null);

  return (
    <>
      <Button
        type="dashed"
        block
        icon={<PlusOutlined />}
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          setPicked(null);
          setOpen(true);
        }}
      >
        新增对比成员
      </Button>
      {disabled ? (
        <Typography.Text type="secondary" style={{ display: "block", textAlign: "center", fontSize: 12 }}>
          {candidates.length === 0
            ? `暂无其他符合条件的${gameName}角色`
            : "已达到同时对比人数上限"}
        </Typography.Text>
      ) : null}
      <Modal
        title="新增对比成员"
        open={open}
        onCancel={() => setOpen(false)}
        okText="添加"
        cancelText="取消"
        confirmLoading={loading}
        okButtonProps={{ disabled: picked == null }}
        onOk={() => {
          if (picked == null) return;
          onAdd(picked);
          setOpen(false);
        }}
        destroyOnClose
      >
        <Select
          showSearch
          optionFilterProp="label"
          placeholder={`选择有${gameName}角色的用户`}
          style={{ width: "100%" }}
          loading={loading}
          value={picked ?? undefined}
          onChange={(id: number) => setPicked(id)}
          options={candidates.map((candidate) => ({
            value: candidate.member_id,
            label: candidate.game_role_name || candidate.nickname,
            title: `${candidate.game_role_name || candidate.nickname} · ${candidate.nickname}`,
          }))}
          optionRender={(option) => {
            const candidate = candidates.find(
              (item) => item.member_id === option.value,
            );
            if (!candidate) return option.label;
            return (
              <Space size={8}>
                <Avatar src={candidate.avatar_url || undefined} size="small">
                  {(candidate.nickname || "?").slice(0, 1)}
                </Avatar>
                <Space direction="vertical" size={0}>
                  <Typography.Text>
                    {candidate.game_role_name || candidate.nickname}
                  </Typography.Text>
                  {candidate.game_role_name &&
                  candidate.game_role_name !== candidate.nickname ? (
                    <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                      {candidate.nickname}
                    </Typography.Text>
                  ) : null}
                </Space>
              </Space>
            );
          }}
        />
        <Typography.Text
          type="secondary"
          style={{ display: "block", marginTop: 10, fontSize: 12 }}
        >
          可选站内已绑定森空岛且有{gameName}角色的用户。其他成员展示最近的本地快照，不会使用对方凭证回源。
        </Typography.Text>
      </Modal>
    </>
  );
}
