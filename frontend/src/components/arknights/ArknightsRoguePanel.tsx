import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Drawer,
  Empty,
  Select,
  Segmented,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  Button,
  message,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { fetchArknightsRogue } from "@/api/client";
import { apiError } from "@/lib/apiError";
import type { ArknightsRogue, ArknightsRogueRecord } from "@/api/types";

const TOPIC_FALLBACK = [
  { label: "界园", value: "rogue_5" },
  { label: "萨卡兹", value: "rogue_4" },
  { label: "萨米", value: "rogue_3" },
  { label: "水月", value: "rogue_2" },
  { label: "傀影", value: "rogue_1" },
  { label: "黑流树海", value: "rogue_6" },
];

function formatTs(raw: string) {
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return raw || "—";
  const ms = n > 1e12 ? n : n * 1000;
  try {
    return new Date(ms).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return raw;
  }
}

type Props = {
  enabled?: boolean;
};

export function ArknightsRoguePanel({ enabled = true }: Props) {
  const queryClient = useQueryClient();
  const [uid, setUid] = useState<string | undefined>();
  const [topicId, setTopicId] = useState<string>("rogue_5");
  const [detail, setDetail] = useState<ArknightsRogueRecord | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const query = useQuery({
    queryKey: ["arknights-rogue", uid ?? "", topicId],
    queryFn: () => fetchArknightsRogue(uid, topicId, false),
    enabled,
    retry: false,
  });

  const data = query.data as ArknightsRogue | undefined;

  const topicOptions = useMemo(() => {
    if (data?.topics?.length) {
      return data.topics.map((t) => ({
        label: t.name,
        value: t.topic_id,
      }));
    }
    return TOPIC_FALLBACK;
  }, [data?.topics]);

  const roleOptions = useMemo(() => {
    const roles = data?.roles ?? [];
    return roles.map((r) => ({
      label: `${r.role_name}（${r.channel_name}）`,
      value: r.uid,
    }));
  }, [data?.roles]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchArknightsRogue(uid, topicId, true);
      queryClient.setQueryData(["arknights-rogue", uid ?? "", topicId], next);
      message.success("已刷新肉鸽数据");
    } catch (e) {
      message.error(apiError(e, "刷新失败"));
    } finally {
      setRefreshing(false);
    }
  };

  const columns: ColumnsType<ArknightsRogueRecord> = [
    {
      title: "结束时间",
      dataIndex: "end_ts",
      width: 160,
      render: (v: string) => formatTs(v),
    },
    {
      title: "结局",
      dataIndex: "ending_text",
      ellipsis: true,
      render: (v: string, row) => (
        <Space size={4} wrap>
          <span>{v || "—"}</span>
          {row.success ? <Tag color="success">通关</Tag> : <Tag>未通关</Tag>}
          {row.is_collect ? <Tag color="gold">收藏</Tag> : null}
        </Space>
      ),
    },
    {
      title: "分数",
      dataIndex: "score",
      width: 88,
      align: "right",
    },
    {
      title: "难度",
      width: 100,
      render: (_, row) =>
        row.mode_grade > 0
          ? `${row.mode || "难度"} ${row.mode_grade}`
          : row.mode || "—",
    },
    {
      title: "层/藏品",
      width: 100,
      render: (_, row) => `${row.zone_count}/${row.relic_count}`,
    },
  ];

  if (!enabled) {
    return (
      <Alert type="info" showIcon message="请先绑定森空岛后再查看集成战略" />
    );
  }

  if (query.isLoading) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin />
      </div>
    );
  }

  if (query.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message={apiError(query.error, "加载肉鸽数据失败")}
        action={
          <Button size="small" onClick={() => query.refetch()}>
            重试
          </Button>
        }
      />
    );
  }

  if (!data) {
    return <Empty description="暂无肉鸽数据" />;
  }

  const ov = data.overview;

  return (
    <div>
      <Space wrap style={{ marginBottom: 16, width: "100%" }} size="middle">
        {roleOptions.length > 1 ? (
          <Select
            style={{ minWidth: 200 }}
            value={uid ?? data.uid}
            options={roleOptions}
            onChange={(v) => setUid(v)}
          />
        ) : (
          <Typography.Text type="secondary">
            {data.role_name} · {data.channel_name}
          </Typography.Text>
        )}
        <Segmented
          value={topicId}
          options={topicOptions}
          onChange={(v) => setTopicId(String(v))}
        />
        <Button
          icon={<ReloadOutlined />}
          loading={refreshing}
          onClick={() => void onRefresh()}
        >
          刷新
        </Button>
        {data.synced_at ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            同步于{" "}
            {new Date(data.synced_at).toLocaleString("zh-CN", {
              hour12: false,
            })}
            {data.stale ? "（陈旧）" : ""}
          </Typography.Text>
        ) : null}
      </Space>

      {data.stale ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="上游刷新失败，正在展示上次缓存"
        />
      ) : null}

      <Space wrap size={[16, 8]} style={{ marginBottom: 16 }}>
        <Stat label="当前主题" value={data.topic_name} />
        <Stat
          label="最高难度"
          value={
            ov.clear_difficulty || ov.mode
              ? `${ov.clear_difficulty || ov.mode} ${ov.clear_grade || ov.mode_grade || ""}`.trim()
              : "—"
          }
        />
        <Stat label="分数" value={String(ov.score || "—")} />
        <Stat
          label="勋章"
          value={
            ov.medal_count
              ? `${ov.medal_current}/${ov.medal_count}`
              : String(ov.medal_current || "—")
          }
        />
        <Stat label="投资" value={String(ov.invest || "—")} />
        <Stat label="藏品" value={String(ov.relic || "—")} />
        <Stat label="对局" value={String(ov.game_count || "—")} />
      </Space>

      <Typography.Title level={5} style={{ marginTop: 8 }}>
        近期战绩
      </Typography.Title>
      <Table
        size="small"
        rowKey="record_id"
        columns={columns}
        dataSource={data.records}
        pagination={{ pageSize: 10, hideOnSinglePage: true }}
        locale={{ emptyText: "该主题暂无战绩" }}
        onRow={(row) => ({
          onClick: () => setDetail(row),
          style: { cursor: "pointer" },
        })}
      />

      {data.favour_records?.length ? (
        <>
          <Typography.Title level={5} style={{ marginTop: 24 }}>
            收藏战绩
          </Typography.Title>
          <Table
            size="small"
            rowKey="record_id"
            columns={columns}
            dataSource={data.favour_records}
            pagination={false}
            onRow={(row) => ({
              onClick: () => setDetail(row),
              style: { cursor: "pointer" },
            })}
          />
        </>
      ) : null}

      <Drawer
        title="战绩详情"
        width={420}
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        destroyOnClose
      >
        {detail ? (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <div>
              <Typography.Text type="secondary">结局</Typography.Text>
              <div>{detail.ending_text || "—"}</div>
            </div>
            <div>
              <Typography.Text type="secondary">时间</Typography.Text>
              <div>
                {formatTs(detail.start_ts)} → {formatTs(detail.end_ts)}
              </div>
            </div>
            <Space wrap>
              <Tag>分数 {detail.score}</Tag>
              <Tag>
                {detail.mode} {detail.mode_grade || ""}
              </Tag>
              <Tag>
                层 {detail.zone_count} / 节点 {detail.node_count}
              </Tag>
              <Tag>藏品 {detail.relic_count}</Tag>
              {detail.band_name ? <Tag>{detail.band_name}</Tag> : null}
            </Space>
            {detail.tags?.length ? (
              <div>
                <Typography.Text type="secondary">标签</Typography.Text>
                <div style={{ marginTop: 4 }}>
                  <Space wrap size={4}>
                    {detail.tags.map((t) => (
                      <Tag key={t}>{t}</Tag>
                    ))}
                  </Space>
                </div>
              </div>
            ) : null}
            <div>
              <Typography.Text type="secondary">终局小队</Typography.Text>
              {detail.squad?.length ? (
                <ul style={{ paddingLeft: 18, margin: "8px 0 0" }}>
                  {detail.squad.map((c) => (
                    <li key={c.char_id}>
                      {c.name} · 精{c.evolve_phase} Lv.{c.level}
                      {c.rarity ? ` · ${c.rarity}★` : ""}
                    </li>
                  ))}
                </ul>
              ) : (
                <div>—</div>
              )}
            </div>
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ minWidth: 72 }}>
      <div style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>{label}</div>
      <div style={{ fontWeight: 600 }}>{value}</div>
    </div>
  );
}
