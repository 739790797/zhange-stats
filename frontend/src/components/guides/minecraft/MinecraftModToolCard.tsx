import { DownOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Input,
  Modal,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  runMinecraftModToolCommand,
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
import { MinecraftModFeatures } from "./MinecraftModFeatures";
import { MinecraftModPresetSection } from "./MinecraftModPresetEditor";
import { MinecraftModToolInstallModal } from "./MinecraftModToolInstallModal";
import { loaderLabel } from "./minecraftUi";
import {
  readModToolExpanded,
  saveModToolExpanded,
} from "./minecraftModToolCollapse";
import styles from "./MinecraftModToolCard.module.css";
import mcmodMark from "@/assets/mcmod-mark.png";
import modrinthMark from "@/assets/modrinth-mark.svg";

function hasCap(tool: MinecraftModTool, cap: string) {
  return (tool.capabilities || []).includes(cap);
}

function ToolLinks({ tool }: { tool: MinecraftModTool }) {
  const links = [
    {
      href: tool.links?.modrinth_url,
      label: "Modrinth",
      logo: <ModrinthLogo />,
    },
    {
      href: tool.links?.curseforge_url,
      label: "CurseForge",
      logo: <CurseForgeLogo />,
    },
    {
      href: tool.links?.mcmod_url,
      label: "MCMOD",
      logo: <McmodLogo />,
    },
  ].filter((row) => row.href);
  if (!links.length) return null;
  return (
    <div className={styles.links}>
      {links.map((row) => (
        <Typography.Link
          key={row.label}
          className={styles.link}
          href={row.href}
          target="_blank"
          rel="noreferrer"
        >
          {row.logo}
          {row.label}
        </Typography.Link>
      ))}
    </div>
  );
}

function ModrinthLogo() {
  return <img className={styles.linkLogo} src={modrinthMark} alt="" />;
}

function CurseForgeLogo() {
  return (
    <svg className={styles.linkLogo} viewBox="0 0 40 40" aria-hidden>
      <rect width="40" height="40" rx="8" fill="#F16436" />
      <path
        fill="#fff"
        d="M29.489 15.285s7.35-1.169 8.511-4.579H26.74V8H2l3.048 3.567v3.655s7.69-.403 10.664 1.872c4.072 3.807-4.58 8.953-4.58 8.953L9.65 31c2.32-2.228 6.741-5.111 14.848-4.972-3.085.984-6.187 2.52-8.602 4.972h16.387l-1.543-4.952s-11.877-7.065-1.25-10.763z"
      />
    </svg>
  );
}

function McmodLogo() {
  return <img className={styles.linkLogo} src={mcmodMark} alt="" />;
}

function CommandBar({
  tool,
  worlds,
  maps,
  disabled,
}: {
  tool: MinecraftModTool;
  worlds: string[];
  maps: string[];
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
    () => suggestionsForLine(line, tree, worlds, maps),
    [line, tree, worlds, maps],
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
              fillLine(completeLine(line, tree, worlds, maps));
            }}
          >
            <Input
              value={line}
              placeholder={tree[0]?.id || "指令"}
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


export function MinecraftModToolCard({
  tool,
  data,
}: {
  tool: MinecraftModTool;
  data: MinecraftModTools;
}) {
  const queryClient = useQueryClient();
  const catalog = tool.catalog;
  const [installMode, setInstallMode] = useState<"install" | "change" | null>(
    null,
  );
  const [expanded, setExpanded] = useState(() =>
    readModToolExpanded(tool.id, Boolean(tool.present)),
  );
  const [expandAnimating, setExpandAnimating] = useState(false);
  const expandTimer = useRef<number>(0);

  const present = Boolean(tool.present);
  const open = present && expanded;

  useEffect(() => {
    setExpanded(readModToolExpanded(tool.id, present));
  }, [tool.id, present]);

  useEffect(
    () => () => {
      window.clearTimeout(expandTimer.current);
    },
    [],
  );

  const toggleExpanded = () => {
    if (!present) return;
    const next = !expanded;
    setExpandAnimating(true);
    setExpanded(next);
    saveModToolExpanded(tool.id, next);
    window.clearTimeout(expandTimer.current);
    expandTimer.current = window.setTimeout(() => {
      setExpandAnimating(false);
    }, 240);
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
      <div
        className={[styles.cardHead, open ? styles.cardHeadOpen : ""]
          .filter(Boolean)
          .join(" ")}
      >
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
            {tool.summary ? (
              <div className={styles.summary}>{tool.summary}</div>
            ) : null}
          </div>
        </div>
        <div className={styles.headRight}>
          {present && open ? <ToolLinks tool={tool} /> : null}
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
      </div>

      {present ? (
        <div
          className={[
            styles.expand,
            open ? styles.expandOpen : "",
            expandAnimating ? styles.expandAnimating : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <div
            className={styles.expandInner}
            aria-hidden={!open}
            {...(!open ? ({ inert: "" } as object) : {})}
          >
            <div className={styles.alerts}>
              {catalog?.message ? (
                <Alert type="warning" showIcon message={catalog.message} />
              ) : null}
            </div>

            {hasCap(tool, "config") ? (
              <div className={styles.section}>
                <MinecraftModPresetSection
                  toolId={tool.id}
                  toolTitle={tool.title}
                  pelicanConfigured={Boolean(data.pelican_configured)}
                  enabled={open}
                />
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
                  maps={data.bluemap?.maps || []}
                  disabled={!canCommand}
                />
              </div>
            ) : null}

            <MinecraftModFeatures
              tool={tool}
              data={data}
              canCommand={canCommand}
            />
          </div>
        </div>
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
