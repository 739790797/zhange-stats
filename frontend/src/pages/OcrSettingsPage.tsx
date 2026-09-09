import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Checkbox,
  Col,
  Form,
  Row,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
  theme,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  fetchJobRuns,
  fetchOcrSettings,
  triggerScheduledJob,
  updateOcrSettings,
} from "@/api/settingsApi";
import { AdminStepUpModal } from "@/components/AdminStepUpModal";
import { JobRunResultModal } from "@/components/JobRunResultModal";
import { PageHeader } from "@/components/PageHeader";
import { ADMIN_STEP_UP_BLOCKED, requestAdminStepUp } from "@/lib/adminCanStepUp";
import { apiError } from "@/lib/apiError";
import type { JobRunWatch } from "@/lib/jobRunResult";
import {
  OCR_MODEL_SYNC_JOB_ID,
  OCR_MODEL_SYNC_JOB_NAME,
  crossCheckSaveError,
  groupOcrProfileOptions,
  type OcrUseCaseFormValue,
} from "@/lib/ocrSettings";
import { useAuthStore } from "@/stores/authStore";

type FormValues = {
  paddle_profile: string;
  engines: Record<string, boolean>;
  use_cases: Record<string, OcrUseCaseFormValue>;
};

export default function OcrSettingsPage() {
  const queryClient = useQueryClient();
  const { token } = theme.useToken();
  const [form] = Form.useForm<FormValues>();
  const user = useAuthStore((s) => s.user);
  const [pending, setPending] = useState<FormValues | null>(null);
  const [runWatch, setRunWatch] = useState<JobRunWatch | null>(null);
  const enginesWatch = Form.useWatch("engines", form);
  const paddleWatch = Form.useWatch("paddle_profile", form);

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

  const checkUpdates = useMutation({
    mutationFn: async () => {
      let sinceRunId = 0;
      try {
        const page = await fetchJobRuns(OCR_MODEL_SYNC_JOB_ID, {
          page: 1,
          page_size: 1,
        });
        sinceRunId = page.items?.[0]?.id ?? 0;
      } catch {
        sinceRunId = 0;
      }
      const result = await triggerScheduledJob(OCR_MODEL_SYNC_JOB_ID, {});
      return { result, sinceRunId };
    },
    onSuccess: ({ result, sinceRunId }) => {
      setRunWatch({
        jobId: OCR_MODEL_SYNC_JOB_ID,
        jobName: OCR_MODEL_SYNC_JOB_NAME,
        sinceRunId,
        acceptedAt: Date.now(),
        acceptedMessage: result.message || "已提交执行",
      });
    },
    onError: (e: unknown) => message.error(apiError(e, "检查更新失败")),
  });

  const paddleOptions = useMemo(
    () => groupOcrProfileOptions(data?.paddle_profiles),
    [data?.paddle_profiles],
  );
  const engineMeta = data?.engine_meta?.length
    ? data.engine_meta
    : [
        {
          id: "paddle",
          label: "熊猫 OCR",
          hint: "",
          has_profiles: true,
        },
        {
          id: "easyocr",
          label: "EasyOCR",
          hint: "",
          has_profiles: false,
        },
      ];
  const labels = data?.engine_labels || {};
  const useCaseLabels = Object.fromEntries(
    (data?.use_case_meta || []).map((row) => [row.id, row.label]),
  );
  const statusById = Object.fromEntries(
    (data?.engine_status || []).map((row) => [row.id, row]),
  );
  const easyocrProfiles = data?.easyocr_profiles?.length
    ? data.easyocr_profiles
    : [{ id: "ch_sim_en", label: "ch_sim+en" }];
  const cardStyle = {
    height: "100%",
    marginBottom: 16,
    borderColor: token.colorBorderSecondary,
    background: token.colorFillAlter,
  } as const;
  const profileDirty =
    Boolean(paddleWatch) &&
    Boolean(data?.paddle_profile) &&
    paddleWatch !== data?.paddle_profile;

  const submit = (values: FormValues) => {
    const blocked = crossCheckSaveError({
      engines: values.engines,
      useCases: values.use_cases,
      labels: useCaseLabels,
    });
    if (blocked) {
      message.warning(blocked);
      return;
    }
    requestAdminStepUp(user, {
      onBlocked: () => message.warning(ADMIN_STEP_UP_BLOCKED),
      onNeedCode: () => setPending(values),
      onSkip: () => save.mutate({ payload: values, code: "" }),
    });
  };

  return (
    <div>
      <PageHeader title="文字识别" />
      <Form
        form={form}
        layout="vertical"
        disabled={isLoading}
        onFinish={submit}
      >
        <Typography.Title level={5} style={{ marginTop: 0 }}>
          模型配置
        </Typography.Title>
        <Row gutter={16}>
          {engineMeta.map((meta) => {
            const status = statusById[meta.id];
            const isPaddle = meta.id === "paddle";
            return (
              <Col key={meta.id} xs={24} md={12}>
                <Card
                  size="small"
                  style={{
                    ...cardStyle,
                    display: "flex",
                    flexDirection: "column",
                  }}
                  styles={{
                    body: {
                      display: "flex",
                      flexDirection: "column",
                      flex: 1,
                    },
                  }}
                  title={meta.label}
                  extra={
                    <Form.Item
                      name={["engines", meta.id]}
                      valuePropName="checked"
                      noStyle
                    >
                      <Switch
                        checkedChildren="启用"
                        unCheckedChildren="关闭"
                      />
                    </Form.Item>
                  }
                >
                  {isPaddle ? (
                    <Form.Item
                      name="paddle_profile"
                      label="当前型号"
                      rules={[{ required: true, message: "请选择档位" }]}
                    >
                      <Select
                        showSearch
                        optionFilterProp="label"
                        options={paddleOptions}
                      />
                    </Form.Item>
                  ) : (
                    <Form.Item label="当前型号">
                      <Select
                        disabled
                        value={easyocrProfiles[0]?.id}
                        options={easyocrProfiles.map((row) => ({
                          value: row.id,
                          label: row.label,
                        }))}
                      />
                    </Form.Item>
                  )}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-end",
                      gap: 8,
                      marginTop: "auto",
                    }}
                  >
                    <Space wrap size={8}>
                      <Tag color={status?.installed ? "success" : "default"}>
                        {status?.installed ? "已安装" : "未安装"}
                      </Tag>
                      <Tag color={status?.models_ready ? "success" : "warning"}>
                        {status?.models_ready ? "权重就绪" : "权重未就绪"}
                      </Tag>
                    </Space>
                    <Space size={8} wrap style={{ justifyContent: "flex-end" }}>
                      {isPaddle && profileDirty ? (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          请先保存档位
                        </Typography.Text>
                      ) : null}
                      <Button
                        size="small"
                        htmlType="button"
                        loading={checkUpdates.isPending}
                        disabled={isPaddle && profileDirty}
                        onClick={() => checkUpdates.mutate()}
                      >
                        检查更新
                      </Button>
                    </Space>
                  </div>
                </Card>
              </Col>
            );
          })}
        </Row>

        <Typography.Title level={5}>业务配置</Typography.Title>
        {(data?.use_case_meta || []).map((meta) => (
          <Card
            key={meta.id}
            size="small"
            style={cardStyle}
            title={meta.label}
            extra={
              <Space size={8}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  多端校验
                </Typography.Text>
                <Form.Item
                  name={["use_cases", meta.id, "cross_check"]}
                  valuePropName="checked"
                  noStyle
                >
                  <Switch />
                </Form.Item>
              </Space>
            }
          >
            <Form.Item
              name={["use_cases", meta.id, "engines"]}
              style={{ marginBottom: 0 }}
            >
              <Checkbox.Group
                options={engineMeta.map((engine) => ({
                  value: engine.id,
                  label: labels[engine.id] || engine.label,
                  disabled: enginesWatch?.[engine.id] === false,
                }))}
              />
            </Form.Item>
          </Card>
        ))}

        <Button type="primary" htmlType="submit" loading={save.isPending}>
          保存
        </Button>
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
      <JobRunResultModal watch={runWatch} onClose={() => setRunWatch(null)} />
    </div>
  );
}
