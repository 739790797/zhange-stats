import { useMutation } from "@tanstack/react-query";
import { Button, Form, Input, Modal, Space, message } from "antd";
import type { FormInstance } from "antd/es/form";
import type { ReactNode } from "react";
import { useEffect } from "react";
import {
  fetchMinecraftFileContents,
  writeMinecraftFile,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";

export type MinecraftTextFileEditorValues = { name: string; content: string };

export function MinecraftTextFileFormModal({
  open,
  title,
  nameDisabled,
  confirmLoading,
  form,
  extra,
  okText = "保存",
  onCancel,
  onOk,
}: {
  open: boolean;
  title: string;
  nameDisabled?: boolean;
  confirmLoading?: boolean;
  form: FormInstance<MinecraftTextFileEditorValues>;
  extra?: ReactNode;
  okText?: string;
  onCancel: () => void;
  onOk: () => void;
}) {
  return (
    <Modal
      title={title}
      open={open}
      width={840}
      confirmLoading={confirmLoading}
      onCancel={onCancel}
      footer={
        <div
          style={{
            display: "flex",
            justifyContent: extra ? "space-between" : "flex-end",
            width: "100%",
          }}
        >
          {extra ? <div>{extra}</div> : null}
          <Space>
            <Button onClick={onCancel}>取消</Button>
            <Button type="primary" loading={confirmLoading} onClick={onOk}>
              {okText}
            </Button>
          </Space>
        </div>
      }
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label="文件名"
          rules={[{ required: true, message: "请输入文件名" }]}
        >
          <Input disabled={nameDisabled} placeholder="config.yml" />
        </Form.Item>
        <Form.Item name="content" label="内容">
          <Input.TextArea
            rows={18}
            style={{
              fontFamily:
                "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
              fontSize: 13,
            }}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export function MinecraftPathFileEditor({
  path,
  onClose,
  onSaved,
}: {
  path: string | null;
  onClose: () => void;
  onSaved?: () => void;
}) {
  const [form] = Form.useForm<MinecraftTextFileEditorValues>();
  const parts = (path || "").split("/").filter(Boolean);
  const name = parts[parts.length - 1] || "";

  useEffect(() => {
    if (!path) {
      form.resetFields();
      return;
    }
    let cancelled = false;
    fetchMinecraftFileContents(path)
      .then((res) => {
        if (cancelled) return;
        form.setFieldsValue({ name, content: res.content });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        message.error(apiError(e, "无法读取文件"));
      });
    return () => {
      cancelled = true;
    };
  }, [path, name, form]);

  const save = useMutation({
    mutationFn: async () => {
      if (!path) return;
      const values = await form.validateFields();
      return writeMinecraftFile(path, values.content);
    },
    onSuccess: () => {
      message.success("已保存");
      onSaved?.();
      onClose();
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  return (
    <MinecraftTextFileFormModal
      open={Boolean(path)}
      title={name ? `编辑 ${name}` : "编辑文件"}
      nameDisabled
      confirmLoading={save.isPending}
      form={form}
      onCancel={onClose}
      onOk={() => save.mutate()}
    />
  );
}
