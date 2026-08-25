import { FileOutlined, FolderOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Breadcrumb, Button, Modal, Table, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  fetchMinecraftFiles,
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

export function MinecraftConfigFilesModal({
  open,
  root,
  title,
  onClose,
}: {
  open: boolean;
  root: string;
  title?: string;
  onClose: () => void;
}) {
  const lockedRoot = normalizeMinecraftPath(root);
  const [directory, setDirectory] = useState(lockedRoot);
  const [editorPath, setEditorPath] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setEditorPath(null);
      return;
    }
    setDirectory(lockedRoot);
  }, [open, lockedRoot]);

  const listQuery = useQuery({
    queryKey: ["minecraft-files", directory],
    queryFn: () => fetchMinecraftFiles(directory),
    enabled: open && Boolean(lockedRoot),
    retry: 1,
  });

  const entries = useMemo(() => {
    const rows = listQuery.data?.entries || [];
    if (directory === lockedRoot) return rows;
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
  }, [listQuery.data, directory, lockedRoot]);

  const crumbs = useMemo(() => {
    const rootParts = lockedRoot.split("/").filter(Boolean);
    const parts = directory.split("/").filter(Boolean);
    const extra = parts.slice(rootParts.length);
    const items = [
      {
        title: (
          <Button
            type="link"
            size="small"
            style={{ padding: 0 }}
            onClick={() => setDirectory(lockedRoot)}
          >
            {lockedRoot}
          </Button>
        ),
      },
    ];
    extra.forEach((part, index) => {
      const path = normalizeMinecraftPath(
        `${lockedRoot}/${extra.slice(0, index + 1).join("/")}`,
      );
      items.push({
        title: (
          <Button
            type="link"
            size="small"
            style={{ padding: 0 }}
            onClick={() => setDirectory(path)}
          >
            {part}
          </Button>
        ),
      });
    });
    return items;
  }, [directory, lockedRoot]);

  const openFile = (row: MinecraftFileEntry) => {
    if (!isMinecraftTextFile(row)) {
      message.info("这个文件不能在这里编辑");
      return;
    }
    const path = joinMinecraftPath(directory, row.name);
    if (!isMinecraftPathWithin(lockedRoot, path)) {
      message.error("超出配置目录");
      return;
    }
    setEditorPath(path);
  };

  const openRow = (row: MinecraftFileEntry) => {
    if (row.name === "..") {
      setDirectory(parentMinecraftPathWithin(lockedRoot, directory));
      return;
    }
    if (!row.is_file) {
      const next = joinMinecraftPath(directory, row.name);
      if (!isMinecraftPathWithin(lockedRoot, next)) {
        message.error("超出配置目录");
        return;
      }
      setDirectory(next);
      return;
    }
    openFile(row);
  };

  return (
    <>
      <Modal
        title={title || "配置文件"}
        open={open && !editorPath}
        width={720}
        footer={null}
        onCancel={onClose}
      >
        <Breadcrumb items={crumbs} style={{ marginBottom: 12 }} />
        {listQuery.isError ? (
          <Typography.Text type="secondary">
            {apiError(listQuery.error, "还没有这个配置目录，写入预设后会出现。")}
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
      </Modal>
      <MinecraftPathFileEditor
        path={editorPath}
        onClose={() => setEditorPath(null)}
      />
    </>
  );
}

