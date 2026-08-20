import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  applyMinecraftProfile,
  fetchMinecraftGameVersions,
  fetchMinecraftLoaderVersions,
  fetchMinecraftModUpdates,
  fetchMinecraftModVersions,
  fetchMinecraftProfile,
  fetchMinecraftStatus,
  searchMinecraftMods,
  updateMinecraftProfile,
  type MinecraftModPin,
  type MinecraftOverride,
  type MinecraftPlaybook,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { isServerLive, LOADERS, PROPERTY_FIELDS } from "./minecraftUi";

type FormValues = {
  public_host: string;
  public_port: number;
  mc_version: string;
  loader: string;
  loader_version: string;
  properties: Record<string, string>;
};

function toForm(profile: MinecraftPlaybook): FormValues {
  return {
    public_host: profile.public_host || "",
    public_port: profile.public_port || 25565,
    mc_version: profile.mc_version,
    loader: profile.loader,
    loader_version: profile.loader_version || "",
    properties: { ...(profile.properties || {}) },
  };
}

export function MinecraftAdminPanel() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const loader = Form.useWatch("loader", form);
  const mcVersion = Form.useWatch("mc_version", form);
  const [mods, setMods] = useState<MinecraftModPin[]>([]);
  const [overrides, setOverrides] = useState<MinecraftOverride[]>([]);
  const [modQuery, setModQuery] = useState("");

  const profileQuery = useQuery({
    queryKey: ["minecraft-profile"],
    queryFn: fetchMinecraftProfile,
  });

  const statusQuery = useQuery({
    queryKey: ["minecraft-status"],
    queryFn: fetchMinecraftStatus,
    refetchInterval: 10_000,
    retry: 1,
  });

  const pelicanConfigured = Boolean(profileQuery.data?.pelican_configured);
  const dirty = Boolean(profileQuery.data?.playbook_dirty);
  const live = isServerLive(statusQuery.data?.power_state);

  const versionsQuery = useQuery({
    queryKey: ["minecraft-game-versions"],
    queryFn: fetchMinecraftGameVersions,
    enabled: pelicanConfigured,
    staleTime: 60 * 60_000,
  });

  const loaderQuery = useQuery({
    queryKey: ["minecraft-loader-versions", loader, mcVersion],
    queryFn: () => fetchMinecraftLoaderVersions(loader, mcVersion || ""),
    enabled: pelicanConfigured && Boolean(loader),
    staleTime: 10 * 60_000,
  });

  const searchQuery = useQuery({
    queryKey: ["minecraft-mod-search", modQuery, loader, mcVersion],
    queryFn: () =>
      searchMinecraftMods({
        q: modQuery,
        loader: loader || "fabric",
        mcVersion: mcVersion || "",
      }),
    enabled: pelicanConfigured && modQuery.trim().length >= 2,
  });

  useEffect(() => {
    const profile = profileQuery.data;
    if (!profile) return;
    form.setFieldsValue(toForm(profile));
    setMods(profile.mods || []);
    setOverrides(profile.overrides || []);
  }, [profileQuery.data, form]);

  const payloadFromForm = (values: FormValues) => {
    const properties: Record<string, string> = {};
    for (const [key, value] of Object.entries(values.properties || {})) {
      if (String(value ?? "").trim() !== "") properties[key] = String(value);
    }
    return {
      mc_version: values.mc_version,
      loader: values.loader,
      loader_version: values.loader_version || "",
      mods,
      properties,
      overrides: overrides.filter((row) => row.path.trim()),
      public_host: values.public_host || "",
      public_port: values.public_port || 25565,
    };
  };

  const save = useMutation({
    mutationFn: async () => {
      const values = await form.validateFields();
      return updateMinecraftProfile(payloadFromForm(values));
    },
    onSuccess: (profile) => {
      message.success("开服配置已保存，尚未写入服务器");
      queryClient.setQueryData(["minecraft-profile"], profile);
      queryClient.invalidateQueries({ queryKey: ["minecraft-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const apply = useMutation({
    mutationFn: async () => {
      const values = await form.validateFields();
      await updateMinecraftProfile(payloadFromForm(values));
      return applyMinecraftProfile();
    },
    onSuccess: (res) => {
      message.success(res.message || "已应用并请求启动");
      queryClient.invalidateQueries({ queryKey: ["minecraft-profile"] });
      queryClient.invalidateQueries({ queryKey: ["minecraft-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "应用失败")),
  });

  const confirmApply = () => {
    Modal.confirm({
      title: "应用开服配置",
      content: live
        ? "当前服正在运行。应用会先停服，再按这份配置启动，在线玩家会断开。"
        : "会把开服配置写入 Pelican 并启动。正在跑的服不会被这份草稿影响，直到你点应用。",
      okText: live ? "停服并应用" : "应用并开服",
      okButtonProps: {
        style: { background: "#1a2332", borderColor: "#1a2332" },
      },
      onOk: () => apply.mutateAsync(),
    });
  };

  const restoreApplied = () => {
    const applied = profileQuery.data?.applied;
    if (!applied) {
      message.warning("还没有已应用的服内快照");
      return;
    }
    form.setFieldsValue(toForm(applied));
    setMods(applied.mods || []);
    setOverrides(applied.overrides || []);
    message.success("已恢复为当前服内配置，保存后才会写回草稿");
  };

  const checkUpdates = useMutation({
    mutationFn: fetchMinecraftModUpdates,
    onSuccess: (rows) => {
      if (!rows.length) {
        message.success("模组都已是当前版本钉死的版本");
        return;
      }
      setMods((prev) => {
        const next = [...prev];
        for (const row of rows) {
          const idx = next.findIndex(
            (m) => m.project_id === row.current.project_id,
          );
          if (idx >= 0) next[idx] = row.latest;
        }
        return next;
      });
      message.success(`已换上 ${rows.length} 个新版本，请保存或应用`);
    },
    onError: (e: unknown) => message.error(apiError(e, "检查更新失败")),
  });

  const addMod = async (projectId: string) => {
    try {
      const versions = await fetchMinecraftModVersions({
        projectId,
        loader: loader || "fabric",
        mcVersion: mcVersion || "",
      });
      const pin = versions[0];
      if (!pin) {
        message.warning("没有适配当前版本/加载器的服务端文件");
        return;
      }
      setMods((prev) => {
        if (prev.some((m) => m.project_id === pin.project_id)) {
          return prev.map((m) =>
            m.project_id === pin.project_id ? pin : m,
          );
        }
        return [...prev, pin];
      });
      message.success(`已加入 ${pin.project_title || pin.filename}`);
    } catch (e: unknown) {
      message.error(apiError(e, "添加模组失败"));
    }
  };

  const versionOptions = useMemo(() => {
    const rows = versionsQuery.data || [];
    return rows.map((row) => ({
      value: row.version,
      label: row.stable ? row.version : `${row.version}（快照）`,
    }));
  }, [versionsQuery.data]);

  const loaderOptions = (loaderQuery.data || []).map((v) => ({
    value: v,
    label: v,
  }));

  if (profileQuery.isLoading) {
    return (
      <Card title="开服">
        <Typography.Text type="secondary">加载中…</Typography.Text>
      </Card>
    );
  }

  if (!pelicanConfigured) {
    return (
      <Card title="开服">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="尚未连接 Pelican"
          description="填好 Panel 地址、Client Token 和这台服的 UUID 之后，才能在这里改下次开服要用的版本和模组。游戏进程仍在 Pelican 里，战鸽只作为操作入口。"
        />
        <Link to="/settings/integrations">
          <Button
            type="primary"
            size="large"
            style={{ background: "#1a2332", borderColor: "#1a2332" }}
          >
            去集成密钥配置
          </Button>
        </Link>
      </Card>
    );
  }

  return (
    <Card
      title={
        <Space>
          开服
          {!profileQuery.data?.applied ? (
            <Tag>尚未应用</Tag>
          ) : dirty ? (
            <Tag color="gold">有未进服的改动</Tag>
          ) : (
            <Tag>与当前服一致</Tag>
          )}
        </Space>
      }
      extra={
        <Space wrap>
          <Button
            onClick={restoreApplied}
            disabled={!profileQuery.data?.applied}
          >
            恢复为当前服
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending}>
            保存草稿
          </Button>
          <Button
            type="primary"
            onClick={confirmApply}
            loading={apply.isPending}
            style={{ background: "#1a2332", borderColor: "#1a2332" }}
          >
            应用并开服
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="这里改的是下次开服才生效的配置，不会改正在跑的进程。"
        description="「保存草稿」只记在战鸽；「应用并开服」才会写入 Pelican 并对齐模组/配置。公开地址保存后立刻用于页面探测，不必等重启。RCON 在集成密钥里配置，不写进开服剧本。"
      />

      {profileQuery.data?.last_apply_message ? (
        <Typography.Paragraph type="secondary">
          上次应用：{profileQuery.data.last_apply_message}
        </Typography.Paragraph>
      ) : null}

      <Collapse
        style={{ marginBottom: 16 }}
        items={[
          {
            key: "boot",
            label: "首次接入：Egg 启动命令",
            children: (
              <div>
                <Typography.Paragraph>
                  把 Egg 启动改成包一层 boot 脚本，加载器换档才会在下次启动执行。并在{" "}
                  <Link to="/settings/integrations">集成密钥</Link> 填写 Panel
                  地址、Client Token、Server UUID，以及 RCON。
                </Typography.Paragraph>
                {profileQuery.data?.startup_hint ? (
                  <Typography.Paragraph copyable>
                    {profileQuery.data.startup_hint}
                  </Typography.Paragraph>
                ) : null}
              </div>
            ),
          },
        ]}
      />

      <Form form={form} layout="vertical">
        <Space size="large" wrap style={{ width: "100%" }}>
          <Form.Item
            name="public_host"
            label="公开地址"
            extra="朋友用来连接的主机名，保存后立刻用于探测"
          >
            <Input placeholder="mc.example.com" style={{ width: 260 }} />
          </Form.Item>
          <Form.Item name="public_port" label="端口">
            <InputNumber min={1} max={65535} style={{ width: 120 }} />
          </Form.Item>
        </Space>

        <Space size="large" wrap style={{ width: "100%" }}>
          <Form.Item
            name="mc_version"
            label="游戏版本"
            rules={[{ required: true, message: "请选择版本" }]}
          >
            <Select
              showSearch
              style={{ width: 200 }}
              options={versionOptions}
              loading={versionsQuery.isFetching}
              placeholder="1.21.1"
            />
          </Form.Item>
          <Form.Item
            name="loader"
            label="加载器"
            rules={[{ required: true }]}
          >
            <Select style={{ width: 160 }} options={LOADERS} />
          </Form.Item>
          <Form.Item
            name="loader_version"
            label="核心（加载器版本）"
            extra="留空则保存时钉死当时最新"
          >
            <Select
              showSearch
              allowClear
              style={{ width: 240 }}
              options={loaderOptions}
              loading={loaderQuery.isFetching}
              placeholder="latest → 保存时钉死"
            />
          </Form.Item>
        </Space>

        <Typography.Title level={5}>模组</Typography.Title>
        <Space style={{ marginBottom: 12 }} wrap>
          <Input.Search
            placeholder="在 Modrinth 搜索"
            allowClear
            enterButton="搜索"
            style={{ width: 320 }}
            onSearch={(v) => setModQuery(v.trim())}
          />
          <Button
            onClick={() => checkUpdates.mutate()}
            loading={checkUpdates.isPending}
          >
            检查更新
          </Button>
        </Space>
        {searchQuery.data?.length ? (
          <Table
            size="small"
            pagination={false}
            rowKey="project_id"
            style={{ marginBottom: 12 }}
            dataSource={searchQuery.data}
            columns={[
              { title: "模组", dataIndex: "title" },
              {
                title: "说明",
                dataIndex: "description",
                ellipsis: true,
              },
              {
                title: "",
                width: 80,
                render: (_, row) => (
                  <Button
                    type="link"
                    size="small"
                    onClick={() => addMod(row.project_id)}
                  >
                    添加
                  </Button>
                ),
              },
            ]}
          />
        ) : null}
        <Table
          size="small"
          pagination={false}
          rowKey={(row) => row.project_id || row.filename}
          dataSource={mods}
          columns={[
            {
              title: "模组",
              dataIndex: "project_title",
              render: (v: string, row) => v || row.filename,
            },
            { title: "版本", dataIndex: "version_number", width: 140 },
            { title: "文件", dataIndex: "filename", ellipsis: true },
            {
              title: "",
              width: 80,
              render: (_, row) => (
                <Button
                  type="link"
                  danger
                  size="small"
                  onClick={() =>
                    setMods((prev) =>
                      prev.filter((m) => m.project_id !== row.project_id),
                    )
                  }
                >
                  移除
                </Button>
              ),
            },
          ]}
        />

        <Typography.Title level={5} style={{ marginTop: 24 }}>
          server.properties
        </Typography.Title>
        {PROPERTY_FIELDS.map((field) => (
          <Form.Item
            key={field.key}
            label={field.label}
            name={["properties", field.key]}
            style={{ marginBottom: 8 }}
          >
            <Input placeholder="保持档案为空则不覆盖该键" />
          </Form.Item>
        ))}

        <Typography.Title level={5} style={{ marginTop: 24 }}>
          其它配置覆盖
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          相对服根路径，例如 config/sodium-extra.properties。应用时写入
          server-overrides，开服 boot 会对齐。
        </Typography.Paragraph>
        {overrides.map((row, index) => (
          <Space
            key={`${row.path}-${index}`}
            align="start"
            style={{ display: "flex", marginBottom: 8, width: "100%" }}
          >
            <Input
              placeholder="config/foo.toml"
              value={row.path}
              style={{ width: 260 }}
              onChange={(e) => {
                const path = e.target.value;
                setOverrides((prev) =>
                  prev.map((item, i) =>
                    i === index ? { ...item, path } : item,
                  ),
                );
              }}
            />
            <Input.TextArea
              placeholder="文件内容"
              value={row.content}
              rows={3}
              style={{ width: 420 }}
              onChange={(e) => {
                const content = e.target.value;
                setOverrides((prev) =>
                  prev.map((item, i) =>
                    i === index ? { ...item, content } : item,
                  ),
                );
              }}
            />
            <Button
              onClick={() =>
                setOverrides((prev) => prev.filter((_, i) => i !== index))
              }
            >
              删除
            </Button>
          </Space>
        ))}
        <Button
          onClick={() =>
            setOverrides((prev) => [...prev, { path: "", content: "" }])
          }
        >
          添加覆盖文件
        </Button>
      </Form>
    </Card>
  );
}
