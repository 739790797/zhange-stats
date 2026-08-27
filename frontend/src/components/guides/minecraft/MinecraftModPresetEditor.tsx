import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Input, Modal, Popconfirm, Space, Table, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  applyMinecraftModToolPreset,
  fetchMinecraftModToolPreset,
  fetchMinecraftModToolPresetKeys,
  saveMinecraftModToolPreset,
  type MinecraftModToolPreset,
  type MinecraftModToolPresetPin,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { MinecraftConfigFilesModal, MinecraftModConfigModal } from "./MinecraftConfigFilesModal";
import {
  isMinecraftPathWithin,
  isMinecraftPinnableFile,
  modPresetStatusMessage,
  normalizeMinecraftPath,
} from "./minecraftUi";
import styles from "./MinecraftModToolCard.module.css";

type Pin = MinecraftModToolPresetPin;

export function MinecraftModPresetSection({
  toolId,
  toolTitle,
  pelicanConfigured,
  enabled,
}: {
  toolId: string;
  toolTitle: string;
  pelicanConfigured: boolean;
  enabled: boolean;
}) {
  const queryClient = useQueryClient();
  const [editorOpen, setEditorOpen] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const query = useQuery({
    queryKey: ["minecraft-mod-preset", toolId],
    queryFn: () => fetchMinecraftModToolPreset(toolId),
    enabled: enabled && Boolean(toolId) && pelicanConfigured,
  });

  const apply = useMutation({
    mutationFn: () => applyMinecraftModToolPreset(toolId),
    onSuccess: (res) => {
      message.success(res.message);
      void queryClient.invalidateQueries({
        queryKey: ["minecraft-mod-preset", toolId],
      });
    },
    onError: (e: unknown) => message.error(apiError(e, "应用预设失败")),
  });

  const data = query.data;
  const directories = data?.directories || [];
  const status = data?.status || "no_preset";
  const statusText = modPresetStatusMessage({
    status,
    diffs: data?.diffs,
    directories,
  });

  return (
    <>
      <div className={styles.sectionHead}>
        <div className={styles.sectionTitle}>配置文件</div>
        <Space wrap>
          <Button
            disabled={!pelicanConfigured}
            onClick={() => setConfigOpen(true)}
          >
            编辑配置
          </Button>
          <Button
            disabled={!pelicanConfigured || query.isFetching}
            onClick={() => setEditorOpen(true)}
          >
            编辑预设
          </Button>
          {status === "mismatch" ? (
            <Popconfirm
              title="按预设改盘上已有文件里的这些键"
              description="不会新建缺失的配置文件，也不会改未钉住的键。"
              okText="应用"
              cancelText="返回"
              disabled={!pelicanConfigured || apply.isPending}
              onConfirm={() => apply.mutate()}
            >
              <Button
                type="primary"
                loading={apply.isPending}
                disabled={!pelicanConfigured}
              >
                一键应用
              </Button>
            </Popconfirm>
          ) : null}
        </Space>
      </div>
      {query.isError ? (
        <Alert
          style={{ marginTop: 12 }}
          showIcon
          type="error"
          message={apiError(query.error, "无法读取预设")}
        />
      ) : statusText ? (
        <Alert
          style={{ marginTop: 12 }}
          showIcon
          type={
            !directories.length
              ? "info"
              : status === "match"
                ? "success"
                : status === "missing_files"
                  ? "info"
                  : "warning"
          }
          message={statusText}
        />
      ) : null}
      <MinecraftModConfigModal
        open={configOpen}
        title={`${toolTitle} 配置`}
        toolId={toolId}
        directories={directories}
        onClose={() => setConfigOpen(false)}
      />
      <MinecraftModPresetEditor
        toolId={toolId}
        open={editorOpen}
        snapshot={data}
        onClose={() => setEditorOpen(false)}
      />
    </>
  );
}

function MinecraftModPresetEditor({
  toolId,
  open,
  snapshot,
  onClose,
}: {
  toolId: string;
  open: boolean;
  snapshot?: MinecraftModToolPreset;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [pins, setPins] = useState<Pin[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [keyFile, setKeyFile] = useState("");
  const [keyRows, setKeyRows] = useState<{ key: string; value: string }[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [keyLoading, setKeyLoading] = useState(false);

  useEffect(() => {
    if (!open) {
      setPins([]);
      setPickerOpen(false);
      setKeyFile("");
      return;
    }
    if (!snapshot) return;
    setPins(snapshot.pins || []);
  }, [open, snapshot]);

  const directories = snapshot?.directories || [];

  const save = useMutation({
    mutationFn: () => saveMinecraftModToolPreset(toolId, { pins }),
    onSuccess: (res) => {
      message.success(res.has_preset ? "已保存预设" : "已清空预设");
      void queryClient.invalidateQueries({
        queryKey: ["minecraft-mod-preset", toolId],
      });
      onClose();
    },
    onError: (e: unknown) => message.error(apiError(e, "保存预设失败")),
  });

  const pickFile = (path: string) => {
    const abs = normalizeMinecraftPath(path);
    const name = abs.split("/").pop() || abs;
    const allowed = directories.some((root) => isMinecraftPathWithin(root, abs));
    if (!abs || abs === "/" || !isMinecraftPinnableFile(name) || !allowed) {
      message.error("请选择配置目录里可做预设的文件");
      return;
    }
    setPickerOpen(false);
    setKeyFile(abs);
    setKeyLoading(true);
    fetchMinecraftModToolPresetKeys(toolId, abs)
      .then((res) => {
        const rows = res.keys || [];
        const current = new Map(
          pins
            .filter((row) => row.file === abs)
            .map((row) => [row.key, row.value]),
        );
        setSelectedKeys(
          rows.filter((row) => current.has(row.key)).map((row) => row.key),
        );
        setKeyRows(
          rows.map((row) => ({
            key: row.key,
            value: current.get(row.key) ?? row.value,
          })),
        );
      })
      .catch((e: unknown) => {
        setKeyFile("");
        message.error(apiError(e, "无法读取该文件的键"));
      })
      .finally(() => setKeyLoading(false));
  };

  const confirmKeys = () => {
    const picked = new Map(
      keyRows.map((row) => [row.key, row.value] as const),
    );
    const next = pins.filter((row) => row.file !== keyFile);
    for (const key of selectedKeys) {
      next.push({
        file: keyFile,
        key,
        value: picked.get(key) ?? "",
      });
    }
    setPins(next);
    setKeyFile("");
    setKeyRows([]);
    setSelectedKeys([]);
  };

  const columns = useMemo(
    () => [
      { title: "文件", dataIndex: "file", ellipsis: true },
      { title: "键", dataIndex: "key", width: 180 },
      {
        title: "值",
        dataIndex: "value",
        render: (_: string, row: Pin, index: number) => (
          <Input
            value={row.value}
            onChange={(event) => {
              const value = event.target.value;
              setPins((prev) =>
                prev.map((item, i) => (i === index ? { ...item, value } : item)),
              );
            }}
          />
        ),
      },
      {
        title: "",
        key: "remove",
        width: 72,
        render: (_: unknown, _row: Pin, index: number) => (
          <Button
            type="link"
            size="small"
            onClick={() =>
              setPins((prev) => prev.filter((_, i) => i !== index))
            }
          >
            删除
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <>
      <Modal
        title="编辑预设"
        open={open && !pickerOpen && !keyFile}
        width={840}
        confirmLoading={save.isPending}
        onCancel={onClose}
        onOk={() => save.mutate()}
        okText="保存"
      >
        <Space style={{ marginBottom: 12 }}>
          <Button
            onClick={() => {
              if (!directories.length) {
                message.info("请先在「编辑配置」里指定配置目录");
                return;
              }
              setPickerOpen(true);
            }}
          >
            添加键
          </Button>
        </Space>
        <Table
          size="small"
          rowKey={(row) => `${row.file}:${row.key}`}
          pagination={false}
          dataSource={pins}
          locale={{ emptyText: "没有预设键。可点添加键，或直接保存表示这个模组不需要预设。" }}
          columns={columns}
        />
      </Modal>
      <MinecraftConfigFilesModal
        open={open && pickerOpen}
        roots={directories}
        title="选择预设文件"
        onClose={() => setPickerOpen(false)}
        onPick={pickFile}
      />
      <Modal
        title={`选择键 · ${keyFile}`}
        open={open && Boolean(keyFile)}
        confirmLoading={keyLoading}
        okText="加入预设"
        onCancel={() => {
          setKeyFile("");
          setKeyRows([]);
          setSelectedKeys([]);
        }}
        onOk={confirmKeys}
        okButtonProps={{ disabled: keyLoading }}
        zIndex={1100}
      >
        <Table
          size="small"
          rowKey="key"
          pagination={false}
          loading={keyLoading}
          dataSource={keyRows}
          rowSelection={{
            selectedRowKeys: selectedKeys,
            onChange: (keys) => setSelectedKeys(keys.map(String)),
          }}
          columns={[
            { title: "键", dataIndex: "key", width: 200 },
            {
              title: "值",
              dataIndex: "value",
              render: (_: string, row: { key: string; value: string }) => (
                <Input
                  value={row.value}
                  onChange={(event) => {
                    const value = event.target.value;
                    setKeyRows((prev) =>
                      prev.map((item) =>
                        item.key === row.key ? { ...item, value } : item,
                      ),
                    );
                  }}
                />
              ),
            },
          ]}
        />
      </Modal>
    </>
  );
}
