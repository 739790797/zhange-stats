import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  message,
} from "antd";
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";
import { createRecord, fetchGames, fetchMembers } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

export default function RecordCreatePage() {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: members } = useQuery({
    queryKey: ["members"],
    queryFn: fetchMembers,
  });
  const { data: games } = useQuery({
    queryKey: ["games"],
    queryFn: fetchGames,
  });

  const mutation = useMutation({
    mutationFn: createRecord,
    onSuccess: () => {
      message.success("战绩已录入");
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
      queryClient.invalidateQueries({ queryKey: ["records"] });
      navigate("/");
    },
    onError: () => message.error("录入失败，请检查填写内容"),
  });

  return (
    <div>
      <PageHeader title="战绩录入" subtitle="手动记录一局结果" />
      <Form
        form={form}
        layout="vertical"
        style={{ maxWidth: 560 }}
        initialValues={{
          result: "win",
          played_at: dayjs(),
          source: "manual",
        }}
        onFinish={(values) => {
          const stats: Record<string, number> = {};
          if (values.score != null) stats.score = values.score;
          if (values.kills != null) stats.kills = values.kills;
          if (values.deaths != null) stats.deaths = values.deaths;

          mutation.mutate({
            member_id: values.member_id,
            game_id: values.game_id,
            played_at: values.played_at.toISOString(),
            result: values.result,
            mode: values.mode || null,
            stats: Object.keys(stats).length ? stats : null,
            raw_text: values.raw_text || null,
            source: "manual",
          });
        }}
      >
        <Form.Item
          name="member_id"
          label="成员"
          rules={[{ required: true, message: "请选择成员" }]}
        >
          <Select
            placeholder="选择成员"
            options={(members ?? []).map((m) => ({
              value: m.id,
              label: m.nickname,
            }))}
          />
        </Form.Item>
        <Form.Item
          name="game_id"
          label="游戏"
          rules={[{ required: true, message: "请选择游戏" }]}
        >
          <Select
            placeholder="选择游戏"
            options={(games ?? []).map((g) => ({
              value: g.id,
              label: `${g.name}${g.platform ? ` (${g.platform})` : ""}`,
            }))}
          />
        </Form.Item>
        <Form.Item name="mode" label="模式">
          <Input placeholder="如：排位 / 匹配 / 死亡竞赛" />
        </Form.Item>
        <Form.Item
          name="result"
          label="结果"
          rules={[{ required: true, message: "请选择结果" }]}
        >
          <Select
            options={[
              { value: "win", label: "胜" },
              { value: "lose", label: "负" },
              { value: "draw", label: "平" },
              { value: "unknown", label: "未知" },
            ]}
          />
        </Form.Item>
        <Form.Item
          name="played_at"
          label="对局时间"
          rules={[{ required: true, message: "请选择时间" }]}
        >
          <DatePicker showTime style={{ width: "100%" }} />
        </Form.Item>
        <Space size="large" style={{ display: "flex" }}>
          <Form.Item name="score" label="比分/得分">
            <InputNumber style={{ width: 120 }} />
          </Form.Item>
          <Form.Item name="kills" label="击杀">
            <InputNumber style={{ width: 120 }} min={0} />
          </Form.Item>
          <Form.Item name="deaths" label="死亡">
            <InputNumber style={{ width: 120 }} min={0} />
          </Form.Item>
        </Space>
        <Form.Item name="raw_text" label="原始文本（可选）">
          <Input.TextArea
            rows={4}
            placeholder="可粘贴战绩截图 OCR / 聊天记录等，便于后续解析"
          />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={mutation.isPending}>
          提交战绩
        </Button>
      </Form>
    </div>
  );
}
