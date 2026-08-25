import { DownOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  applyMinecraftModToolPreset,
  fetchMinecraftFiles,
  fetchMinecraftModToolPreset,
  runMinecraftModToolCommand,
  saveMinecraftModToolPreset,
  type MinecraftModTool,
  type MinecraftModTools,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import {
  applySuggestionLine,
  completeLine,
  parseCommandLine,
  suggestionsForLine,
} from "./minecraftModCommandComplete";
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
  const boxRef = useRef<HTMLDivElement>(null);
  const tree = useMemo(
    () =>
      (tool.command_tree || []).filter((node) => node.show_in_bar !== false),
    [tool.command_tree],
  );
  const [line, setLine] = useState("");
  const [raw, setRaw] = useState("");

  const run = useMutation({
    mutationFn: (payload: {
      command_id: string;
      args: Record<string, string | number>;
    }) => runMinecraftModToolCommand(tool.id, payload),
    onSuccess: (res) => {
      if (res.message) message.success(res.message);
      else message.success("已发送");
      if (res.raw) setRaw(res.raw);
      queryClient.invalidateQueries({ queryKey: ["minecraft-mod-tools"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "指令失败")),
  });

  const hits = useMemo(
    () => suggestionsForLine(line, tree, worlds),
    [line, tree, worlds],
  );
  const options = hits.map((row) => ({
    value: row.line,
    label: row.token,
  }));

  const focusEnd = (next: string) => {
    requestAnimationFrame(() => {
      const el = boxRef.current?.querySelector("input");
      if (!el) return;
      el.focus();
      const at = next.length;
      el.setSelectionRange(at, at);
    });
  };

  const fillLine = (next: string) => {
    setLine(next);
    focusEnd(next);
  };

  const submit = () => {
    if (disabled) return;
    const parsed = parseCommandLine(line, tree);
    if ("error" in parsed) {
      message.error(parsed.error);
      return;
    }
    const node = tree.find((row) => row.id === parsed.commandId);
    const send = () =>
      run.mutate({ command_id: parsed.commandId, args: parsed.args });
    if (node?.confirm) {
      Modal.confirm({
        title: node.confirm,
        okText: "发送",
        cancelText: "返回",
        onOk: send,
      });
      return;
    }
    send();
  };

  if (!tree.length) return null;

  return (
    <>
      <div className={styles.sectionHead}>
        <div className={styles.sectionTitle}>执行指令</div>
        <div className={styles.commandRow} ref={boxRef}>
          <div
            className={styles.commandInputWrap}
            onKeyDown={(event) => {
              if (event.key !== "Tab") return;
              event.preventDefault();
              fillLine(completeLine(line, tree, worlds));
            }}
          >
            <Input
              value={line}
              placeholder="world"
              spellCheck={false}
              autoComplete="off"
              className={styles.commandInput}
              onChange={(event) => {
                setLine(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  const parsed = parseCommandLine(line, tree);
                  if ("error" in parsed && line.trim() && hits.length) {
                    fillLine(applySuggestionLine(hits[0].line, tree));
                    return;
                  }
                  submit();
                }
              }}
            />
            {options.length ? (
              <ul className={styles.commandSuggest} role="listbox">
                {options.map((row) => (
                  <li key={row.value}>
                    <button
                      type="button"
                      className={styles.commandSuggestItem}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        fillLine(applySuggestionLine(row.value, tree));
                      }}
                    >
                      {row.label}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <Button
            type="primary"
            disabled={disabled || run.isPending}
            loading={run.isPending}
            onClick={submit}
          >
            发送
          </Button>
        </div>
      </div>
      {raw ? (
        <details className={styles.logDetails}>
          <summary>上次输出</summary>
          <pre className={styles.log}>{raw}</pre>
        </details>
      ) : null}
    </>
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
          </div>

          {hasCap(tool, "config") && tool.config_directory ? (
            <div className={styles.section}>
              <div className={styles.sectionHead}>
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
            </div>
          ) : null}

          {hasCap(tool, "commands") ? (
            <div className={styles.section}>
              {!data.rcon_configured ? (
                <Alert
                  className={styles.commandAlert}
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
              {data.rcon_configured && !tool.loaded ? (
                <Alert
                  className={styles.commandAlert}
                  type="info"
                  showIcon
                  message="找到了模组文件，但当前命令不可用。通常是服未开、模组还没进进程，或 RCON 没连上。"
                />
              ) : null}
              <CommandBar
                tool={tool}
                worlds={worlds}
                disabled={!canCommand}
              />
            </div>
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
