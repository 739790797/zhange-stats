import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Table,
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

type FormValues = {
  name: string;
  slug?: string;
  sort_order: number;
};

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
    form.setFieldsValue({ name: "", slug: "", sort_order: 0 });
    setOpen(true);
  };

  const openEdit = (row: ArticleCategory) => {
    setEditing(row);
    form.setFieldsValue({
      name: row.name,
      slug: row.slug,
      sort_order: row.sort_order ?? 0,
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
          { title: "短链", dataIndex: "slug", width: 160 },
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
          <Form.Item name="sort_order" label="排序" extra="数字越小越靠前">
            <InputNumber min={0} max={9999} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
