import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  ColorPicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  message,
} from "antd";
import { useState } from "react";
import {
  createArticleCategory,
  deleteArticleCategory,
  fetchArticleCategories,
  patchArticleCategory,
  type ArticleCategory,
} from "@/api/articlesApi";
import { apiError } from "@/lib/apiError";
import { articleCategoryChipColor } from "@/lib/articleCategory";

type FormValues = {
  name: string;
  slug?: string;
  sort_order: number;
  admin_only: boolean;
  chip_color?: string | null;
};

function ChipColorField({
  value,
  onChange,
}: {
  value?: string | null;
  onChange?: (hex: string | null) => void;
}) {
  return (
    <ColorPicker
      value={value || undefined}
      allowClear
      disabledAlpha
      showText
      format="hex"
      onChange={(color, css) => {
        if (!color) {
          onChange?.(null);
          return;
        }
        const hex = typeof css === "string" && css.startsWith("#") ? css : color.toHexString();
        onChange?.(hex);
      }}
      onClear={() => onChange?.(null)}
    />
  );
}

export function TavernCategoryPanel() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const [editing, setEditing] = useState<ArticleCategory | null>(null);
  const [open, setOpen] = useState(false);

  const listQuery = useQuery({
    queryKey: ["article-categories"],
    queryFn: fetchArticleCategories,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["article-categories"] });
    queryClient.invalidateQueries({ queryKey: ["articles"] });
  };

  const saveMut = useMutation({
    mutationFn: async (values: FormValues) => {
      const body = {
        name: values.name.trim(),
        slug: values.slug?.trim() || null,
        sort_order: values.sort_order ?? 0,
        admin_only: Boolean(values.admin_only),
        chip_color: values.chip_color?.trim() || null,
      };
      if (editing) {
        return patchArticleCategory(editing.id, body);
      }
      return createArticleCategory(body);
    },
    onSuccess: () => {
      message.success(editing ? "已更新分类" : "已添加分类");
      invalidate();
      setOpen(false);
      setEditing(null);
      form.resetFields();
    },
    onError: (e) => message.error(apiError(e, "保存分类失败")),
  });

  const delMut = useMutation({
    mutationFn: deleteArticleCategory,
    onSuccess: () => {
      message.success("已删除分类");
      invalidate();
    },
    onError: (e) => message.error(apiError(e, "删除失败")),
  });

  const openCreate = () => {
    setEditing(null);
    form.setFieldsValue({
      name: "",
      slug: "",
      sort_order: 0,
      admin_only: false,
      chip_color: null,
    });
    setOpen(true);
  };

  const openEdit = (row: ArticleCategory) => {
    setEditing(row);
    form.setFieldsValue({
      name: row.name,
      slug: row.slug,
      sort_order: row.sort_order ?? 0,
      admin_only: Boolean(row.admin_only),
      chip_color: row.chip_color || null,
    });
    setOpen(true);
  };

  return (
    <div>
      <Button type="primary" onClick={openCreate} style={{ marginBottom: 16 }}>
        添加分类
      </Button>
      <Table
        rowKey="id"
        loading={listQuery.isLoading}
        dataSource={listQuery.data || []}
        pagination={false}
        columns={[
          { title: "名称", dataIndex: "name" },
          { title: "短链", dataIndex: "slug", width: 140 },
          {
            title: "芯片",
            width: 140,
            render: (_, row) => (
              <Tag color={articleCategoryChipColor(row)} style={{ marginInlineEnd: 0 }}>
                {row.name}
              </Tag>
            ),
          },
          {
            title: "权限",
            width: 120,
            render: (_, row) =>
              row.admin_only ? (
                <Tag color="gold">仅管理员</Tag>
              ) : (
                <Tag>作者可发</Tag>
              ),
          },
          { title: "排序", dataIndex: "sort_order", width: 80 },
          {
            title: "操作",
            width: 160,
            render: (_, row) => (
              <Space>
                <Button type="link" size="small" onClick={() => openEdit(row)}>
                  编辑
                </Button>
                <Popconfirm
                  title="删除这个分类？文章上的该分类会被去掉。"
                  onConfirm={() => delMut.mutate(row.id)}
                >
                  <Button type="link" size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal
        title={editing ? "编辑分类" : "添加分类"}
        open={open}
        confirmLoading={saveMut.isPending}
        okText="保存"
        cancelText="取消"
        onCancel={() => {
          setOpen(false);
          setEditing(null);
        }}
        onOk={() => form.submit()}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => saveMut.mutate(values)}
        >
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: "请填写分类名" }]}
          >
            <Input maxLength={64} placeholder="如：游戏攻略" />
          </Form.Item>
          <Form.Item
            name="slug"
            label="短链"
            extra="英文或拼音，筛选链接会用到。中文名请填写，例如 guides。"
            rules={[{ required: true, message: "请填写英文短链" }]}
          >
            <Input maxLength={191} placeholder="guides" />
          </Form.Item>
          <Form.Item
            name="admin_only"
            label="仅管理员可发"
            extra="勾选后，只有站点管理员能把文章标到这个分类，例如站点公告。"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <Form.Item
            name="chip_color"
            label="芯片颜色"
            extra="文章卡片上的分类芯片颜色。清空则用默认蓝。"
          >
            <ChipColorField />
          </Form.Item>
          <Form.Item name="sort_order" label="排序" extra="数字越小越靠前">
            <InputNumber min={0} max={9999} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
