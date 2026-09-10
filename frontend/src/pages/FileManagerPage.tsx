import {
  CloseOutlined,
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
  Card,
  Col,
  Dropdown,
  Form,
  Input,
  Modal,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Upload,
  message,
  theme,
} from "antd";
import type { MenuProps } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createManagedFile,
  createManagedFolder,
  deleteManagedFiles,
  downloadManagedFile,
  fetchFileBrowse,
  fetchFileSummary,
  fetchManagedFileContents,
  renameManagedFile,
  uploadManagedFile,
  writeManagedFile,
  type FileBrowseEntry,
  type FileOk,
} from "@/api/filesApi";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";
import {
  FILE_KIND_LABEL,
  fileBrowseUp,
  formatBytes,
  formatPercent,
  isFileBrowseLocked,
  joinFileRel,
  managedUploadJobLabel,
  managedUploadProgressPercent,
  stackDiskUsage,
  type FileKind,
  type ManagedUploadPhase,
} from "@/lib/fileManager";
import { formatBeijing } from "@/lib/time";

type BrowserRow = FileBrowseEntry & {
  key: string;
  browseRootId?: string;
  missing?: boolean;
};

type NameForm = { name: string };
type RenameForm = { dest: string };
type EditorForm = { name: string; content: string };

type UploadJob = {
  uid: string;
  name: string;
  size: number;
  percent: number | null;
  phase: ManagedUploadPhase;
};

const UPLOAD_DISMISS_MS = 4000;

function uploadJobStatus(phase: ManagedUploadPhase) {
  if (phase === "done") return "success" as const;
  if (phase === "error") return "exception" as const;
  return "active" as const;
}

export default function FileManagerPage() {
  const { token } = theme.useToken();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const rootId = params.get("root") || "install";
  const path = params.get("path") || "";
  const [selected, setSelected] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [folderOpen, setFolderOpen] = useState(false);
  const [renameRow, setRenameRow] = useState<BrowserRow | null>(null);
  const [editor, setEditor] = useState<{
    mode: "create" | "edit";
    name: string;
    content: string;
    path?: string;
  } | null>(null);
  const [uploads, setUploads] = useState<UploadJob[]>([]);
  const [folderForm] = Form.useForm<NameForm>();
  const [renameForm] = Form.useForm<RenameForm>();
  const [editorForm] = Form.useForm<EditorForm>();
  const dismissTimers = useRef<Record<string, number>>({});

  useEffect(
    () => () => {
      Object.values(dismissTimers.current).forEach((id) =>
        window.clearTimeout(id),
      );
    },
    [],
  );

  const summaryQuery = useQuery({
    queryKey: ["site-files-summary"],
    queryFn: () => fetchFileSummary(false),
  });

  const browseQuery = useQuery({
    queryKey: ["site-files-browse", rootId, path],
    queryFn: () => fetchFileBrowse(rootId, path),
    enabled: Boolean(rootId),
  });

  const summary = summaryQuery.data;
  const roots = useMemo(() => summary?.roots || [], [summary?.roots]);
  const summaryCards = useMemo(() => {
    const byKind = new Map(
      (summary?.kind_totals || []).map((row) => [row.kind, row]),
    );
    const kinds = Object.keys(FILE_KIND_LABEL) as FileKind[];
    return [
      {
        key: "total",
        title: "本站合计",
        value: summary?.total_bytes ?? 0,
      },
      ...kinds.map((kind) => {
        const row = byKind.get(kind);
        return {
          key: kind,
          title: FILE_KIND_LABEL[kind],
          value: row?.size_bytes ?? 0,
        };
      }),
    ];
  }, [summary?.kind_totals, summary?.total_bytes]);
  const disk = useMemo(
    () => stackDiskUsage(summary?.total_bytes ?? 0, summary?.volumes ?? []),
    [summary?.total_bytes, summary?.volumes],
  );

  const setLocation = useCallback((nextRoot: string, nextPath = "") => {
    setSelected([]);
    setFilter("");
    if (!nextRoot) {
      setParams({});
      return;
    }
    const next: Record<string, string> = { root: nextRoot };
    if (nextPath) next.path = nextPath;
    setParams(next);
  }, [setParams]);

  const refreshBrowse = () => {
    void queryClient.invalidateQueries({ queryKey: ["site-files-browse"] });
  };

  const refresh = useMutation({
    mutationFn: () => fetchFileSummary(true),
    onSuccess: (data) => {
      queryClient.setQueryData(["site-files-summary"], data);
      refreshBrowse();
      message.success("已重新扫描磁盘占用");
    },
    onError: (e: unknown) => message.error(apiError(e, "扫描失败")),
  });

  const download = useMutation({
    mutationFn: (rel: string) => downloadManagedFile(rootId, rel),
    onError: (e: unknown) => message.error(apiError(e, "下载失败")),
  });

  const run = async (task: () => Promise<FileOk | void>, ok: string) => {
    try {
      const result = await task();
      if (result && result.kept_sensitive) {
        message.success("已删除，敏感项已保留");
      } else {
        message.success(ok);
      }
      setSelected([]);
      refreshBrowse();
      return true;
    } catch (e: unknown) {
      message.error(apiError(e, "操作失败"));
      return false;
    }
  };

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

  const openEntry = (row: BrowserRow) => {
    if (isFileBrowseLocked(row)) return;
    if (row.name === "..") {
      const next = fileBrowseUp(rootId, path);
      setLocation(next.root || "install", next.path);
      return;
    }
    if (row.browseRootId) {
      setLocation(row.browseRootId, "");
      return;
    }
    if (row.is_dir) {
      setLocation(rootId, joinFileRel(path, row.name));
    }
  };

  const openEditor = async (row: BrowserRow) => {
    const rel = joinFileRel(path, row.name);
    try {
      const res = await fetchManagedFileContents(rootId, rel);
      setEditor({
        mode: "edit",
        name: row.name,
        content: res.content,
        path: rel,
      });
      editorForm.setFieldsValue({ name: row.name, content: res.content });
    } catch (e: unknown) {
      message.error(apiError(e, "无法读取文件"));
    }
  };

  const onNameClick = (row: BrowserRow) => {
    if (row.is_dir) {
      openEntry(row);
      return;
    }
    if (row.editable && !isFileBrowseLocked(row)) {
      void openEditor(row);
    }
  };

  const confirmDelete = (names: string[]) => {
    Modal.confirm({
      title: names.length === 1 ? `删除 ${names[0]}？` : `删除 ${names.length} 项？`,
      content: "删除后无法从这里恢复。目录里的敏感文件会留下。",
      okText: "删除",
      okButtonProps: { danger: true },
      onOk: () => run(() => deleteManagedFiles(rootId, path, names), "已删除"),
    });
  };

  const saveEditor = useMutation({
    mutationFn: async () => {
      const values = await editorForm.validateFields();
      if (editor?.mode === "create") {
        return createManagedFile(rootId, path, values.name, values.content);
      }
      const rel = editor?.path || joinFileRel(path, values.name);
      return writeManagedFile(rootId, rel, values.content);
    },
    onSuccess: () => {
      message.success(editor?.mode === "create" ? "已创建" : "已保存");
      setEditor(null);
      refreshBrowse();
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const browserRows: BrowserRow[] = useMemo(() => {
    const entries = browseQuery.data?.entries || [];
    const q = filter.trim().toLowerCase();
    const filtered = q
      ? entries.filter((row) => row.name.toLowerCase().includes(q))
      : entries;
    const rows: BrowserRow[] = filtered.map((row) => ({
      ...row,
      key: row.name,
    }));
    if (path && !q) {
      rows.unshift({
        key: "..",
        name: "..",
        is_dir: true,
        size: 0,
        modified_at: null,
        sensitive: false,
        downloadable: false,
        editable: false,
      });
    }
    return rows;
  }, [browseQuery.data?.entries, filter, path]);

  const crumbs = useMemo(() => {
    const rootLabel =
      browseQuery.data?.root_label ||
      roots.find((row) => row.id === rootId)?.label ||
      "安装根";
    const items = [
      {
        title: (
          <Button type="link" size="small" onClick={() => setLocation(rootId, "")}>
            {rootLabel}
          </Button>
        ),
      },
    ];
    const parts = path ? path.split("/").filter(Boolean) : [];
    let acc = "";
    for (const part of parts) {
      acc = joinFileRel(acc, part);
      const target = acc;
      items.push({
        title: (
          <Button type="link" size="small" onClick={() => setLocation(rootId, target)}>
            {part}
          </Button>
        ),
      });
    }
    return items;
  }, [browseQuery.data?.root_label, path, rootId, roots, setLocation]);

  const rowMenu = (row: BrowserRow): MenuProps["items"] => {
    if (row.name === ".." || isFileBrowseLocked(row)) return [];
    const items: MenuProps["items"] = [];
    if (row.is_dir) {
      items.push({
        key: "open",
        label: "打开",
        onClick: () => openEntry(row),
      });
    } else if (row.editable) {
      items.push({
        key: "edit",
        icon: <EditOutlined />,
        label: "编辑",
        onClick: () => void openEditor(row),
      });
    }
    if (row.downloadable) {
      items.push({
        key: "download",
        icon: <DownloadOutlined />,
        label: "下载",
        onClick: () => download.mutate(joinFileRel(path, row.name)),
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

  const fileColumns: ColumnsType<BrowserRow> = [
    {
      title: "名称",
      dataIndex: "name",
      ellipsis: true,
      render: (name: string, row) => {
        const locked = isFileBrowseLocked(row);
        const clickable = row.is_dir ? !locked : Boolean(row.editable && !locked);
        const inner = (
          <Space>
            {row.is_dir ? <FolderOutlined /> : <FileOutlined />}
            {name}
            {row.sensitive ? <Tag>敏感</Tag> : null}
            {row.missing ? <Tag>不存在</Tag> : null}
          </Space>
        );
        if (!clickable) {
          return (
            <Typography.Text
              type={locked ? "secondary" : undefined}
              style={locked ? { color: token.colorTextDisabled } : undefined}
            >
              {inner}
            </Typography.Text>
          );
        }
        return (
          <Button
            type="link"
            size="small"
            style={{ padding: 0, height: "auto" }}
            onClick={() => onNameClick(row)}
          >
            {inner}
          </Button>
        );
      },
    },
    {
      title: "大小",
      dataIndex: "size",
      width: 110,
      render: (n: number, row) =>
        row.is_dir || row.name === ".." ? "—" : formatBytes(n),
    },
    {
      title: "修改时间",
      dataIndex: "modified_at",
      width: 180,
      render: (value: string | null) =>
        value ? formatBeijing(value, "YYYY-MM-DD HH:mm") : "—",
    },
    {
      title: "",
      key: "actions",
      width: 108,
      render: (_, row) => {
        if (row.name === "..") return null;
        return (
          <Space size={0}>
            {row.downloadable ? (
              <Button
                type="link"
                size="small"
                icon={<DownloadOutlined />}
                loading={download.isPending}
                onClick={() => download.mutate(joinFileRel(path, row.name))}
              >
                下载
              </Button>
            ) : null}
            {isFileBrowseLocked(row) ? null : (
              <Dropdown menu={{ items: rowMenu(row) }} trigger={["click"]}>
                <Button type="text" size="small" icon={<MoreOutlined />} />
              </Dropdown>
            )}
          </Space>
        );
      },
    },
  ];

  const selectedMutable = selected.filter((name) => {
    const row = browserRows.find((item) => item.name === name);
    return row && row.name !== ".." && !isFileBrowseLocked(row);
  });

  return (
    <>
      <PageHeader
        title="文件管理"
        subtitle="查看本站磁盘占用，并在安装根内增删改查。敏感项置灰，不可进入、下载、修改或删除。"
        extra={
          <Button
            icon={<ReloadOutlined />}
            loading={refresh.isPending || summaryQuery.isFetching}
            onClick={() => refresh.mutate()}
          >
            重新扫描
          </Button>
        }
      />
      {summaryQuery.isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message={apiError(summaryQuery.error, "无法读取磁盘占用")}
        />
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }} align="stretch">
        {summaryCards.map((card) => (
          <Col
            key={card.key}
            flex="1 1 0"
            style={{ minWidth: 168, display: "flex" }}
          >
            <Card size="small" style={{ width: "100%", height: "100%" }}>
              <Statistic
                title={card.title}
                value={card.value}
                formatter={(value) => formatBytes(Number(value))}
                loading={summaryQuery.isLoading}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {disk ? (
        <Card
          size="small"
          title="磁盘占用"
          extra={
            <Typography.Text type="secondary">
              已用 {formatBytes(disk.siteBytes + disk.otherBytes)} /{" "}
              {formatBytes(disk.totalBytes)}
              {` · ${formatPercent(disk.siteBytes + disk.otherBytes, disk.totalBytes)}%`}
              {summary?.measured_at
                ? ` · ${formatBeijing(summary.measured_at, "HH:mm:ss")}`
                : ""}
            </Typography.Text>
          }
          style={{ marginBottom: 16 }}
        >
          <div
            role="img"
            aria-label={`本站已使用 ${formatBytes(disk.siteBytes)}，其他文件 ${formatBytes(disk.otherBytes)}，剩余 ${formatBytes(disk.freeBytes)}，共 ${formatBytes(disk.totalBytes)}`}
            style={{
              display: "flex",
              height: 12,
              overflow: "hidden",
              borderRadius: token.borderRadiusSM,
              background: token.colorFillSecondary,
            }}
          >
            {disk.siteBytes > 0 ? (
              <div
                title={`本站已使用 ${formatBytes(disk.siteBytes)}`}
                style={{
                  flexGrow: disk.siteBytes,
                  flexShrink: 0,
                  flexBasis: 0,
                  minWidth: 2,
                  background: token.colorPrimary,
                }}
              />
            ) : null}
            {disk.otherBytes > 0 ? (
              <div
                title={`其他文件 ${formatBytes(disk.otherBytes)}`}
                style={{
                  flexGrow: disk.otherBytes,
                  flexShrink: 0,
                  flexBasis: 0,
                  minWidth: 2,
                  background: token.colorTextTertiary,
                }}
              />
            ) : null}
            {disk.freeBytes > 0 ? (
              <div
                title={`剩余 ${formatBytes(disk.freeBytes)}`}
                style={{
                  flexGrow: disk.freeBytes,
                  flexShrink: 0,
                  flexBasis: 0,
                }}
              />
            ) : null}
          </div>
          <Space wrap size={[16, 8]} style={{ marginTop: 12 }}>
            <DiskStackLegend
              color={token.colorPrimary}
              border={token.colorBorder}
              label="本站已使用"
              value={disk.siteBytes}
            />
            <DiskStackLegend
              color={token.colorTextTertiary}
              border={token.colorBorder}
              label="其他文件"
              value={disk.otherBytes}
            />
            <DiskStackLegend
              color={token.colorFillSecondary}
              border={token.colorBorder}
              label="剩余"
              value={disk.freeBytes}
            />
          </Space>
          {disk.path ? (
            <Typography.Text
              type="secondary"
              style={{ display: "block", marginTop: 8 }}
            >
              {disk.path}
            </Typography.Text>
          ) : null}
        </Card>
      ) : null}

      <Card
        size="small"
        title="目录"
        extra={
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
                  await uploadManagedFile(rootId, path, file, (percent) => {
                    patchUpload(uid, {
                      percent: percent ?? null,
                      phase: percent === 100 ? "writing" : "uploading",
                    });
                    options.onProgress?.({ percent: percent ?? 0 });
                  });
                  patchUpload(uid, { percent: 100, phase: "done" });
                  options.onSuccess?.(null);
                  message.success(`已上传 ${file.name}`);
                  refreshBrowse();
                  scheduleDismiss(uid);
                } catch (e: unknown) {
                  patchUpload(uid, { phase: "error" });
                  options.onError?.(e as Error);
                  message.error(apiError(e, `上传 ${file.name} 失败`));
                }
              }}
            >
              <Button size="small" icon={<UploadOutlined />}>
                上传
              </Button>
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
              danger
              disabled={!selectedMutable.length}
              icon={<DeleteOutlined />}
              onClick={() => confirmDelete(selectedMutable)}
            >
              删除
            </Button>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => browseQuery.refetch()}
            >
              刷新
            </Button>
          </Space>
        }
      >
        <Space
          style={{ marginBottom: 12, width: "100%", justifyContent: "space-between" }}
          wrap
        >
          <Breadcrumb items={crumbs} />
          <Space wrap>
            {rootId && browseQuery.data?.abs_path ? (
              <Typography.Text type="secondary" copyable>
                {browseQuery.data.abs_path}
              </Typography.Text>
            ) : null}
            <Input.Search
              size="small"
              allowClear
              placeholder="筛选当前目录"
              style={{ width: 220 }}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </Space>
        </Space>
        {uploads.length > 0 ? (
          <div style={{ marginBottom: 12, display: "flex", flexDirection: "column", gap: 8 }}>
            {uploads.map((job) => (
              <div
                key={job.uid}
                style={{
                  border: `1px solid ${token.colorBorderSecondary}`,
                  borderRadius: token.borderRadius,
                  padding: "8px 12px",
                }}
              >
                <Space style={{ width: "100%", justifyContent: "space-between" }}>
                  <Typography.Text ellipsis style={{ maxWidth: 360 }} title={job.name}>
                    {job.name}
                  </Typography.Text>
                  <Space size={8}>
                    <Typography.Text type="secondary">
                      {formatBytes(job.size)}
                    </Typography.Text>
                    {job.phase === "done" || job.phase === "error" ? (
                      <Button
                        type="text"
                        size="small"
                        icon={<CloseOutlined />}
                        onClick={() => dismissUpload(job.uid)}
                      />
                    ) : null}
                  </Space>
                </Space>
                <Progress
                  percent={managedUploadProgressPercent(job.phase, job.percent)}
                  status={uploadJobStatus(job.phase)}
                  showInfo={false}
                  size="small"
                />
                <Typography.Text
                  type={job.phase === "error" ? "danger" : "secondary"}
                  style={{ fontSize: 12 }}
                >
                  {managedUploadJobLabel(job.phase, job.percent)}
                </Typography.Text>
              </div>
            ))}
          </div>
        ) : null}
        {rootId && browseQuery.isError ? (
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 12 }}
            message={apiError(browseQuery.error, "无法列出目录")}
          />
        ) : null}
        <Table
          size="small"
          rowKey="key"
          loading={browseQuery.isFetching}
          dataSource={browserRows}
          columns={fileColumns}
          pagination={{ pageSize: 50, hideOnSinglePage: true }}
          rowSelection={{
            selectedRowKeys: selected,
            onChange: (keys) =>
              setSelected(
                keys
                  .map(String)
                  .filter((name) => {
                    const row = browserRows.find((item) => item.name === name);
                    return Boolean(
                      row && row.name !== ".." && !isFileBrowseLocked(row),
                    );
                  }),
              ),
            getCheckboxProps: (row) => ({
              disabled: row.name === ".." || isFileBrowseLocked(row),
            }),
          }}
          onRow={(row) => ({
            style: row.sensitive
              ? { opacity: 0.45, color: token.colorTextDisabled }
              : undefined,
            onDoubleClick: () => {
              if (row.is_dir && !isFileBrowseLocked(row)) openEntry(row);
            },
          })}
        />
      </Card>

      <Modal
        title="新建目录"
        open={folderOpen}
        onCancel={() => setFolderOpen(false)}
        onOk={async () => {
          const values = await folderForm.validateFields();
          const ok = await run(
            () => createManagedFolder(rootId, path, values.name),
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
            <Input placeholder="logs" />
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
            () => renameManagedFile(rootId, path, renameRow.name, values.dest),
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

      <Modal
        title={editor?.mode === "create" ? "新建文件" : `编辑 ${editor?.name || ""}`}
        open={Boolean(editor)}
        width={840}
        confirmLoading={saveEditor.isPending}
        onCancel={() => setEditor(null)}
        okText="保存"
        onOk={() => saveEditor.mutate()}
      >
        <Form form={editorForm} layout="vertical">
          <Form.Item
            name="name"
            label="文件名"
            rules={[{ required: true, message: "请输入文件名" }]}
          >
            <Input
              disabled={editor?.mode === "edit"}
              placeholder="notes.txt"
            />
          </Form.Item>
          <Form.Item name="content" label="内容">
            <Input.TextArea
              rows={18}
              style={{
                fontFamily:
                  "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                fontSize: 13,
              }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

function DiskStackLegend({
  color,
  border,
  label,
  value,
}: {
  color: string;
  border: string;
  label: string;
  value: number;
}) {
  return (
    <Space size={6}>
      <span
        aria-hidden
        style={{
          display: "inline-block",
          width: 10,
          height: 10,
          borderRadius: 2,
          background: color,
          boxShadow: `inset 0 0 0 1px ${border}`,
        }}
      />
      <Typography.Text type="secondary">
        {label} {formatBytes(value)}
      </Typography.Text>
    </Space>
  );
}
