import { Button, Form, Input, Space } from "antd";
import type { FormItemProps } from "antd";
import type { CSSProperties, ReactNode } from "react";
import { secretPlaceholder } from "@/lib/secretInput";

/** 只写密钥栏：从不回填原值，留空不修改；点「清除」后保存才清空（调用方据 clearing 发 clear_*）。 */
export function SecretFormItem({
  name,
  label,
  extra,
  required,
  rules,
  style,
  set,
  hint,
  clearing,
  onClearingChange,
  emptyPlaceholder,
  clearText = "清除",
}: {
  name: string;
  label: ReactNode;
  extra?: ReactNode;
  required?: boolean;
  rules?: FormItemProps["rules"];
  style?: CSSProperties;
  set: boolean;
  hint?: string | null;
  clearing: boolean;
  onClearingChange: (next: boolean) => void;
  emptyPlaceholder: string;
  clearText?: string;
}) {
  const form = Form.useFormInstance();
  return (
    <Form.Item label={label} extra={extra} required={required} style={style}>
      <Space.Compact style={{ width: "100%" }}>
        <Form.Item name={name} noStyle rules={rules}>
          <Input.Password
            disabled={clearing}
            placeholder={secretPlaceholder({ set, hint, clearing, empty: emptyPlaceholder })}
            autoComplete="new-password"
          />
        </Form.Item>
        {set ? (
          <Button
            htmlType="button"
            danger={!clearing}
            onClick={() => {
              if (!clearing) form.setFieldValue(name, "");
              onClearingChange(!clearing);
            }}
          >
            {clearing ? "撤销清除" : clearText}
          </Button>
        ) : null}
      </Space.Compact>
    </Form.Item>
  );
}
