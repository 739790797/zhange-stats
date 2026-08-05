import { useState } from "react";
import { Modal, Select, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { ArknightsCompareCandidate } from "@/api/types";
import { COMPARE_MAX } from "./constants";

export function AddCompareCard({
  disabled,
  loading,
  candidates,
  onAdd,
}: {
  disabled?: boolean;
  loading?: boolean;
  candidates: ArknightsCompareCandidate[];
  onAdd: (memberId: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<number | null>(null);

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          setPicked(null);
          setOpen(true);
        }}
        style={{
          width: "100%",
          minHeight: 88,
          marginTop: 12,
          border: "1px dashed rgba(0,0,0,0.18)",
          borderRadius: 10,
          background: disabled ? "#f5f5f5" : "#fafafa",
          cursor: disabled ? "not-allowed" : "pointer",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
          color: disabled ? "#bfbfbf" : "#666",
          transition: "border-color 0.2s, background 0.2s, color 0.2s",
        }}
        onMouseEnter={(e) => {
          if (disabled) return;
          e.currentTarget.style.borderColor = "#1677ff";
          e.currentTarget.style.color = "#1677ff";
          e.currentTarget.style.background = "#f0f7ff";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "rgba(0,0,0,0.18)";
          e.currentTarget.style.color = disabled ? "#bfbfbf" : "#666";
          e.currentTarget.style.background = disabled ? "#f5f5f5" : "#fafafa";
        }}
      >
        <PlusOutlined style={{ fontSize: 22 }} />
        <span style={{ fontSize: 14, fontWeight: 500 }}>新增对比</span>
        {disabled ? (
          <span style={{ fontSize: 12 }}>最多 {COMPARE_MAX} 人</span>
        ) : null}
      </button>

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
          placeholder="选择 Steam 好友"
          style={{ width: "100%" }}
          loading={loading}
          value={picked ?? undefined}
          onChange={(id: number) => setPicked(id)}
          options={candidates.map((c) => ({
            value: c.member_id,
            label: `${c.nickname}${c.is_self ? "（我）" : ""}${
              c.skland_bound ? "" : " · 未绑森空岛"
            }`,
          }))}
        />
        <Typography.Text
          type="secondary"
          style={{ display: "block", marginTop: 10, fontSize: 12 }}
        >
          需为 Steam 双向好友。添加后可在左侧切换渠道服。
        </Typography.Text>
      </Modal>
    </>
  );
}
