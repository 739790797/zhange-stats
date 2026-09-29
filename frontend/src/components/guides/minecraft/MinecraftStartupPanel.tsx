import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Card, Input, Select, Typography } from "antd";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  fetchMinecraftStartup,
  saveMinecraftStartup,
  type MinecraftStartup,
  type MinecraftStartupIn,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { heapFlagsFromText } from "./minecraftUi";
import styles from "./MinecraftLivePanel.module.css";

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
  };
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 16, marginBottom: 16, alignItems: "flex-start" }}>
      <Typography.Text style={{ width: 88, flex: "none", lineHeight: "32px" }}>
        {label}
      </Typography.Text>
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
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
  const [dirty, setDirty] = useState(false);
  const draftRef = useRef<Draft | null>(null);
  draftRef.current = draft;

  useEffect(() => {
    if (!query.data || dirty) return;
    setDraft(draftFrom(query.data));
  }, [query.data, dirty]);

  const save = useMutation({
    mutationFn: saveMinecraftStartup,
    onSuccess: (next, sent) => {
      queryClient.setQueryData(["minecraft-startup"], next);
      const current = draftRef.current;
      if (
        current &&
        current.core_id === sent.core_id &&
        current.loader === sent.loader &&
        current.java_image === sent.java_image &&
        current.jvm_args === sent.jvm_args &&
        current.user_jvm_args === sent.user_jvm_args
      ) {
        setDirty(false);
      }
    },
  });

  useEffect(() => {
    if (!dirty || !draft) return;
    if (!draft.core_id && !draft.loader) return;
    const timer = window.setTimeout(() => {
      const current = draftRef.current;
      if (current && (current.core_id || current.loader)) save.mutate(current);
    }, 600);
    return () => window.clearTimeout(timer);
    // save.mutate 在 Query 里是稳定的；把整个 mutation 放进依赖会在每次渲染时清掉计时器
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dirty, draft]);

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
    setDirty(true);
  };

  const changeCore = (coreId: string) => {
    const core = (data.cores ?? []).find((row) => row.id === coreId);
    if (!core) {
      edit({ core_id: coreId });
      return;
    }
    if (core.launch === "jar" && selected?.launch === "args") {
      edit({
        core_id: coreId,
        jvm_args:
          heapFlagsFromText(draft.user_jvm_args) ||
          draft.jvm_args ||
          data.suggested_heap ||
          "",
      });
      return;
    }
    edit({ core_id: coreId });
  };

  const launch = selected?.launch || data.launch;
  const preview = (() => {
    if (!selected) return "";
    if (launch === "args") {
      const path = (selected.unix_args || "").replace(/^\//, "");
      return path ? `java @user_jvm_args.txt @${path} nogui` : "";
    }
    if (!selected.jar) return "";
    return ["java", (draft.jvm_args || "").trim(), "-jar", selected.jar, selected.server_args]
      .filter(Boolean)
      .join(" ");
  })();
  const previewSynced = Boolean(data.synced && preview && preview === data.command);

  return (
    <Card size="small" title="启动">
      <div className={styles.wrap}>
        <Row label="加载器">
          {data.loader_locked ? (
            <Typography.Text style={{ lineHeight: "32px" }}>{data.loader_label}</Typography.Text>
          ) : (
            <Select
              style={{ maxWidth: 360 }}
              placeholder="先选择加载器"
              value={draft.loader || undefined}
              options={(data.loader_choices ?? []).map((value) => ({
                value,
                label: LOADER_LABELS[value] || value,
              }))}
              onChange={(value) => edit({ loader: value, core_id: "" })}
            />
          )}
        </Row>
        <Row label="服务端">
          <Select
            style={{ maxWidth: 420 }}
            placeholder="选择服务端"
            value={draft.core_id || undefined}
            options={(data.cores ?? []).map((row) => ({ value: row.id, label: row.label }))}
            onChange={changeCore}
            disabled={!data.cores.length}
          />
        </Row>
        <Row label="Java 镜像">
          <Select
            style={{ maxWidth: 420 }}
            placeholder="选择镜像"
            value={draft.java_image || undefined}
            options={(data.java_images ?? []).map((row) => ({
              value: row.image,
              label: row.label === row.image ? row.image : `${row.label} · ${row.image}`,
            }))}
            onChange={(value) => edit({ java_image: value })}
            disabled={!data.java_images.length}
          />
          {data.java_warning ? (
            <Typography.Paragraph type="warning" style={{ margin: "8px 0 0" }}>
              {data.java_warning}
            </Typography.Paragraph>
          ) : null}
        </Row>
        <Row label="启动参数">
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
        </Row>
        <Row label="启动指令">
          <Typography.Paragraph code style={{ marginBottom: 8 }}>
            {preview || "指令还不完整"}
          </Typography.Paragraph>
          <Typography.Text type={previewSynced ? "success" : "secondary"}>
            {previewSynced
              ? "已同步到 Pelican"
              : data.message || "改完且文件齐全后会写入"}
          </Typography.Text>
          {save.isError ? (
            <div>
              <Typography.Text type="danger">
                {apiError(save.error, "写入 Pelican 失败")}
              </Typography.Text>
            </div>
          ) : null}
        </Row>
      </div>
    </Card>
  );
}
