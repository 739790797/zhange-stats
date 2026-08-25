import { DownOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Form,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  applyMinecraftModToolPreset,
  fetchMinecraftFiles,
  fetchMinecraftModToolPreset,
  runMinecraftModToolCommand,
  saveMinecraftModToolPreset,
  type MinecraftModCommandArg,
  type MinecraftModTool,
  type MinecraftModTools,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { MinecraftConfigFilesModal } from "./MinecraftConfigFilesModal";
import { MinecraftChunkyWorkspace } from "./MinecraftChunkyWorkspace";
import { MinecraftModToolInstallModal } from "./MinecraftModToolInstallModal";
import {
  MinecraftPathFileEditor,
  MinecraftTextFileFormModal,
  type MinecraftTextFileEditorValues,
} from "./MinecraftTextFileEditor";
import {
  isMinecraftTextFile,
  joinMinecraftPath,
  loaderLabel,
  normalizeMinecraftPath,
} from "./minecraftUi";
import {
  readModToolExpanded,
  saveModToolExpanded,
} from "./minecraftModToolCollapse";
import styles from "./MinecraftModToolCard.module.css";

function hasCap(tool: MinecraftModTool, cap: string) {
  return (tool.capabilities || []).includes(cap);
}

async function openConfigFiles(
  root: string,
): Promise<{ kind: "edit"; path: string } | { kind: "browse" }> {
  const lockedRoot = normalizeMinecraftPath(root);
  if (!lockedRoot || lockedRoot === "/") return { kind: "browse" };
  try {
    const list = await fetchMinecraftFiles(lockedRoot);
    const files = (list.entries || []).filter((row) => row.is_file);
    const folders = (list.entries || []).filter((row) => !row.is_file);
    if (
      files.length === 1 &&
      folders.length === 0 &&
      isMinecraftTextFile(files[0])
    ) {
      return {
        kind: "edit",
        path: joinMinecraftPath(lockedRoot, files[0].name),
      };
    }
  } catch {
    return { kind: "browse" };
  }
  return { kind: "browse" };
}

function ToolLinks({ tool }: { tool: MinecraftModTool }) {
  const links = [
    { href: tool.links?.modrinth_url, label: "Modrinth" },
    { href: tool.links?.curseforge_url, label: "CurseForge" },
    { href: tool.links?.mcmod_url, label: "MCMOD" },
    { href: tool.links?.wiki_url, label: "Wiki" },
    { href: tool.links?.github_url, label: "GitHub" },
  ].filter((row) => row.href);
  if (!links.length) return null;
  return (
    <div className={styles.links}>
      {links.map((row) => (
        <Typography.Link key={row.label} href={row.href} target="_blank">
          {row.label}
        </Typography.Link>
      ))}
    </div>
  );
}

function CommandBar({
  tool,
  worlds,
  disabled,
}: {
  tool: MinecraftModTool;
  worlds: string[];
  disabled: boolean;
}) {
  const queryClient = useQueryClient();
  const tree = (tool.command_tree || []).filter((node) => node.show_in_bar !== false);
  const [commandId, setCommandId] = useState(tree[0]?.id || "");
  const [args, setArgs] = useState<Record<string, string | number | null>>({});
  const [raw, setRaw] = useState("");
  const node = tree.find((row) => row.id === commandId) || null;

  const run = useMutation({
    mutationFn: () => {
      const cleaned: Record<string, string | number> = {};
      for (const [key, value] of Object.entries(args)) {
        if (value == null || value === "") continue;
        cleaned[key] = value;
      }
      return runMinecraftModToolCommand(tool.id, {
        command_id: commandId,
        args: cleaned,
      });
    },
    onSuccess: (res) => {
      if (res.message) message.success(res.message);
      else message.success("已发送");
      if (res.raw) setRaw(res.raw);
      queryClient.invalidateQueries({ queryKey: ["minecraft-mod-tools"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "指令失败")),
  });

  if (!tree.length) return null;

  const pickCommand = (id: string) => {
    setCommandId(id);
    setArgs({});
  };

  const setArg = (id: string, value: string | number | null) => {
    setArgs((prev) => ({ ...prev, [id]: value }));
  };

  const renderArg = (arg: MinecraftModCommandArg) => {
    if (arg.kind === "enum" || arg.kind === "world") {
      const options =
        arg.kind === "world"
          ? worlds.map((name) => ({ value: name, label: name }))
          : (arg.options || []).map((row) => ({
              value: row.value,
              label: row.label || row.value,
            }));
      return (
        <Select
          allowClear={arg.optional}
          showSearch={arg.kind === "world"}
          placeholder={arg.label}
          value={(args[arg.id] as string | undefined) || undefined}
          onChange={(value) => setArg(arg.id, value ?? null)}
          options={options}
          style={{ minWidth: 140 }}
        />
      );
    }
    if (arg.kind === "int") {
      return (
        <InputNumber
          placeholder={arg.label}
          value={(args[arg.id] as number | null) ?? null}
          min={arg.min_value ?? undefined}
          max={arg.max_value ?? undefined}
          onChange={(value) => setArg(arg.id, value)}
          style={{ width: 120 }}
        />
      );
    }
    return null;
  };

  const send = (
    <Button
      type="primary"
      disabled={disabled || !commandId}
      loading={run.isPending}
      onClick={() => run.mutate()}
    >
      发送
    </Button>
  );

  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>执行指令</div>
      <div className={styles.commandRow}>
        <Select
          value={commandId || undefined}
          placeholder="选择指令"
          onChange={pickCommand}
          options={tree.map((row) => ({ value: row.id, label: row.label }))}
          style={{ minWidth: 160 }}
        />
        {(node?.args || []).map((arg) => (
          <div key={arg.id} className={styles.commandField}>
            <label>{arg.label}</label>
            {renderArg(arg)}
          </div>
        ))}
        {node?.confirm ? (
          <Popconfirm
            title={node.confirm}
            okText="发送"
            cancelText="返回"
            disabled={disabled || !commandId}
            onConfirm={() => run.mutate()}
          >
            <Button type="primary" disabled={disabled || !commandId} loading={run.isPending}>
              发送
            </Button>
          </Popconfirm>
        ) : (
          send
        )}
      </div>
      {raw ? (
        <details className={styles.logDetails}>
          <summary>上次输出</summary>
          <pre className={styles.log}>{raw}</pre>
        </details>
      ) : null}
    </div>
  );
}

function PresetEditor({
  toolId,
  presetId,
  title,
  open,
  onClose,
}: {
  toolId: string;
  presetId: string;
  title: string;
  open: boolean;
  onClose: () => void;
}) {
  const [form] = Form.useForm<MinecraftTextFileEditorValues>();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["minecraft-mod-preset", toolId, presetId],
    queryFn: () => fetchMinecraftModToolPreset(toolId, presetId),
    enabled: open && Boolean(presetId),
  });

  useEffect(() => {
    if (!open) {
      form.resetFields();
      return;
    }
    if (query.data) {
      form.setFieldsValue({
        name: query.data.filename,
        content: query.data.content,
      });
    }
  }, [open, query.data, form]);

  useEffect(() => {
    if (open && query.isError) {
      message.error(apiError(query.error, "无法读取预设"));
    }
  }, [open, query.isError, query.error]);

  const save = useMutation({
    mutationFn: async () => {
      const values = await form.validateFields();
      return saveMinecraftModToolPreset(toolId, presetId, {
        content: values.content,
        restore: false,
      });
    },
    onSuccess: (res) => {
      form.setFieldsValue({ name: res.filename, content: res.content });
      void queryClient.invalidateQueries({
        queryKey: ["minecraft-mod-preset", toolId, presetId],
      });
      message.success("已保存草稿，尚未写入服务器");
      onClose();
    },
    onError: (e: unknown) => message.error(apiError(e, "保存草稿失败")),
  });
  const restore = useMutation({
    mutationFn: () =>
      saveMinecraftModToolPreset(toolId, presetId, { restore: true }),
    onSuccess: (res) => {
      form.setFieldsValue({ name: res.filename, content: res.content });
      void queryClient.invalidateQueries({
        queryKey: ["minecraft-mod-preset", toolId, presetId],
      });
      message.success("已恢复出厂模板");
    },
    onError: (e: unknown) => message.error(apiError(e, "恢复出厂失败")),
  });

  const source = query.data?.source === "draft" ? "草稿" : "出厂";
  return (
    <MinecraftTextFileFormModal
      open={open}
      title={`编辑预设 · ${title}（${source}）`}
      nameDisabled
      confirmLoading={save.isPending || query.isFetching}
      form={form}
      extra={
        <Button
          onClick={() => restore.mutate()}
          loading={restore.isPending}
          disabled={save.isPending}
        >
          恢复出厂
        </Button>
      }
      onCancel={onClose}
      onOk={() => save.mutate()}
    />
  );
}

export function MinecraftModToolCard({
  tool,
  data,
}: {
  tool: MinecraftModTool;
  data: MinecraftModTools;
}) {
  const queryClient = useQueryClient();
  const catalog = tool.catalog;
  const [browseOpen, setBrowseOpen] = useState(false);
  const [editorPath, setEditorPath] = useState<string | null>(null);
  const presets = tool.presets || [];
  const [activePresetId, setActivePresetId] = useState(presets[0]?.id || "");
  const [presetEditorOpen, setPresetEditorOpen] = useState(false);
  const [installMode, setInstallMode] = useState<"install" | "change" | null>(
    null,
  );
  const [expanded, setExpanded] = useState(() =>
    readModToolExpanded(tool.id, Boolean(tool.present)),
  );
  const activePreset =
    presets.find((row) => row.id === activePresetId) || presets[0] || null;

  const preset = useMutation({
    mutationFn: (presetId: string) =>
      applyMinecraftModToolPreset(tool.id, presetId),
    onSuccess: (res) => {
      message.success(res.message);
      queryClient.invalidateQueries({ queryKey: ["minecraft-mod-tools"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "写入配置失败")),
  });

  const busy = preset.isPending;
  const present = Boolean(tool.present);
  const open = present && expanded;

  useEffect(() => {
    setExpanded(readModToolExpanded(tool.id, present));
  }, [tool.id, present]);

  const toggleExpanded = () => {
    if (!present) return;
    const next = !expanded;
    setExpanded(next);
    saveModToolExpanded(tool.id, next);
  };

  const canCommand = Boolean(present && tool.loaded && data.rcon_configured);
  const loaderTag = catalog?.loader ? (
    <Tag>{loaderLabel(catalog.loader)}</Tag>
  ) : null;
  const versionTag = (
    <Tag color={present && catalog?.installed_version ? "blue" : undefined}>
      {catalog?.installed_version || (present ? "已装" : "未安装")}
    </Tag>
  );
  const worlds = useMemo(() => {
    const extra = [
      "minecraft:overworld",
      "minecraft:the_nether",
      "minecraft:the_end",
    ];
    return [...new Set([...(data.worlds || []), ...extra].filter(Boolean))];
  }, [data.worlds]);

  const openConfig = async () => {
    const root = tool.config_directory || "";
    if (!root) {
      message.error("该模组未声明配置目录");
      return;
    }
    const next = await openConfigFiles(root);
    if (next.kind === "edit") setEditorPath(next.path);
    else setBrowseOpen(true);
  };

  return (
    <Card
      className={[
        styles.card,
        !open ? styles.cardCollapsed : "",
        !present ? styles.cardAbsent : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className={styles.cardHead}>
        <div
          className={styles.toggle}
          role={present ? "button" : undefined}
          tabIndex={present ? 0 : -1}
          aria-expanded={present ? open : undefined}
          aria-disabled={!present}
          title={present ? (open ? "收起" : "展开") : "未安装，无法展开"}
          onClick={toggleExpanded}
          onKeyDown={(event) => {
            if (!present) return;
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              toggleExpanded();
            }
          }}
        >
          <DownOutlined
            className={[
              styles.chevron,
              open ? "" : styles.chevronClosed,
              present ? "" : styles.chevronMuted,
            ]
              .filter(Boolean)
              .join(" ")}
          />
          <div className={styles.titleBlock}>
            <div className={styles.titleRow}>
              {tool.icon_url ? (
                <img className={styles.icon} src={tool.icon_url} alt="" />
              ) : null}
              <Typography.Title level={4} style={{ margin: 0 }}>
                {tool.title}
              </Typography.Title>
              {loaderTag}
              {versionTag}
            </div>
            <div className={styles.summary}>{tool.summary}</div>
          </div>
        </div>
        <div className={styles.headActions}>
          {!present && data.pelican_configured && hasCap(tool, "install") ? (
            <Button
              size="small"
              type="primary"
              onClick={() => setInstallMode("install")}
            >
              安装模组
            </Button>
          ) : null}
          {present && data.pelican_configured && hasCap(tool, "install") ? (
            <Button size="small" onClick={() => setInstallMode("change")}>
              修改版本
            </Button>
          ) : null}
        </div>
      </div>

      {open ? (
        <>
          <ToolLinks tool={tool} />
          <div className={styles.alerts}>
            {catalog?.message ? (
              <Alert type="warning" showIcon message={catalog.message} />
            ) : null}

            {!data.rcon_configured && hasCap(tool, "commands") ? (
              <Alert
                type="warning"
                showIcon
                message={
                  <span>
                    尚未配置 RCON，无法发送指令。{" "}
                    <Link to="/settings/integrations">去集成密钥</Link>
                  </span>
                }
              />
            ) : null}

            {data.rcon_configured && !tool.loaded && hasCap(tool, "commands") ? (
              <Alert
                type="info"
                showIcon
                message="找到了模组文件，但当前命令不可用。通常是服未开、模组还没进进程，或 RCON 没连上。"
              />
            ) : null}
          </div>

          {hasCap(tool, "config") && tool.config_directory ? (
            <div className={styles.section}>
              <div className={styles.sectionTitle}>配置文件</div>
              <Space wrap>
                <Button
                  disabled={!data.pelican_configured}
                  onClick={() => void openConfig()}
                >
                  编辑配置
                </Button>
                {presets.length > 1 ? (
                  <Select
                    value={activePreset?.id}
                    onChange={setActivePresetId}
                    options={presets.map((row) => ({
                      value: row.id,
                      label: row.title,
                    }))}
                    style={{ minWidth: 140 }}
                  />
                ) : null}
                {activePreset ? (
                  <>
                    <Button
                      disabled={busy}
                      onClick={() => setPresetEditorOpen(true)}
                    >
                      编辑预设
                    </Button>
                    <Popconfirm
                      title={`写入「${activePreset.title}」会覆盖服上主配置文件`}
                      description="不会改 tasks 等运行时目录。没有草稿时用出厂模板。"
                      okText="写入"
                      cancelText="返回"
                      disabled={!data.pelican_configured || busy}
                      onConfirm={() => preset.mutate(activePreset.id)}
                    >
                      <Button
                        loading={preset.isPending}
                        disabled={!data.pelican_configured || busy}
                      >
                        写入预设
                      </Button>
                    </Popconfirm>
                  </>
                ) : null}
              </Space>
            </div>
          ) : null}

          {hasCap(tool, "commands") ? (
            <CommandBar tool={tool} worlds={worlds} disabled={!canCommand} />
          ) : null}

          {tool.id === "chunky" ? (
            <div className={styles.section}>
              <MinecraftChunkyWorkspace data={data} canCommand={canCommand} />
            </div>
          ) : null}
        </>
      ) : null}

      <MinecraftConfigFilesModal
        open={browseOpen}
        root={tool.config_directory || "/"}
        title={`${tool.title} 配置`}
        onClose={() => setBrowseOpen(false)}
      />
      <MinecraftPathFileEditor
        path={editorPath}
        onClose={() => setEditorPath(null)}
      />
      {activePreset ? (
        <PresetEditor
          toolId={tool.id}
          presetId={activePreset.id}
          title={activePreset.title}
          open={presetEditorOpen}
          onClose={() => setPresetEditorOpen(false)}
        />
      ) : null}
      <MinecraftModToolInstallModal
        tool={tool}
        mode={installMode}
        onClose={() => setInstallMode(null)}
        onDone={() => {
          saveModToolExpanded(tool.id, true);
          setExpanded(true);
          void queryClient.invalidateQueries({
            queryKey: ["minecraft-mod-tools"],
          });
        }}
      />
    </Card>
  );
}
