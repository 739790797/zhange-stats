import {
  CloseOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileAddOutlined,
  FileOutlined,
  FolderAddOutlined,
  FolderOutlined,
  MoreOutlined,
  ReloadOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Breadcrumb,
  Button,
  Dropdown,
  Form,
  Input,
  Modal,
  Progress,
  Select,
  Space,
  Table,
  Typography,
  Upload,
  message,
} from "antd";
import type { MenuProps } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import styles from "./MinecraftFileManager.module.css";
import { Link } from "react-router-dom";
import {
  chmodMinecraftFiles,
  compressMinecraftFiles,
  copyMinecraftFile,
  createMinecraftFile,
  createMinecraftFolder,
  decompressMinecraftFile,
  deleteMinecraftFiles,
  fetchMinecraftFileContents,
  fetchMinecraftFileDownload,
  fetchMinecraftFiles,
  fetchMinecraftStatus,
  pullMinecraftFile,
  renameMinecraftFile,
  uploadMinecraftFile,
  writeMinecraftFile,
  type MinecraftFileEntry,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { formatBeijing } from "@/lib/time";
import {
  formatBytes,
  isMinecraftArchive,
  isMinecraftTextFile,
  joinMinecraftPath,
  minecraftUploadJobLabel,
  minecraftUploadProgressPercent,
  parentMinecraftPath,
  type MinecraftUploadPhase,
} from "./minecraftUi";
import {
  MinecraftTextFileFormModal,
  type MinecraftTextFileEditorValues,
} from "./MinecraftTextFileEditor";

type NameForm = { name: string };
type RenameForm = { dest: string };
type ChmodForm = { mode: string };
type PullForm = { url: string; filename: string };
type CompressForm = { archive_name: string; extension: "zip" | "tar.gz" };

type UploadJob = {
  uid: string;
  name: string;
  size: number;
  percent: number | null;
  phase: MinecraftUploadPhase;
};

const UPLOAD_DISMISS_MS = 4000;

function uploadJobStatus(phase: MinecraftUploadPhase) {
  if (phase === "done") return "success" as const;
  if (phase === "error") return "exception" as const;
  return "active" as const;
}

function openDownload(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function MinecraftFileManager() {
  const queryClient = useQueryClient();
  const [directory, setDirectory] = useState("/");
  const [selected, setSelected] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [folderOpen, setFolderOpen] = useState(false);
  const [renameRow, setRenameRow] = useState<MinecraftFileEntry | null>(null);
  const [editor, setEditor] = useState<{
    mode: "create" | "edit";
    name: string;
    content: string;
    path?: string;
  } | null>(null);
  const [chmodNames, setChmodNames] = useState<string[]>([]);
  const [pullOpen, setPullOpen] = useState(false);
  const [compressOpen, setCompressOpen] = useState(false);
  const [folderForm] = Form.useForm<NameForm>();
  const [renameForm] = Form.useForm<RenameForm>();
  const [editorForm] = Form.useForm<MinecraftTextFileEditorValues>();
  const [chmodForm] = Form.useForm<ChmodForm>();
  const [pullForm] = Form.useForm<PullForm>();
  const [compressForm] = Form.useForm<CompressForm>();
  const [uploads, setUploads] = useState<UploadJob[]>([]);
  const dismissTimers = useRef<Record<string, number>>({});

  useEffect(
    () => () => {
      Object.values(dismissTimers.current).forEach((id) =>
        window.clearTimeout(id),
      );
    },
    [],
  );

  const patchUpload = (uid: string, patch: Partial<UploadJob>) => {
    setUploads((rows) =>
      rows.map((row) => (row.uid === uid ? { ...row, ...patch } : row)),
    );
  };

  const dismissUpload = (uid: string) => {
    window.clearTimeout(dismissTimers.current[uid]);
    delete dismissTimers.current[uid];
    setUploads((rows) => rows.filter((row) => row.uid !== uid));
  };

  const scheduleDismiss = (uid: string) => {
    window.clearTimeout(dismissTimers.current[uid]);
    dismissTimers.current[uid] = window.setTimeout(
      () => dismissUpload(uid),
      UPLOAD_DISMISS_MS,
    );
  };

  const statusQuery = useQuery({
    queryKey: ["minecraft-status"],
    queryFn: fetchMinecraftStatus,
    retry: 1,
  });
  const pelicanConfigured = Boolean(statusQuery.data?.pelican_configured);

  const listQuery = useQuery({
    queryKey: ["minecraft-files", directory],
    queryFn: () => fetchMinecraftFiles(directory),
    enabled: pelicanConfigured,
  });

  const refreshList = () => {
    queryClient.invalidateQueries({ queryKey: ["minecraft-files", directory] });
  };

  const run = async (task: () => Promise<unknown>, ok: string) => {
    try {
      await task();
      message.success(ok);
      setSelected([]);
      refreshList();
      return true;
    } catch (e: unknown) {
      message.error(apiError(e, "操作失败"));
      return false;
    }
  };

  const download = async (row: MinecraftFileEntry) => {
    try {
      const res = await fetchMinecraftFileDownload(
        joinMinecraftPath(directory, row.name),
      );
      openDownload(res.url);
    } catch (e: unknown) {
      message.error(apiError(e, "无法下载"));
    }
  };

  const openEditor = async (row: MinecraftFileEntry) => {
    const path = joinMinecraftPath(directory, row.name);
    try {
      const res = await fetchMinecraftFileContents(path);
      setEditor({ mode: "edit", name: row.name, content: res.content, path });
      editorForm.setFieldsValue({ name: row.name, content: res.content });
    } catch (e: unknown) {
      message.error(apiError(e, "无法读取文件"));
    }
  };

  const onNameClick = (row: MinecraftFileEntry) => {
    if (row.name === "..") {
      setDirectory(parentMinecraftPath(directory));
      setSelected([]);
      setFilter("");
      return;
    }
    if (!row.is_file) {
      setDirectory(joinMinecraftPath(directory, row.name));
      setSelected([]);
      setFilter("");
      return;
    }
    if (isMinecraftTextFile(row)) {
      void openEditor(row);
      return;
    }
    void download(row);
  };

  const saveEditor = useMutation({
    mutationFn: async () => {
      const values = await editorForm.validateFields();
      if (editor?.mode === "create") {
        return createMinecraftFile(directory, values.name, values.content);
      }
      const path = editor?.path || joinMinecraftPath(directory, values.name);
      return writeMinecraftFile(path, values.content);
    },
    onSuccess: () => {
      message.success(editor?.mode === "create" ? "已创建" : "已保存");
      setEditor(null);
      refreshList();
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const entries = useMemo(() => {
    const rows = listQuery.data?.entries || [];
    const q = filter.trim().toLowerCase();
    const filtered = q
      ? rows.filter((row) => row.name.toLowerCase().includes(q))
      : rows;
    if (directory === "/" || q) return filtered;
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
    return [parent, ...filtered];
  }, [listQuery.data, filter, directory]);

  const crumbs = useMemo(() => {
    const parts = directory.split("/").filter(Boolean);
    const items = [
      {
        title:
          directory === "/" ? (
            "根目录"
          ) : (
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                setDirectory("/");
                setSelected([]);
              }}
            >
              根目录
            </a>
          ),
      },
    ];
    parts.forEach((part, index) => {
      const path = `/${parts.slice(0, index + 1).join("/")}`;
      const last = index === parts.length - 1;
      items.push({
        title: last ? (
          part
        ) : (
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              setDirectory(path);
              setSelected([]);
            }}
          >
            {part}
          </a>
        ),
      });
    });
    return items;
  }, [directory]);

  const confirmDelete = (names: string[]) => {
    Modal.confirm({
      title: names.length === 1 ? `删除 ${names[0]}？` : `删除 ${names.length} 项？`,
      content: "删除后无法从这里恢复。",
      okText: "删除",
      okButtonProps: { danger: true },
      onOk: () => run(() => deleteMinecraftFiles(directory, names), "已删除"),
    });
  };

  const rowMenu = (row: MinecraftFileEntry): MenuProps["items"] => {
    if (row.name === "..") return [];
    const items: MenuProps["items"] = [];
    if (!row.is_file) {
      items.push({
        key: "open",
        label: "打开",
        onClick: () => onNameClick(row),
      });
    } else if (isMinecraftTextFile(row)) {
      items.push({
        key: "edit",
        icon: <EditOutlined />,
        label: "编辑",
        onClick: () => void openEditor(row),
      });
    }
    if (row.is_file) {
      items.push({
        key: "download",
        icon: <DownloadOutlined />,
        label: "下载",
        onClick: () => void download(row),
      });
      items.push({
        key: "copy",
        icon: <CopyOutlined />,
        label: "复制",
        onClick: () =>
          run(
            () => copyMinecraftFile(joinMinecraftPath(directory, row.name)),
            "已复制",
          ),
      });
    }
    items.push({
      key: "rename",
      label: "重命名",
      onClick: () => {
        setRenameRow(row);
        renameForm.setFieldsValue({ dest: row.name });
      },
    });
    if (row.is_file && isMinecraftArchive(row.name)) {
      items.push({
        key: "decompress",
        label: "解压",
        onClick: () =>
          run(
            () => decompressMinecraftFile(directory, row.name),
            "已开始解压",
          ),
      });
    }
    items.push({
      key: "chmod",
      label: "权限",
      onClick: () => {
        setChmodNames([row.name]);
        chmodForm.setFieldsValue({
          mode: (row.mode_bits || "0644").replace(/^0+/, "") || "644",
        });
      },
    });
    items.push({ type: "divider" });
    items.push({
      key: "delete",
      icon: <DeleteOutlined />,
      danger: true,
      label: "删除",
      onClick: () => confirmDelete([row.name]),
    });
    return items;
  };

  if (statusQuery.isLoading) {
    return <Typography.Text type="secondary">加载中…</Typography.Text>;
  }

  if (!pelicanConfigured) {
    return (
      <Alert
        type="info"
        showIcon
        message="尚未连接 Pelican"
        description="填好 Panel 地址、Client Token 和这台服的 UUID 之后，才能管理服内文件。"
        action={
          <Link to="/settings/integrations">
            <Button type="primary" size="small">
              去集成密钥配置
            </Button>
          </Link>
        }
      />
    );
  }

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          文件
        </Typography.Title>
        <Space wrap>
          <Upload
            multiple
            showUploadList={false}
            customRequest={async (options) => {
              const file = options.file as File & { uid?: string };
              const uid = String(
                file.uid || `${file.name}-${file.size}-${Date.now()}`,
              );
              setUploads((rows) => [
                ...rows.filter((row) => row.uid !== uid),
                {
                  uid,
                  name: file.name,
                  size: file.size,
                  percent: null,
                  phase: "uploading",
                },
              ]);
              try {
                await uploadMinecraftFile(directory, file, (percent) => {
                  patchUpload(uid, {
                    percent: percent ?? null,
                    phase: percent === 100 ? "writing" : "uploading",
                  });
                  options.onProgress?.({ percent: percent ?? 0 });
                });
                patchUpload(uid, { percent: 100, phase: "done" });
                options.onSuccess?.(null);
                message.success(`已上传 ${file.name}`);
                refreshList();
                scheduleDismiss(uid);
              } catch (e: unknown) {
                patchUpload(uid, { phase: "error" });
                options.onError?.(e as Error);
                message.error(apiError(e, `上传 ${file.name} 失败`));
              }
            }}
          >
            <Button size="small" icon={<UploadOutlined />}>上传</Button>
          </Upload>
          <Button
            size="small"
            icon={<FileAddOutlined />}
            onClick={() => {
              setEditor({ mode: "create", name: "", content: "" });
              editorForm.setFieldsValue({ name: "", content: "" });
            }}
          >
            新建文件
          </Button>
          <Button
            size="small"
            icon={<FolderAddOutlined />}
            onClick={() => {
              folderForm.resetFields();
              setFolderOpen(true);
            }}
          >
            新建目录
          </Button>
          <Button
            size="small"
            disabled={!selected.length}
            onClick={() => {
              compressForm.setFieldsValue({ archive_name: "", extension: "zip" });
              setCompressOpen(true);
            }}
          >
            压缩
          </Button>
          <Button
            size="small"
            disabled={!selected.length}
            onClick={() => {
              setChmodNames(selected);
              chmodForm.setFieldsValue({ mode: "644" });
            }}
          >
            权限
          </Button>
          <Button
            size="small"
            danger
            disabled={!selected.length}
            icon={<DeleteOutlined />}
            onClick={() => confirmDelete(selected)}
          >
            删除
          </Button>
          <Button size="small" onClick={() => setPullOpen(true)}>从 URL 拉取</Button>
          <Button size="small" icon={<ReloadOutlined />} onClick={() => listQuery.refetch()}>
            刷新
          </Button>
        </Space>
      </div>

      {uploads.length > 0 ? (
        <div className={styles.uploads}>
          {uploads.map((job) => (
            <div key={job.uid} className={styles.job}>
              <div className={styles.jobHead}>
                <span className={styles.jobName} title={job.name}>
                  {job.name}
                </span>
                <span className={styles.jobMeta}>{formatBytes(job.size)}</span>
                {job.phase === "done" || job.phase === "error" ? (
                  <Button
                    type="text"
                    size="small"
                    icon={<CloseOutlined />}
                    onClick={() => dismissUpload(job.uid)}
                  />
                ) : null}
              </div>
              <div className={styles.jobBar}>
                <Progress
                  percent={minecraftUploadProgressPercent(
                    job.phase,
                    job.percent,
                  )}
                  status={uploadJobStatus(job.phase)}
                  showInfo={false}
                  size="small"
                />
              </div>
              <div
                className={
                  job.phase === "error"
                    ? `${styles.jobStatus} ${styles.jobStatusError}`
                    : styles.jobStatus
                }
              >
                {minecraftUploadJobLabel(job.phase, job.percent)}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <Space
        style={{ marginBottom: 12, width: "100%", justifyContent: "space-between" }}
        wrap
      >
        <Breadcrumb items={crumbs} />
        <Input.Search
          size="small"
          allowClear
          placeholder="筛选当前目录"
          style={{ width: 220 }}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </Space>

      {listQuery.isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message={apiError(listQuery.error, "无法列出文件")}
        />
      ) : null}

      <Table
        size="small"
        rowKey="name"
        loading={listQuery.isLoading}
        dataSource={entries}
        pagination={false}
        rowSelection={{
          selectedRowKeys: selected,
          onChange: (keys) =>
            setSelected(keys.map(String).filter((name) => name !== "..")),
          getCheckboxProps: (row) => ({ disabled: row.name === ".." }),
        }}
        onRow={(row) => ({
          onDoubleClick: () => onNameClick(row),
        })}
        columns={[
          {
            title: "名称",
            dataIndex: "name",
            ellipsis: true,
            render: (name: string, row) => (
              <Button
                type="link"
                size="small"
                style={{ padding: 0, height: "auto" }}
                onClick={() => onNameClick(row)}
              >
                <Space>
                  {row.is_file ? <FileOutlined /> : <FolderOutlined />}
                  {name}
                </Space>
              </Button>
            ),
          },
          {
            title: "大小",
            dataIndex: "size",
            width: 110,
            render: (size: number, row) =>
              row.is_file ? formatBytes(size) : "—",
          },
          {
            title: "修改时间",
            dataIndex: "modified_at",
            width: 180,
            render: (value: string | null) =>
              value ? formatBeijing(value, "YYYY-MM-DD HH:mm") : "—",
          },
          {
            title: "权限",
            dataIndex: "mode",
            width: 120,
            ellipsis: true,
            render: (mode: string, row) => row.mode_bits || mode || "—",
          },
          {
            title: "",
            width: 48,
            render: (_, row) =>
              row.name === ".." ? null : (
                <Dropdown menu={{ items: rowMenu(row) }} trigger={["click"]}>
                  <Button type="text" size="small" icon={<MoreOutlined />} />
                </Dropdown>
              ),
          },
        ]}
      />

      <Modal
        title="新建目录"
        open={folderOpen}
        onCancel={() => setFolderOpen(false)}
        onOk={async () => {
          const values = await folderForm.validateFields();
          const ok = await run(
            () => createMinecraftFolder(directory, values.name),
            "已创建目录",
          );
          if (ok) setFolderOpen(false);
        }}
      >
        <Form form={folderForm} layout="vertical">
          <Form.Item
            name="name"
            label="目录名"
            rules={[{ required: true, message: "请输入目录名" }]}
          >
            <Input placeholder="config" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="重命名"
        open={Boolean(renameRow)}
        onCancel={() => setRenameRow(null)}
        onOk={async () => {
          if (!renameRow) return;
          const values = await renameForm.validateFields();
          const ok = await run(
            () => renameMinecraftFile(directory, renameRow.name, values.dest),
            "已重命名",
          );
          if (ok) setRenameRow(null);
        }}
      >
        <Form form={renameForm} layout="vertical">
          <Form.Item
            name="dest"
            label="新名称"
            rules={[{ required: true, message: "请输入新名称" }]}
          >
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <MinecraftTextFileFormModal
        title={editor?.mode === "create" ? "新建文件" : `编辑 ${editor?.name || ""}`}
        open={Boolean(editor)}
        nameDisabled={editor?.mode === "edit"}
        confirmLoading={saveEditor.isPending}
        form={editorForm}
        onCancel={() => setEditor(null)}
        onOk={() => saveEditor.mutate()}
      />

      <Modal
        title="修改权限"
        open={chmodNames.length > 0}
        onCancel={() => setChmodNames([])}
        onOk={async () => {
          const values = await chmodForm.validateFields();
          if (!chmodNames.length) return;
          const ok = await run(
            () => chmodMinecraftFiles(directory, chmodNames, values.mode),
            "已修改权限",
          );
          if (ok) setChmodNames([]);
        }}
      >
        <Form form={chmodForm} layout="vertical">
          <Form.Item
            name="mode"
            label="权限"
            extra="例如 644 或 0755"
            rules={[{ required: true, message: "请输入权限" }]}
          >
            <Input placeholder="644" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="从 URL 拉取"
        open={pullOpen}
        onCancel={() => setPullOpen(false)}
        onOk={async () => {
          const values = await pullForm.validateFields();
          const ok = await run(
            () =>
              pullMinecraftFile(
                directory,
                values.url,
                values.filename || "",
              ),
            "已请求拉取",
          );
          if (ok) {
            setPullOpen(false);
            pullForm.resetFields();
          }
        }}
      >
        <Form form={pullForm} layout="vertical">
          <Form.Item
            name="url"
            label="地址"
            rules={[{ required: true, message: "请输入 URL" }]}
          >
            <Input placeholder="https://…" />
          </Form.Item>
          <Form.Item name="filename" label="保存为" extra="留空则用 URL 里的文件名">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="压缩所选"
        open={compressOpen}
        onCancel={() => setCompressOpen(false)}
        onOk={async () => {
          const values = await compressForm.validateFields();
          const ok = await run(
            () =>
              compressMinecraftFiles({
                directory,
                names: selected,
                archive_name: values.archive_name || null,
                extension: values.extension,
              }),
            "已压缩",
          );
          if (ok) setCompressOpen(false);
        }}
      >
        <Form
          form={compressForm}
          layout="vertical"
          initialValues={{ extension: "zip" }}
        >
          <Form.Item name="archive_name" label="压缩包名" extra="留空则由面板生成">
            <Input placeholder="archive" />
          </Form.Item>
          <Form.Item name="extension" label="格式">
            <Select
              options={[
                { value: "zip", label: "zip" },
                { value: "tar.gz", label: "tar.gz" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
