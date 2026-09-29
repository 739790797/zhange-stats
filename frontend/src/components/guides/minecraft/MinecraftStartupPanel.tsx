import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Cascader, Input, Select, Typography, message } from "antd";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  fetchMinecraftStartup,
  fetchMinecraftStartupBuilds,
  applyMinecraftStartup,
  type MinecraftStartup,
  type MinecraftStartupIn,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { heapFlagsFromText } from "./minecraftUi";
import liveStyles from "./MinecraftLivePanel.module.css";
import styles from "./MinecraftStartupPanel.module.css";

const LOADER_LABELS: Record<string, string> = {
  neoforge: "NeoForge",
  forge: "Forge",
  fabric: "Fabric",
  quilt: "Quilt",
  paper: "Paper",
  purpur: "Purpur",
  vanilla: "原版",
};

type Draft = MinecraftStartupIn;

function draftFrom(data: MinecraftStartup): Draft {
  return {
    loader: data.loader || "",
    core_id: data.selected_id || "",
    java_image: data.java_image || "",
    jvm_args: data.jvm_args || "",
    user_jvm_args: data.user_jvm_args || "",
    build_channel: data.build_channel || "",
    build_name: data.build_name || "",
  };
}

function imageText(image: string) {
  return image || "未设置";
}

function coreText(data: MinecraftStartup, id: string) {
  if (!id) return "未从启动指令识别";
  return (data.cores ?? []).find((row) => row.id === id)?.label || id;
}

function currentArgsText(data: MinecraftStartup) {
  if (data.current_launch === "args") return data.current_user_jvm_args || "";
  if (data.current_launch === "jar") return data.current_jvm_args || "";
  return data.current_user_jvm_args || data.current_jvm_args || "";
}

function Cell({
  caption,
  children,
}: {
  caption: string;
  children: ReactNode;
}) {
  return (
    <div className={caption === "当前" ? styles.current : styles.edit}>
      <Typography.Text type="secondary" className={styles.caption}>
        {caption}
      </Typography.Text>
      {children}
    </div>
  );
}

export function MinecraftStartupPanel() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["minecraft-startup"],
    queryFn: fetchMinecraftStartup,
    refetchInterval: 15_000,
    retry: 1,
  });
  const [draft, setDraft] = useState<Draft | null>(null);
  const draftRef = useRef<Draft | null>(null);
  draftRef.current = draft;

  useEffect(() => {
    if (!query.data || draftRef.current) return;
    setDraft(draftFrom(query.data));
  }, [query.data]);

  const apply = useMutation({
    mutationFn: applyMinecraftStartup,
    onSuccess: (next) => {
      queryClient.setQueryData(["minecraft-startup"], next);
      message.success("已下载核心并写入启动指令");
    },
  });

  const draftCore = draft?.core_id || "";
  const arclightOnDisk = (query.data?.cores ?? []).find((row) => row.id === "arclight");
  const needsBuilds = draftCore === "arclight" && !arclightOnDisk?.jar;
  const builds = useQuery({
    queryKey: ["minecraft-startup-builds", draftCore],
    queryFn: () => fetchMinecraftStartupBuilds(draftCore),
    enabled: needsBuilds,
    retry: 1,
  });

  useEffect(() => {
    if (!needsBuilds || draft?.build_name || !builds.data) return;
    const stable =
      builds.data.options?.find((row) => row.value === "stable") || builds.data.options?.[0];
    const first = stable?.children?.[0];
    if (!stable || !first) return;
    setDraft((prev) =>
      prev ? { ...prev, build_channel: stable.value, build_name: first.value } : prev,
    );
  }, [builds.data, draft?.build_name, needsBuilds]);

  const data = query.data;

  if (query.isError) {
    return (
      <Alert type="error" showIcon message={apiError(query.error, "无法读取启动项")} />
    );
  }
  if (!data || !draft) {
    return <Typography.Text type="secondary">正在读取启动项…</Typography.Text>;
  }

  const selected = (data.cores ?? []).find((row) => row.id === draft.core_id);

  const edit = (patch: Partial<Draft>) => {
    setDraft((prev) => ({ ...(prev || draftFrom(data)), ...patch }));
  };

  const changeCore = (coreId: string) => {
    const core = (data.cores ?? []).find((row) => row.id === coreId);
    if (!core) {
      edit({ core_id: coreId, build_channel: "", build_name: "" });
      return;
    }
    if (core.launch === "jar" && selected?.launch === "args") {
      edit({
        core_id: coreId,
        build_channel: "",
        build_name: "",
        jvm_args:
          heapFlagsFromText(draft.user_jvm_args) ||
          draft.jvm_args ||
          data.suggested_heap ||
          "",
      });
      return;
    }
    edit({ core_id: coreId, build_channel: "", build_name: "" });
  };

  const launch = selected?.launch || data.launch;
  const chosenBuild = (builds.data?.options ?? [])
    .flatMap((channel) => channel.children ?? [])
    .find((row) => row.value === draft.build_name);
  const preview = (() => {
    if (!selected) return "";
    if (launch === "args") {
      const path = (selected.unix_args || "").replace(/^\//, "");
      return path ? `java @user_jvm_args.txt @${path} nogui` : "";
    }
    const jar = selected.jar || chosenBuild?.filename || "";
    if (!jar) return "";
    return ["java", (draft.jvm_args || "").trim(), "-jar", jar, selected.server_args]
      .filter(Boolean)
      .join(" ");
  })();
  const aligned = Boolean(preview && preview === (data.current_command || ""));
  const storedArgs = currentArgsText(data);
  const currentArgsFromFile =
    data.current_launch === "args" ||
    (!data.current_launch && Boolean(data.current_user_jvm_args));

  return (
    <Card size="small" title="启动">
      <div className={liveStyles.wrap}>
        <div className={styles.grid}>
          <div className={styles.corner} />
          <Typography.Text type="secondary" className={styles.head}>
            当前
          </Typography.Text>
          <Typography.Text type="secondary" className={styles.head}>
            修改
          </Typography.Text>

          <Typography.Text className={styles.label}>加载器</Typography.Text>
          <Cell caption="当前">
            <div className={styles.currentLine}>{data.loader_label || "未识别"}</div>
          </Cell>
          <Cell caption="修改">
            {data.loader_locked ? (
              <Typography.Text type="secondary" className={styles.currentLine}>
                由服内文件识别
              </Typography.Text>
            ) : (
              <Select
                style={{ width: "100%", maxWidth: 420 }}
                placeholder="先选择加载器"
                value={draft.loader || undefined}
                options={(data.loader_choices ?? []).map((value) => ({
                  value,
                  label: LOADER_LABELS[value] || value,
                }))}
                onChange={(value) => edit({ loader: value, core_id: "" })}
              />
            )}
          </Cell>

          <Typography.Text className={styles.label}>服务端</Typography.Text>
          <Cell caption="当前">
            <div className={styles.currentLine}>
              {coreText(data, data.current_selected_id || "")}
            </div>
          </Cell>
          <Cell caption="修改">
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Select
                style={{ width: needsBuilds ? 160 : "100%", maxWidth: 420, flex: "none" }}
                placeholder="选择服务端"
                value={draft.core_id || undefined}
                options={(data.cores ?? []).map((row) => ({ value: row.id, label: row.label }))}
                onChange={changeCore}
                disabled={!data.cores.length}
              />
              {needsBuilds ? (
                <Cascader
                  style={{ flex: 1, minWidth: 0 }}
                  placeholder={builds.isFetching ? "正在获取版本" : "选择版本"}
                  allowClear={false}
                  loading={builds.isFetching}
                  value={
                    draft.build_channel && draft.build_name
                      ? [draft.build_channel, draft.build_name]
                      : undefined
                  }
                  options={(builds.data?.options ?? []).map((channel) => ({
                    value: channel.value,
                    label: channel.label,
                    children: (channel.children ?? []).map((row) => ({
                      value: row.value,
                      label: row.label,
                    })),
                  }))}
                  onChange={(value) => {
                    const channel = String(value?.[0] || "");
                    const name = String(value?.[1] || "");
                    edit({ build_channel: channel, build_name: name });
                  }}
                />
              ) : null}
            </div>
            {builds.isError ? (
              <Typography.Paragraph type="danger" style={{ margin: "8px 0 0" }}>
                {apiError(builds.error, "无法获取版本")}
              </Typography.Paragraph>
            ) : null}
          </Cell>

          <Typography.Text className={styles.label}>Java 镜像</Typography.Text>
          <Cell caption="当前">
            <div className={styles.currentLine}>
              {imageText(data.current_java_image || "")}
            </div>
            {data.current_java_warning ? (
              <Typography.Paragraph type="warning" style={{ margin: "8px 0 0" }}>
                {data.current_java_warning}
              </Typography.Paragraph>
            ) : null}
          </Cell>
          <Cell caption="修改">
            <Select
              style={{ width: "100%", maxWidth: 420 }}
              placeholder="选择镜像"
              value={draft.java_image || undefined}
              options={(data.java_images ?? []).map((row) => ({
                value: row.image,
                label: row.image,
              }))}
              onChange={(value) => edit({ java_image: value })}
              disabled={!data.java_images.length}
            />
            {data.java_warning ? (
              <Typography.Paragraph type="warning" style={{ margin: "8px 0 0" }}>
                {data.java_warning}
              </Typography.Paragraph>
            ) : null}
          </Cell>

          <Typography.Text className={styles.label}>启动参数</Typography.Text>
          <Cell caption="当前">
            {currentArgsFromFile ? (
              <Typography.Text type="secondary">user_jvm_args.txt</Typography.Text>
            ) : null}
            <div className={styles.block}>{storedArgs || "还没有启动参数"}</div>
          </Cell>
          <Cell caption="修改">
            {launch === "args" ? (
              <>
                <Typography.Text type="secondary">user_jvm_args.txt</Typography.Text>
                <Input.TextArea
                  style={{ marginTop: 8 }}
                  autoSize={{ minRows: 4, maxRows: 12 }}
                  value={draft.user_jvm_args}
                  onChange={(event) => edit({ user_jvm_args: event.target.value })}
                />
              </>
            ) : (
              <Input
                value={draft.jvm_args}
                placeholder={data.suggested_heap || "-Xms2G -Xmx2G"}
                onChange={(event) => edit({ jvm_args: event.target.value })}
              />
            )}
          </Cell>

          <Typography.Text className={styles.label}>启动指令</Typography.Text>
          <Cell caption="当前">
            <Typography.Paragraph code className={styles.block} style={{ marginBottom: 0 }}>
              {data.current_command || "面板上还没有启动指令"}
            </Typography.Paragraph>
          </Cell>
          <Cell caption="修改">
            <Typography.Paragraph code className={styles.block} style={{ marginBottom: 8 }}>
              {preview || (needsBuilds ? "先选择版本" : "指令还不完整")}
            </Typography.Paragraph>
            <Button
              type="primary"
              htmlType="button"
              disabled={!preview || aligned || !data.application_token_set}
              loading={apply.isPending}
              onClick={() => apply.mutate(draft)}
            >
              应用
            </Button>
            <div>
              <Typography.Text type={aligned ? "success" : "secondary"}>
                {aligned
                  ? "已与面板一致"
                  : data.application_token_set
                    ? draft.build_name
                      ? "下载所选核心，并写入启动指令"
                      : "写入面板上的启动命令"
                    : "先在集成密钥填写管理端 API Token"}
              </Typography.Text>
            </div>
            {apply.isError ? (
              <div>
                <Typography.Text type="danger">
                  {apiError(apply.error, "应用失败")}
                </Typography.Text>
              </div>
            ) : null}
          </Cell>
        </div>
      </div>
    </Card>
  );
}
