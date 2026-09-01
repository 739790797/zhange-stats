import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Checkbox, Descriptions, Modal, Select, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  fetchMinecraftModToolVersions,
  installMinecraftModTool,
  type MinecraftModTool,
  type MinecraftModToolVersions,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { loaderLabel } from "./minecraftUi";

type ToolVersion = NonNullable<MinecraftModToolVersions["versions"]>[number];
const EMPTY_VERSIONS: ToolVersion[] = [];

export function MinecraftModToolInstallModal({
  tool,
  mode,
  onClose,
  onDone,
}: {
  tool: MinecraftModTool;
  mode: "install" | "change" | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const open = Boolean(mode);
  const catalog = tool.catalog;
  const [versionId, setVersionId] = useState("");
  const [restart, setRestart] = useState(false);

  const versionsQuery = useQuery({
    queryKey: ["minecraft-mod-tool-versions", tool.id],
    queryFn: () => fetchMinecraftModToolVersions(tool.id),
    enabled: open,
  });

  const versions = versionsQuery.data?.versions || EMPTY_VERSIONS;
  const loader = versionsQuery.data?.loader || catalog?.loader || "";
  const mcVersion = versionsQuery.data?.mc_version || catalog?.mc_version || "";
  const installed = catalog?.installed_version || "";

  useEffect(() => {
    if (!open) {
      setVersionId("");
      setRestart(false);
      return;
    }
    const rows = versionsQuery.data?.versions || [];
    if (!rows.length) return;
    const current = rows.find(
      (row) => installed && row.version_number === installed,
    );
    setVersionId((current || rows[0]).version_id);
  }, [open, versionsQuery.data?.versions, installed]);

  const options = useMemo(
    () =>
      versions.map((row, index) => {
        const bits = [row.version_number || row.filename];
        if (installed && row.version_number === installed) bits.push("已装");
        if (index === 0) bits.push("最新兼容");
        return { value: row.version_id, label: bits.join(" · ") };
      }),
    [versions, installed],
  );

  const install = useMutation({
    mutationFn: () =>
      installMinecraftModTool(tool.id, {
        version_id: versionId,
        preset_id: "",
        restart,
      }),
    onSuccess: (res) => {
      message.success(res.message);
      onDone();
      onClose();
    },
    onError: (e: unknown) =>
      message.error(apiError(e, mode === "change" ? "更换版本失败" : "安装失败")),
  });

  const title =
    mode === "change" ? `修改版本 · ${tool.title}` : `安装模组 · ${tool.title}`;
  const emptyMessage =
    versionsQuery.data?.message || catalog?.message || "没有匹配当前服的文件";

  return (
    <Modal
      title={title}
      open={open}
      okText={mode === "change" ? "替换" : "安装"}
      confirmLoading={install.isPending}
      okButtonProps={{ disabled: !versionId || !versions.length }}
      onCancel={onClose}
      onOk={() => install.mutate()}
      destroyOnClose
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          来源、加载器和游戏版本按当前服带入，只需选择模组版本。
        </Typography.Paragraph>
        <Descriptions column={1} size="small">
          <Descriptions.Item label="来源">Modrinth</Descriptions.Item>
          <Descriptions.Item label="加载器">
            {loaderLabel(loader)}
          </Descriptions.Item>
          <Descriptions.Item label="游戏版本">
            {mcVersion || "—"}
          </Descriptions.Item>
        </Descriptions>
        <div>
          <Typography.Text type="secondary">模组版本</Typography.Text>
          <Select
            showSearch
            optionFilterProp="label"
            placeholder={
              versionsQuery.isFetching ? "正在列出兼容版本…" : "选择版本"
            }
            loading={versionsQuery.isFetching}
            value={versionId || undefined}
            onChange={setVersionId}
            options={options}
            style={{ width: "100%", marginTop: 6 }}
          />
        </div>
        {versionsQuery.isError ? (
          <Alert
            type="error"
            showIcon
            message={apiError(versionsQuery.error, "无法列出版本")}
          />
        ) : null}
        {!versionsQuery.isFetching && !versions.length ? (
          <Alert type="warning" showIcon message={emptyMessage} />
        ) : null}
        <Checkbox checked={restart} onChange={(e) => setRestart(e.target.checked)}>
          完成后重启服务器
        </Checkbox>
      </div>
    </Modal>
  );
}
