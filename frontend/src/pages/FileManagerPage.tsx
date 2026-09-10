import {
  DownloadOutlined,
  FileOutlined,
  FolderOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  Col,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
  theme,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  downloadManagedFile,
  fetchFileBrowse,
  fetchFileSummary,
  type FileBrowseEntry,
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
  stackDiskUsage,
  type FileKind,
} from "@/lib/fileManager";
import { formatBeijing } from "@/lib/time";

type BrowserRow = FileBrowseEntry & {
  key: string;
  browseRootId?: string;
  missing?: boolean;
};

export default function FileManagerPage() {
  const { token } = theme.useToken();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const rootId = params.get("root") || "install";
  const path = params.get("path") || "";

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
    if (!nextRoot) {
      setParams({});
      return;
    }
    const next: Record<string, string> = { root: nextRoot };
    if (nextPath) next.path = nextPath;
    setParams(next);
  }, [setParams]);

  const refresh = useMutation({
    mutationFn: () => fetchFileSummary(true),
    onSuccess: (data) => {
      queryClient.setQueryData(["site-files-summary"], data);
      void queryClient.invalidateQueries({ queryKey: ["site-files-browse"] });
      message.success("已重新扫描磁盘占用");
    },
    onError: (e: unknown) => message.error(apiError(e, "扫描失败")),
  });

  const download = useMutation({
    mutationFn: (rel: string) => downloadManagedFile(rootId, rel),
    onError: (e: unknown) => message.error(apiError(e, "下载失败")),
  });

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

  const browserRows: BrowserRow[] = useMemo(() => {
    const entries = browseQuery.data?.entries || [];
    const rows: BrowserRow[] = entries.map((row) => ({
      ...row,
      key: row.name,
    }));
    if (path) {
      rows.unshift({
        key: "..",
        name: "..",
        is_dir: true,
        size: 0,
        modified_at: null,
        sensitive: false,
        downloadable: false,
      });
    }
    return rows;
  }, [browseQuery.data?.entries, path]);

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

  const fileColumns: ColumnsType<BrowserRow> = [
    {
      title: "名称",
      dataIndex: "name",
      ellipsis: true,
      render: (name: string, row) => {
        const locked = isFileBrowseLocked(row);
        const inner = (
          <Space>
            {row.is_dir ? <FolderOutlined /> : <FileOutlined />}
            {name}
            {row.sensitive ? <Tag>敏感</Tag> : null}
            {row.missing ? <Tag>不存在</Tag> : null}
          </Space>
        );
        if (locked || !row.is_dir) {
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
            onClick={() => openEntry(row)}
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
      width: 88,
      render: (_, row) =>
        row.downloadable ? (
          <Button
            type="link"
            size="small"
            icon={<DownloadOutlined />}
            loading={download.isPending}
            onClick={() => download.mutate(joinFileRel(path, row.name))}
          >
            下载
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="文件管理"
        subtitle="查看本站运行时、模型、缓存与依赖的磁盘占用，并浏览安装根。敏感项置灰，不可进入、不可下载。"
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

      <Card size="small" title="目录">
        <Space
          style={{ marginBottom: 12, width: "100%", justifyContent: "space-between" }}
          wrap
        >
          <Breadcrumb items={crumbs} />
          {rootId && browseQuery.data?.abs_path ? (
            <Typography.Text type="secondary" copyable>
              {browseQuery.data.abs_path}
            </Typography.Text>
          ) : null}
        </Space>
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
