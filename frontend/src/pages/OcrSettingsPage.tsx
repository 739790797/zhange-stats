import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Checkbox,
  Form,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchOcrSettings, updateOcrSettings } from "@/api/settingsApi";
import { AdminStepUpModal } from "@/components/AdminStepUpModal";
import { PageHeader } from "@/components/PageHeader";
import { ADMIN_STEP_UP_BLOCKED, requestAdminStepUp } from "@/lib/adminCanStepUp";
import { apiError } from "@/lib/apiError";
import { useAuthStore } from "@/stores/authStore";

type FormValues = {
  paddle_profile: string;
  engines: Record<string, boolean>;
  use_cases: Record<string, string[]>;
};

export default function OcrSettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const user = useAuthStore((s) => s.user);
  const [pending, setPending] = useState<FormValues | null>(null);
  const enginesWatch = Form.useWatch("engines", form);

  const { data, isLoading } = useQuery({
    queryKey: ["ocr-settings"],
    queryFn: fetchOcrSettings,
  });

  useEffect(() => {
    if (!data) return;
    form.setFieldsValue({
      paddle_profile: data.paddle_profile,
      engines: data.engines,
      use_cases: data.use_cases,
    });
  }, [data, form]);

  const save = useMutation({
    mutationFn: ({ payload, code }: { payload: FormValues; code: string }) =>
      updateOcrSettings(payload, code),
    onSuccess: () => {
      message.success("文字识别配置已保存");
      setPending(null);
      queryClient.invalidateQueries({ queryKey: ["ocr-settings"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const engineIds = Object.keys(data?.engine_labels || { paddle: "", easyocr: "", tess: "" });
  const labels = data?.engine_labels || {};

  return (
    <div>
      <PageHeader
        title="文字识别"
        subtitle="站内共享 OCR：选引擎、Paddle 档位，以及各业务用哪几路。不对外提供通用识别接口。"
      />
      <Form
        form={form}
        layout="vertical"
        disabled={isLoading}
        onFinish={(values) => {
          requestAdminStepUp(user, {
            onBlocked: () => message.warning(ADMIN_STEP_UP_BLOCKED),
            onNeedCode: () => setPending(values),
            onSkip: () => save.mutate({ payload: values, code: "" }),
          });
        }}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 20 }}
          message="换 Paddle 档位后，请到任务配置运行「识别模型更新」。识别时不会现场下载权重。"
          action={
            <Link to="/settings/task-config">
              <Button size="small">任务配置</Button>
            </Link>
          }
        />

        <Form.Item
          name="paddle_profile"
          label="熊猫 OCR 档位"
          extra="v5 / v6 同属 Paddle 族，钥匙箱交叉验证里不能当两票。默认 v5 server 更准。"
          rules={[{ required: true, message: "请选择档位" }]}
        >
          <Select
            options={(data?.paddle_profiles || []).map((row) => ({
              value: row.id,
              label: row.label,
            }))}
          />
        </Form.Item>

        <Form.Item label="引擎开关" extra="关掉后，所有场景都不会再用这一路。">
          <Space wrap>
            {engineIds.map((id) => (
              <Form.Item
                key={id}
                name={["engines", id]}
                valuePropName="checked"
                noStyle
              >
                <Checkbox>{labels[id] || id}</Checkbox>
              </Form.Item>
            ))}
          </Space>
        </Form.Item>

        {(data?.use_case_meta || []).map((meta) => (
          <Form.Item
            key={meta.id}
            name={["use_cases", meta.id]}
            label={meta.label}
            extra={meta.hint}
          >
            <Checkbox.Group
              options={engineIds.map((id) => ({
                value: id,
                label: labels[id] || id,
                disabled: enginesWatch?.[id] === false,
              }))}
            />
          </Form.Item>
        ))}

        <Typography.Paragraph type="secondary" style={{ fontSize: 13 }}>
          本机状态
        </Typography.Paragraph>
        <Space wrap style={{ marginBottom: 8 }}>
          {(data?.engine_status || []).map((row) => (
            <Space key={row.id} size={6}>
              <Typography.Text>{row.label || row.id}</Typography.Text>
              <Tag color={row.installed ? "success" : "default"}>
                {row.installed ? "已安装" : "未安装"}
              </Tag>
              <Tag color={row.models_ready ? "success" : "warning"}>
                {row.id === "tess"
                  ? row.models_ready
                    ? "系统就绪"
                    : "未就绪"
                  : row.models_ready
                    ? "权重就绪"
                    : "权重未就绪"}
              </Tag>
            </Space>
          ))}
        </Space>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 20 }}>
          熊猫 OCR / EasyOCR 用任务配置「识别模型更新」拉权重。Tesseract
          是系统程序，不能点保存安装：Windows 装{" "}
          <Typography.Link
            href="https://github.com/UB-Mannheim/tesseract/wiki"
            target="_blank"
            rel="noreferrer"
          >
            UB Mannheim 安装包
          </Typography.Link>
          （勾选 chi_sim + eng，并把安装目录加入 PATH），Linux 用{" "}
          <Typography.Text code>
            apt install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
          </Typography.Text>
          。装完重启后端再刷新本页。钥匙箱交叉验证有熊猫 + EasyOCR
          就够，Tesseract 只是可选第三路。
        </Typography.Paragraph>

        <Space>
          <Button type="primary" htmlType="submit" loading={save.isPending}>
            保存
          </Button>
        </Space>
      </Form>
      <AdminStepUpModal
        open={pending != null}
        title="保存文字识别配置需邮箱验证码"
        confirmLoading={save.isPending}
        onCancel={() => setPending(null)}
        onConfirm={(code) => {
          if (!pending) return;
          save.mutate({ payload: pending, code });
        }}
      />
    </div>
  );
}
