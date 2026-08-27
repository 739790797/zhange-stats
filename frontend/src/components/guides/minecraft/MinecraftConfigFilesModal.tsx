import { FileOutlined, FolderOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Breadcrumb,
  Button,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  fetchMinecraftFiles,
  saveMinecraftModToolPreset,
  type MinecraftFileEntry,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { MinecraftPathFileEditor } from "./MinecraftTextFileEditor";
import {
  isMinecraftPathWithin,
  isMinecraftTextFile,
  joinMinecraftPath,
  normalizeMinecraftPath,
  parentMinecraftPathWithin,
} from "./minecraftUi";

function MinecraftFileBrowser({
  jailRoot,
  directory,
  enabled,
  allowFiles = true,
  onDirectoryChange,
  onOpenFile,
}: {
  jailRoot: string;
  directory: string;
  enabled: boolean;
  allowFiles?: boolean;
  onDirectoryChange: (path: string) => void;
  onOpenFile: (path: string) => void;
}) {
  const listQuery = useQuery({
    queryKey: ["minecraft-files", directory],
    queryFn: () => fetchMinecraftFiles(directory),
    enabled: enabled && Boolean(jailRoot),
    retry: 1,
  });

  const entries = useMemo(() => {
    const rows = listQuery.data?.entries || [];
    if (directory === jailRoot) return rows;
    const parent: MinecraftFileEntry = {
      name: "..",
      is_file: false,
      is_symlink: false,
      size: 0,
      mode: "",
      mode_bits: "",
      mimetype: "",
      created_at: null,
      modified_at: null,
    };
    return [parent, ...rows];
  }, [listQuery.data, directory, jailRoot]);

  const crumbs = useMemo(() => {
    const rootParts = jailRoot.split("/").filter(Boolean);
    const parts = directory.split("/").filter(Boolean);
    const extra = parts.slice(rootParts.length);
    const items = [
      {
        title: (
          <Button
            type="link"
            size="small"
            style={{ padding: 0 }}
            onClick={() => onDirectoryChange(jailRoot)}
          >
            {jailRoot}
          </Button>
        ),
      },
    ];
    extra.forEach((part, index) => {
      const path = normalizeMinecraftPath(
        `${jailRoot}/${extra.slice(0, index + 1).join("/")}`,
      );
      items.push({
        title: (
          <Button
            type="link"
            size="small"
            style={{ padding: 0 }}
            onClick={() => onDirectoryChange(path)}
          >
            {part}
          </Button>
        ),
      });
    });
    return items;
  }, [directory, jailRoot, onDirectoryChange]);

  const openFile = (row: MinecraftFileEntry) => {
    if (!allowFiles) return;
    if (!isMinecraftTextFile(row)) {
      message.info("这个文件不能在这里编辑");
      return;
    }
    const path = joinMinecraftPath(directory, row.name);
    if (!isMinecraftPathWithin(jailRoot, path)) {
      message.error("路径无效");
      return;
    }
    onOpenFile(path);
  };

  const openRow = (row: MinecraftFileEntry) => {
    if (row.name === "..") {
      onDirectoryChange(parentMinecraftPathWithin(jailRoot, directory));
      return;
    }
    if (!row.is_file) {
      const next = joinMinecraftPath(directory, row.name);
      if (!isMinecraftPathWithin(jailRoot, next)) {
        message.error("路径无效");
        return;
      }
      onDirectoryChange(next);
      return;
    }
    openFile(row);
  };

  return (
    <>
      <Breadcrumb items={crumbs} style={{ marginBottom: 12 }} />
      {listQuery.isError ? (
        <Typography.Text type="secondary">
          {apiError(listQuery.error, "无法列出这个目录。")}
        </Typography.Text>
      ) : (
        <Table
          size="small"
          rowKey="name"
          pagination={false}
          loading={listQuery.isLoading}
          dataSource={entries}
          onRow={(row) => ({ onClick: () => openRow(row) })}
          columns={[
            {
              title: "名称",
              dataIndex: "name",
              render: (value: string, row) => (
                <span>
                  {row.is_file ? (
                    <FileOutlined style={{ marginRight: 8 }} />
                  ) : (
                    <FolderOutlined style={{ marginRight: 8 }} />
                  )}
                  {value}
                </span>
              ),
            },
          ]}
        />
      )}
    </>
  );
}

export function MinecraftConfigFilesModal({
  open,
  root,
  roots,
  title,
  onClose,
  onPick,
  onPickDirectory,
}: {
  open: boolean;
  root?: string;
  roots?: string[];
  title?: string;
  onClose: () => void;
  onPick?: (path: string) => void;
  onPickDirectory?: (dir: string) => void;
}) {
  const pickDir = Boolean(onPickDirectory);
  const jailOptions = useMemo(() => {
    if (pickDir) return ["/"];
    const rows = (roots?.length ? roots : [root || "/"]).map(
      normalizeMinecraftPath,
    );
    return rows.length ? rows : ["/"];
  }, [pickDir, roots, root]);
  const initialJail = jailOptions[0];
  const [jailRoot, setJailRoot] = useState(initialJail);
  const [directory, setDirectory] = useState(initialJail);
  const [editorPath, setEditorPath] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setEditorPath(null);
      return;
    }
    setJailRoot(initialJail);
    setDirectory(initialJail);
  }, [open, initialJail]);

  const switchJail = (next: string) => {
    setJailRoot(next);
    setDirectory(next);
  };

  const openFile = (path: string) => {
    if (onPick) {
      onPick(path);
      return;
    }
    setEditorPath(path);
  };

  return (
    <>
      <Modal
        title={title || (onPickDirectory ? "选择配置目录" : onPick ? "选择文件" : "配置文件")}
        open={open && !editorPath}
        width={720}
        zIndex={onPick || onPickDirectory ? 1100 : undefined}
        onCancel={onClose}
        footer={
          onPickDirectory ? (
            <Button
              type="primary"
              disabled={directory === "/"}
              onClick={() => onPickDirectory(directory)}
            >
              使用当前目录
            </Button>
          ) : null
        }
      >
        {jailOptions.length > 1 ? (
          <Select
            size="small"
            style={{ minWidth: 240, marginBottom: 12 }}
            value={jailRoot}
            options={jailOptions.map((path) => ({ value: path, label: path }))}
            onChange={switchJail}
          />
        ) : null}
        <MinecraftFileBrowser
          jailRoot={jailRoot}
          directory={directory}
          enabled={open && !editorPath}
          allowFiles={!onPickDirectory}
          onDirectoryChange={setDirectory}
          onOpenFile={onPickDirectory ? () => undefined : openFile}
        />
      </Modal>
      {onPick || onPickDirectory ? null : (
        <MinecraftPathFileEditor
          path={editorPath}
          onClose={() => setEditorPath(null)}
        />
      )}
    </>
  );
}

export function MinecraftModConfigModal({
  open,
  title,
  toolId,
  directories,
  onClose,
}: {
  open: boolean;
  title: string;
  toolId: string;
  directories: string[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [activeRoot, setActiveRoot] = useState(directories[0] || "");
  const [directory, setDirectory] = useState(directories[0] || "");
  const [adding, setAdding] = useState(false);
  const [editorPath, setEditorPath] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setAdding(false);
      setEditorPath(null);
      return;
    }
  }, [open]);

  useEffect(() => {
    if (!directories.includes(activeRoot)) {
      const next = directories[0] || "";
      setActiveRoot(next);
      setDirectory(next);
    }
  }, [directories, activeRoot]);

  const saveDirs = useMutation({
    mutationFn: (next: string[]) =>
      saveMinecraftModToolPreset(toolId, { directories: next }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({
        queryKey: ["minecraft-mod-preset", toolId],
      });
      message.success(
        res.directories?.length ? "已更新配置目录" : "已清空配置目录",
      );
    },
    onError: (e: unknown) => message.error(apiError(e, "保存配置目录失败")),
  });

  const addDirectory = (path: string) => {
    const abs = normalizeMinecraftPath(path);
    if (!abs || abs === "/") {
      message.error("请选择一个具体目录，不能用服根目录");
      return;
    }
    if (directories.includes(abs)) {
      message.info("这个目录已经加过了");
      setAdding(false);
      return;
    }
    saveDirs.mutate([...directories, abs], {
      onSuccess: () => {
        setActiveRoot(abs);
        setDirectory(abs);
      },
    });
    setAdding(false);
  };

  const removeActive = () => {
    if (!activeRoot) return;
    saveDirs.mutate(directories.filter((row) => row !== activeRoot));
  };

  const switchRoot = (next: string) => {
    setActiveRoot(next);
    setDirectory(next);
  };

  return (
    <>
      <Modal
        title={title}
        open={open && !adding && !editorPath}
        width={720}
        footer={null}
        onCancel={onClose}
      >
        <Space wrap style={{ marginBottom: 12 }}>
          {directories.length ? (
            <Select
              size="small"
              style={{ minWidth: 240 }}
              value={activeRoot}
              options={directories.map((path) => ({ value: path, label: path }))}
              onChange={switchRoot}
            />
          ) : null}
          <Button onClick={() => setAdding(true)}>添加目录</Button>
          {activeRoot ? (
            <Popconfirm
              title="不再把这个目录当作该模组的配置目录"
              description="目录里钉过的预设键也会一并去掉。"
              okText="移除"
              cancelText="返回"
              onConfirm={removeActive}
            >
              <Button danger>移除此目录</Button>
            </Popconfirm>
          ) : null}
        </Space>
        {directories.length && activeRoot ? (
          <MinecraftFileBrowser
            jailRoot={activeRoot}
            directory={directory || activeRoot}
            enabled={open && !adding && !editorPath}
            onDirectoryChange={setDirectory}
            onOpenFile={setEditorPath}
          />
        ) : (
          <Typography.Text type="secondary">
            还没有指定配置目录。点「添加目录」，从服盘里选一个或多个文件夹。
          </Typography.Text>
        )}
      </Modal>
      <MinecraftConfigFilesModal
        open={open && adding}
        title="选择配置目录"
        onClose={() => setAdding(false)}
        onPickDirectory={addDirectory}
      />
      <MinecraftPathFileEditor
        path={editorPath}
        onClose={() => setEditorPath(null)}
      />
    </>
  );
}
