import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Steps,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  applyMinecraftConfig,
  bootstrapMinecraftServer,
  fetchMinecraftEggs,
  fetchMinecraftFileContents,
  fetchMinecraftGameVersions,
  fetchMinecraftLiveConfigs,
  fetchMinecraftLoaderVersions,
  fetchMinecraftModUpdates,
  fetchMinecraftModVersions,
  fetchMinecraftProfile,
  fetchMinecraftStatus,
  searchMinecraftMods,
  syncMinecraftEgg,
  syncMinecraftMods,
  updateMinecraftProfile,
  type MinecraftLiveConfig,
  type MinecraftModPin,
  type MinecraftOverride,
  type MinecraftPlaybook,
  type MinecraftPlaybookStages,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { MinecraftSetupPicker } from "./MinecraftSetupPicker";
import {
  eggOptionLabel,
  eggsForLoader,
  inferEggLoader,
  inferSetupFromPlaybook,
  isServerLive,
  modLoaderOfCore,
  pickSelectedEggId,
  PLAYBOOK_STEPS,
  PROPERTY_FIELDS,
  setupSummary,
  type MinecraftSetupValue,
} from "./minecraftUi";

type FormValues = {
  mc_version: string;
  loader: string;
  loader_version: string;
  properties: Record<string, string>;
};

function toForm(profile: MinecraftPlaybook): FormValues {
  return {
    mc_version: profile.mc_version,
    loader: profile.loader,
    loader_version: profile.loader_version || "latest",
    properties: { ...(profile.properties || {}) },
  };
}

function relPath(path: string) {
  return path.replace(/^\/+/, "");
}

function parsePropertiesText(text: string) {
  const out: Record<string, string> = {};
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const index = trimmed.indexOf("=");
    if (index < 0) continue;
    out[trimmed.slice(0, index).trim()] = trimmed.slice(index + 1);
  }
  return out;
}

function defaultStep(stages?: MinecraftPlaybookStages) {
  if (!stages || stages.bootstrap !== "applied") return 0;
  if (stages.mods !== "applied") return 1;
  return 2;
}

export function MinecraftAdminPanel() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const loader = Form.useWatch("loader", form);
  const mcVersion = Form.useWatch("mc_version", form);
  const [step, setStep] = useState(0);
  const [mods, setMods] = useState<MinecraftModPin[]>([]);
  const [overrides, setOverrides] = useState<MinecraftOverride[]>([]);
  const [modQuery, setModQuery] = useState("");
  const [liveConfigs, setLiveConfigs] = useState<MinecraftLiveConfig[]>([]);
  const [startupCmd, setStartupCmd] = useState("");
  const [selectedEggId, setSelectedEggId] = useState<number | null>(null);
  const [setup, setSetup] = useState<MinecraftSetupValue>({
    mcVersion: "",
    kind: "",
    core: "",
  });
  const [setupDone, setSetupDone] = useState(false);
  const steppedFromProfile = useRef(false);
  const setupFromProfile = useRef(false);

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
  const draftEggId = profileQuery.data?.egg_id || 0;

  const versionsQuery = useQuery({
    queryKey: ["minecraft-game-versions"],
    queryFn: fetchMinecraftGameVersions,
    staleTime: 60 * 60_000,
  });

  const loaderQuery = useQuery({
    queryKey: ["minecraft-loader-versions", loader, mcVersion],
    queryFn: () => fetchMinecraftLoaderVersions(loader, mcVersion || ""),
    enabled: Boolean(loader),
    staleTime: 10 * 60_000,
  });

  const eggsQuery = useQuery({
    queryKey: ["minecraft-eggs", loader],
    queryFn: () => fetchMinecraftEggs(loader || ""),
    staleTime: 60_000,
  });

  const searchQuery = useQuery({
    queryKey: ["minecraft-mod-search", modQuery, loader, mcVersion],
    queryFn: () =>
      searchMinecraftMods({
        q: modQuery,
        loader: loader || "fabric",
        mcVersion: mcVersion || "",
      }),
    enabled: Boolean(loader) && modQuery.trim().length >= 2,
  });

  useEffect(() => {
    const profile = profileQuery.data;
    if (!profile) return;
    form.setFieldsValue(toForm(profile));
    setMods(profile.mods || []);
    setOverrides(profile.overrides || []);
    setSelectedEggId(profile.egg_id || null);
    setStartupCmd(profile.startup || "");
    if (!setupFromProfile.current) {
      setupFromProfile.current = true;
      setSetup(inferSetupFromPlaybook(profile.mc_version, profile.loader));
    }
    if (!steppedFromProfile.current) {
      steppedFromProfile.current = true;
      setStep(defaultStep(profile.stages));
    }
  }, [profileQuery.data, form]);

  const allEggs = eggsQuery.data?.eggs;
  const recommended = eggsQuery.data?.recommended;
  const canWriteEgg = Boolean(eggsQuery.data?.application_configured);
  const eggChoices = useMemo(
    () =>
      eggsForLoader(
        allEggs || [],
        loader || "",
        selectedEggId || draftEggId,
      ),
    [allEggs, loader, selectedEggId, draftEggId],
  );

  useEffect(() => {
    setSelectedEggId((prev) =>
      pickSelectedEggId({
        availableIds: eggChoices.map((row) => row.egg_id),
        currentId: draftEggId,
        recommendedId: recommended?.egg_id,
        prev,
      }),
    );
  }, [eggChoices, draftEggId, recommended?.egg_id]);

  const payloadFromForm = (values: FormValues) => {
    const properties: Record<string, string> = {};
    for (const [key, value] of Object.entries(values.properties || {})) {
      if (String(value ?? "").trim() !== "") properties[key] = String(value);
    }
    return {
      mc_version: values.mc_version,
      loader: values.loader,
      loader_version: values.loader_version || "",
      egg_id: selectedEggId || 0,
      startup: startupCmd,
      mods,
      properties,
      overrides: overrides.filter((row) => row.path.trim()),
    };
  };

  const saveDraft = async () => {
    const values = await form.validateFields();
    return updateMinecraftProfile(payloadFromForm(values));
  };

  const save = useMutation({
    mutationFn: saveDraft,
    onSuccess: (profile) => {
      message.success("草稿已保存");
      queryClient.setQueryData(["minecraft-profile"], profile);
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const afterStage = (res: {
    message?: string | null;
    ready?: boolean;
    ping_online?: boolean;
  }) => {
    if (res.ready) {
      message.success(res.message || "已完成，服已就绪");
    } else {
      message.warning(res.message || "已执行，但尚未探测到就绪，请看总览或控制台");
    }
    queryClient.invalidateQueries({ queryKey: ["minecraft-profile"] });
    queryClient.invalidateQueries({ queryKey: ["minecraft-status"] });
    queryClient.invalidateQueries({ queryKey: ["minecraft-eggs"] });
  };

  const bootstrap = useMutation({
    mutationFn: async () => {
      await saveDraft();
      return bootstrapMinecraftServer({
        startup: startupCmd,
        egg_id: selectedEggId,
      });
    },
    onSuccess: (res) => {
      afterStage(res);
      setStep(1);
    },
    onError: (e: unknown) => message.error(apiError(e, "开服失败")),
  });

  const pushEgg = useMutation({
    mutationFn: async () => {
      await saveDraft();
      return syncMinecraftEgg({
        startup: startupCmd,
        egg_id: selectedEggId,
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["minecraft-eggs", loader], data);
      message.success(data.message || "已写回 Panel");
    },
    onError: (e: unknown) => message.error(apiError(e, "同步 Egg 失败")),
  });

  const syncMods = useMutation({
    mutationFn: async () => {
      await saveDraft();
      return syncMinecraftMods();
    },
    onSuccess: (res) => {
      afterStage(res);
      setStep(2);
    },
    onError: (e: unknown) => message.error(apiError(e, "同步模组失败")),
  });

  const applyConfig = useMutation({
    mutationFn: async () => {
      await saveDraft();
      return applyMinecraftConfig();
    },
    onSuccess: afterStage,
    onError: (e: unknown) => message.error(apiError(e, "写入配置失败")),
  });

  const confirmStage = (
    title: string,
    content: string,
    okText: string,
    run: () => Promise<unknown>,
  ) => {
    Modal.confirm({
      title,
      content,
      okText,
      okButtonProps: {
        style: { background: "#1a2332", borderColor: "#1a2332" },
      },
      onOk: () => run(),
    });
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
      message.success(`已换上 ${rows.length} 个新版本，请保存后再同步`);
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

  const scanConfigs = useMutation({
    mutationFn: fetchMinecraftLiveConfigs,
    onSuccess: (rows) => {
      setLiveConfigs(rows);
      message.success(
        rows.length ? `扫到 ${rows.length} 个配置文件` : "还没有生成配置文件",
      );
    },
    onError: (e: unknown) => message.error(apiError(e, "扫描失败")),
  });

  const loadLiveFile = async (path: string) => {
    const relative = relPath(path);
    try {
      const file = await fetchMinecraftFileContents(path);
      if (relative === "server.properties") {
        const parsed = parsePropertiesText(file.content || "");
        const next: Record<string, string> = {
          ...(form.getFieldValue("properties") || {}),
        };
        for (const field of PROPERTY_FIELDS) {
          if (parsed[field.key] != null) next[field.key] = parsed[field.key];
        }
        form.setFieldValue("properties", next);
        message.success("已载入 server.properties 常用项");
        return;
      }
      setOverrides((prev) => {
        const rest = prev.filter((row) => row.path !== relative);
        return [...rest, { path: relative, content: file.content || "" }];
      });
      message.success(`已载入 ${relative}`);
    } catch (e: unknown) {
      message.error(apiError(e, "读取失败"));
    }
  };

  const applySetup = (next: MinecraftSetupValue, done: boolean) => {
    setSetup(next);
    if (next.mcVersion) form.setFieldValue("mc_version", next.mcVersion);
    const mapped = modLoaderOfCore(next.core);
    if (mapped) {
      form.setFieldValue("loader", mapped);
      if (mapped !== loader) form.setFieldValue("loader_version", "latest");
    }
    setSetupDone(done);
  };

  const loaderOptions = [
    { value: "latest", label: "latest" },
    ...(loaderQuery.data || [])
      .filter((v) => v !== "latest")
      .map((v) => ({
        value: v,
        label: v,
      })),
  ];

  const busy =
    save.isPending ||
    bootstrap.isPending ||
    pushEgg.isPending ||
    syncMods.isPending ||
    applyConfig.isPending;

  if (profileQuery.isLoading) {
    return (
      <Card title="开服">
        <Typography.Text type="secondary">加载中…</Typography.Text>
      </Card>
    );
  }

  const bootWrapped = startupCmd.includes("zhange/boot.sh");
  const eggEmpty = !eggsQuery.isFetching && !(allEggs || []).length;

  const onSelectEgg = (eggId: number) => {
    setSelectedEggId(eggId);
    const egg = (allEggs || []).find((row) => row.egg_id === eggId);
    const inferred = egg ? inferEggLoader(egg) : "";
    if (inferred) form.setFieldValue("loader", inferred);
    if (egg?.startup) setStartupCmd(egg.startup);
  };

  return (
    <Card
      title={
        <Space>
          开服
          <Tag>草稿</Tag>
          {dirty ? <Tag color="gold">有未应用改动</Tag> : null}
        </Space>
      }
      extra={
        <Button onClick={() => save.mutate()} loading={save.isPending}>
          保存草稿
        </Button>
      }
    >
      {profileQuery.data?.last_apply_message ? (
        <Typography.Paragraph type="secondary">
          上次执行：{profileQuery.data.last_apply_message}
        </Typography.Paragraph>
      ) : null}

      <Steps
        current={step}
        onChange={setStep}
        style={{ marginBottom: 24 }}
        items={PLAYBOOK_STEPS.map((item) => ({
          title: item.title,
        }))}
      />

      <Form form={form} layout="vertical">
        <Form.Item
          name="mc_version"
          hidden
          rules={[{ required: true, message: "请选择版本" }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="loader" hidden rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        {step === 0 ? (
          <>
            <MinecraftSetupPicker
              versions={versionsQuery.data || []}
              loading={versionsQuery.isFetching}
              value={setup}
              done={setupDone}
              currentLabel={
                profileQuery.data
                  ? setupSummary(
                      inferSetupFromPlaybook(
                        profileQuery.data.mc_version,
                        profileQuery.data.loader,
                      ),
                    )
                  : ""
              }
              onChange={(next) => applySetup(next, false)}
              onComplete={(next) => applySetup(next, true)}
              onEdit={() => setSetupDone(false)}
              onUseCurrent={() =>
                applySetup(
                  inferSetupFromPlaybook(
                    profileQuery.data?.mc_version || setup.mcVersion,
                    profileQuery.data?.loader || "",
                  ),
                  true,
                )
              }
            />

            {setupDone && setup.kind && setup.kind !== "mod" ? (
              <Alert
                style={{ marginTop: 16, maxWidth: 640 }}
                type="info"
                showIcon
                message={`已记下 ${setupSummary(setup)}`}
                description="纯净端、插件端、混合端的自动安装下一步再接到 Panel Egg。现在先把版本和核心选好。"
              />
            ) : null}

            {setupDone && setup.kind === "mod" ? (
              <>
                <Form.Item
                  label="Egg"
                  required
                  style={{ marginTop: 20 }}
                  validateStatus={eggEmpty ? "warning" : undefined}
                  help={
                    eggEmpty
                      ? eggsQuery.data?.message ||
                        "还没有从 Panel 读到 Egg。请确认 Application API Token 能列出 nests / eggs。"
                      : undefined
                  }
                >
                  <Select
                    showSearch
                    optionFilterProp="label"
                    style={{ width: "100%", maxWidth: 560 }}
                    loading={eggsQuery.isFetching}
                    placeholder="选择 Panel 里的 Egg"
                    value={selectedEggId ?? undefined}
                    options={eggChoices
                      .filter((row) => row.egg_id)
                      .map((row) => ({
                        value: row.egg_id as number,
                        label: eggOptionLabel(row, {
                          recommended: row.egg_id === recommended?.egg_id,
                        }),
                      }))}
                    onChange={onSelectEgg}
                  />
                </Form.Item>
                <Form.Item name="loader_version" label="核心版本">
                  <Select
                    showSearch
                    style={{ width: 240 }}
                    options={loaderOptions}
                    loading={loaderQuery.isFetching}
                    placeholder="latest"
                  />
                </Form.Item>

                <Form.Item label="启动命令">
                  <Input.TextArea
                    rows={3}
                    value={startupCmd}
                    onChange={(e) => setStartupCmd(e.target.value)}
                    placeholder="java -jar {{SERVER_JARFILE}}"
                  />
                </Form.Item>
                {bootWrapped ? (
                  <Tag color="green" style={{ marginBottom: 12 }}>
                    已包 boot.sh
                  </Tag>
                ) : null}

                <Space wrap>
                  <Button
                    onClick={() => pushEgg.mutate()}
                    loading={pushEgg.isPending}
                    disabled={
                      busy || !canWriteEgg || !pelicanConfigured || !selectedEggId
                    }
                  >
                    同步到 Panel
                  </Button>
                  <Button
                    type="primary"
                    loading={bootstrap.isPending}
                    disabled={
                      busy || !canWriteEgg || !pelicanConfigured || !selectedEggId
                    }
                    onClick={() =>
                      confirmStage(
                        "用 Egg 开服",
                        live
                          ? "会先把 Egg 和启动命令写回 Panel，再停服启动。首次安装加载器可能要几分钟。"
                          : "会把 Egg / 启动命令写回 Panel，再启动并等待就绪。首次安装加载器可能要几分钟。",
                        live ? "停服并开服" : "开服并等待就绪",
                        () => bootstrap.mutateAsync(),
                      )
                    }
                    style={{ background: "#1a2332", borderColor: "#1a2332" }}
                  >
                    用 Egg 开服
                  </Button>
                </Space>
              </>
            ) : null}
          </>
        ) : null}

        {step === 1 ? (
          <>
            <Typography.Paragraph type="secondary">
              按当前版本和加载器从 Modrinth
              匹配服务端文件。已在 /mods 里的 jar 会跳过，缺的再下载，然后重启并检查服况。
            </Typography.Paragraph>
            <Space style={{ marginBottom: 12 }} wrap>
              <Input.Search
                placeholder="搜索模组（Modrinth）"
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
              style={{ marginBottom: 16 }}
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
            <Button
              type="primary"
              loading={syncMods.isPending}
              disabled={busy}
              onClick={() =>
                confirmStage(
                  "同步模组",
                  live
                    ? "会停服、补齐缺少的 jar、去掉档案外的模组，再重启并等待就绪。"
                    : "会检查 /mods，下载缺少的文件后启动，并等待就绪。",
                  live ? "停服并同步" : "同步并重启",
                  () => syncMods.mutateAsync(),
                )
              }
              style={{ background: "#1a2332", borderColor: "#1a2332" }}
            >
              同步模组并重启
            </Button>
          </>
        ) : null}

        {step === 2 ? (
          <>
            <Typography.Paragraph type="secondary">
              加载器和模组首启后才会写出默认配置。先扫描服内文件，把要改的载入剧本再编辑；没载入的保持服内默认。
            </Typography.Paragraph>
            <Space style={{ marginBottom: 16 }} wrap>
              <Button
                onClick={() => scanConfigs.mutate()}
                loading={scanConfigs.isPending}
              >
                扫描服内配置
              </Button>
              <Button
                onClick={() => loadLiveFile("/server.properties")}
                disabled={busy}
              >
                载入 server.properties
              </Button>
            </Space>
            {liveConfigs.length ? (
              <Table
                size="small"
                pagination={false}
                rowKey="path"
                style={{ marginBottom: 16 }}
                dataSource={liveConfigs}
                columns={[
                  {
                    title: "文件",
                    dataIndex: "path",
                    render: (path: string, row) => (
                      <Space>
                        {path}
                        <Tag>{row.kind === "server" ? "服务器" : "模组"}</Tag>
                      </Space>
                    ),
                  },
                  {
                    title: "",
                    width: 120,
                    render: (_, row) => (
                      <Button
                        type="link"
                        size="small"
                        onClick={() => loadLiveFile(row.path)}
                      >
                        载入到剧本
                      </Button>
                    ),
                  },
                ]}
              />
            ) : null}

            <Typography.Title level={5}>服务器常用项</Typography.Title>
            {PROPERTY_FIELDS.map((field) => (
              <Form.Item
                key={field.key}
                label={field.label}
                name={["properties", field.key]}
                style={{ marginBottom: 8 }}
              >
                <Input placeholder="空着则不覆盖该键" />
              </Form.Item>
            ))}

            <Typography.Title level={5} style={{ marginTop: 24 }}>
              将写入的配置文件
            </Typography.Title>
            {overrides.length ? (
              <Collapse
                style={{ marginBottom: 16 }}
                items={overrides.map((row, index) => ({
                  key: `${row.path}-${index}`,
                  label: row.path || "未填写路径",
                  extra: (
                    <Button
                      size="small"
                      danger
                      onClick={(e) => {
                        e.stopPropagation();
                        setOverrides((prev) =>
                          prev.filter((_, i) => i !== index),
                        );
                      }}
                    >
                      删除
                    </Button>
                  ),
                  children: (
                    <Space
                      direction="vertical"
                      style={{ width: "100%" }}
                      size={8}
                    >
                      <Input
                        placeholder="config/foo.toml"
                        value={row.path}
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
                        rows={8}
                        onChange={(e) => {
                          const content = e.target.value;
                          setOverrides((prev) =>
                            prev.map((item, i) =>
                              i === index ? { ...item, content } : item,
                            ),
                          );
                        }}
                      />
                    </Space>
                  ),
                }))}
              />
            ) : (
              <Typography.Paragraph type="secondary">
                还没有要覆盖的模组配置。扫描后点「载入到剧本」，会按文件分别编辑。
              </Typography.Paragraph>
            )}
            <Button
              style={{ marginBottom: 16 }}
              onClick={() =>
                setOverrides((prev) => [...prev, { path: "", content: "" }])
              }
            >
              手动添加覆盖文件
            </Button>
            <div>
              <Button
                type="primary"
                loading={applyConfig.isPending}
                disabled={busy}
                onClick={() =>
                  confirmStage(
                    "写入配置",
                    live
                      ? "会停服、写入 server.properties 和已载入的模组配置，再启动并检查服况。"
                      : "会写入配置文件后启动，并等待就绪。",
                    live ? "停服并写入" : "写入并重启",
                    () => applyConfig.mutateAsync(),
                  )
                }
                style={{ background: "#1a2332", borderColor: "#1a2332" }}
              >
                写入配置并重启
              </Button>
            </div>
          </>
        ) : null}
      </Form>
    </Card>
  );
}
