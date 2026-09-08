import { SettingOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Form,
  Input,
  Modal,
  Result,
  Select,
  Spin,
  Tooltip,
  message,
} from "antd";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  createArticle,
  fetchAdminArticle,
  fetchArticleCapabilities,
  fetchArticleCategories,
  patchArticle,
  uploadArticleAsset,
  type ArticleDetail,
} from "@/api/articlesApi";
import { ArticleComposer } from "@/components/articles/ArticleComposer";
import "@/components/articles/articleRichtext.css";
import styles from "@/components/articles/TavernEdit.module.css";
import { apiError } from "@/lib/apiError";
import {
  articleCategoryOptionLabel,
  selectableArticleCategories,
} from "@/lib/articleCategory";
import {
  ARTICLE_AUTOSAVE_MS,
  EMPTY_ARTICLE_FORM,
  articleDraftIsDirty,
  articleDraftSnapshot,
  articleEditorFormValues,
  autosaveTitle,
  autosaveWriteStatus,
  canAutosaveDraft,
} from "@/lib/articleDraft";
import {
  articleAttachmentLabel,
  classifyArticleUpload,
  rejectArticleUploadFile,
  type ArticleUploadedAsset,
} from "@/lib/articleImages";
import { nowBeijing } from "@/lib/time";
import { TAVERN_PATH, tavernEditPath } from "@/lib/tavernNav";
import { useDocumentTitle } from "@/lib/documentTitle";

type FormValues = {
  title: string;
  slug?: string;
  summary?: string;
  body: string;
  body_format: "markdown" | "html";
  status: "draft" | "published";
  category_ids: number[];
  tag_ids: number[];
  cover_url?: string;
};

type SavePayload = FormValues & { silent?: boolean };

export default function TavernEditPage() {
  const { articleId } = useParams();
  const isNew = !articleId || articleId === "new";
  const id = isNew ? null : Number(articleId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const title = Form.useWatch("title", form) || "";
  useDocumentTitle(isNew ? "写文章" : title.trim() || "编辑文章");
  const body = Form.useWatch("body", form) || "";
  const bodyFormat = Form.useWatch("body_format", form) || "html";
  const coverUrl = Form.useWatch("cover_url", form) || "";
  const slug = Form.useWatch("slug", form) || "";
  const summary = Form.useWatch("summary", form) || "";
  const categoryIds = Form.useWatch("category_ids", form);
  const tagIds = Form.useWatch("tag_ids", form);
  const [uploading, setUploading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [saveHint, setSaveHint] = useState("");
  const [toolbarHost, setToolbarHost] = useState<HTMLDivElement | null>(null);
  const persistRef = useRef<(status: "draft" | "published") => Promise<void>>(
    async () => undefined,
  );
  const persistedId = useRef<number | null>(id);
  const hydratedId = useRef<number | null>(null);
  const savedSnap = useRef(articleDraftSnapshot({}));
  const createLock = useRef<Promise<ArticleDetail> | null>(null);
  const autosaveCtx = useRef({
    canWrite: false,
    isNew: true,
    articleStatus: undefined as string | undefined,
    articleId: null as number | null,
    savePending: false,
    uploading: false,
    mutate: ((_payload: SavePayload) => undefined) as (payload: SavePayload) => void,
  });

  const uploadImages = async (files: File[]): Promise<ArticleUploadedAsset[]> => {
    const accepted: File[] = [];
    for (const file of files) {
      const reason = rejectArticleUploadFile(file);
      if (reason) {
        message.error(`${file.name || "文件"}：${reason}`);
        continue;
      }
      accepted.push(file);
    }
    if (!accepted.length) return [];
    setUploading(true);
    try {
      const rows: ArticleUploadedAsset[] = [];
      for (const file of accepted) {
        const kind = classifyArticleUpload(file) || "file";
        const res = await uploadArticleAsset(file);
        rows.push({
          url: res.url,
          name: articleAttachmentLabel(file.name),
          kind,
        });
      }
      return rows;
    } catch (e) {
      message.error(apiError(e, "上传失败"));
      return [];
    } finally {
      setUploading(false);
    }
  };

  const capQuery = useQuery({
    queryKey: ["article-capabilities"],
    queryFn: fetchArticleCapabilities,
  });
  const detailQuery = useQuery({
    queryKey: ["article-editor", id],
    queryFn: () => fetchAdminArticle(id as number),
    enabled: id != null && !Number.isNaN(id),
  });
  const catsQuery = useQuery({
    queryKey: ["article-categories"],
    queryFn: fetchArticleCategories,
  });

  const saveMut = useMutation({
    mutationFn: async (values: SavePayload) => {
      const payload = {
        title: values.title,
        slug: values.slug || null,
        summary: values.summary || "",
        body: values.body || "",
        body_format: "html",
        status: values.status,
        category_ids: values.category_ids || [],
        tag_ids: values.tag_ids || [],
        cover_url: values.cover_url || null,
      };
      const target = persistedId.current;
      if (target == null) {
        if (!createLock.current) {
          createLock.current = createArticle(payload)
            .then((saved) => {
              persistedId.current = saved.id;
              return saved;
            })
            .finally(() => {
              createLock.current = null;
            });
          return createLock.current;
        }
        const inFlight = createLock.current;
        return inFlight.then((saved) => {
          persistedId.current = saved.id;
          return patchArticle(saved.id, payload);
        });
      }
      return patchArticle(target, payload);
    },
    onSuccess: (saved, values) => {
      persistedId.current = saved.id;
      const latest = articleDraftSnapshot(form.getFieldsValue(true));
      savedSnap.current = latest;
      setSaveHint(
        values.silent
          ? `已自动保存 ${nowBeijing().format("HH:mm")}`
          : `已保存 ${nowBeijing().format("HH:mm")}`,
      );
      if (!values.silent) {
        message.success(saved.status === "published" ? "已发布" : "已保存");
      }
      queryClient.setQueryData(["article-editor", saved.id], {
        ...saved,
        title: latest.title || saved.title,
        slug: latest.slug || saved.slug,
        summary: latest.summary,
        body: latest.body,
        body_format: latest.body_format,
        cover_url: latest.cover_url || null,
      });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["articles-mine"] });
      queryClient.invalidateQueries({ queryKey: ["articles-admin"] });
      queryClient.invalidateQueries({ queryKey: ["article-versions", saved.id] });
      if (!values.silent) {
        queryClient.invalidateQueries({ queryKey: ["article-editor", saved.id] });
      }
      if (id == null) {
        navigate(tavernEditPath(saved.id), { replace: true });
      }
    },
    onError: (e) => message.error(apiError(e, "保存失败")),
  });

  const initial = detailQuery.data;
  const canAdmin = Boolean(capQuery.data?.can_admin);
  const canWrite = Boolean(capQuery.data?.can_write);

  useEffect(() => {
    if (id != null) persistedId.current = id;
  }, [id]);

  useEffect(() => {
    if (!initial) return;
    if (hydratedId.current === initial.id) return;
    const values = articleEditorFormValues(initial);
    form.setFieldsValue(values);
    savedSnap.current = articleDraftSnapshot(values);
    hydratedId.current = initial.id;
  }, [form, initial]);

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (
        !articleDraftIsDirty(
          articleDraftSnapshot(form.getFieldsValue(true)),
          savedSnap.current,
        )
      ) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [form]);

  const savePending = saveMut.isPending;
  const silentSaving = savePending && Boolean(saveMut.variables?.silent);
  autosaveCtx.current = {
    canWrite,
    isNew,
    articleStatus: initial?.status,
    articleId: initial?.id ?? null,
    savePending,
    uploading,
    mutate: saveMut.mutate,
  };

  useEffect(() => {
    const ctx = autosaveCtx.current;
    if (!ctx.canWrite || !capQuery.isSuccess) return;
    if (!ctx.isNew && (ctx.articleId == null || hydratedId.current !== ctx.articleId)) {
      return;
    }
    if (ctx.savePending || ctx.uploading) return;
    const snap = articleDraftSnapshot({
      title,
      slug,
      summary,
      body,
      body_format: bodyFormat,
      category_ids: categoryIds,
      tag_ids: tagIds,
      cover_url: coverUrl,
    });
    if (!articleDraftIsDirty(snap, savedSnap.current)) return;
    const timer = window.setTimeout(() => {
      const latest = autosaveCtx.current;
      if (latest.savePending || latest.uploading || !latest.canWrite) {
        return;
      }
      const values = form.getFieldsValue(true);
      const next = articleDraftSnapshot(values);
      if (!articleDraftIsDirty(next, savedSnap.current)) return;
      const nextTitle = autosaveTitle(values.title || "");
      if (!values.title?.trim()) {
        form.setFieldValue("title", nextTitle);
      }
      setSaveHint("正在保存…");
      latest.mutate({
        ...values,
        title: nextTitle,
        status: autosaveWriteStatus(latest.articleStatus),
        silent: true,
      });
    }, ARTICLE_AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
  }, [
    title,
    body,
    bodyFormat,
    coverUrl,
    slug,
    summary,
    categoryIds,
    tagIds,
    capQuery.isSuccess,
    canWrite,
    isNew,
    savePending,
    uploading,
    form,
  ]);

  const persist = async (status: "draft" | "published") => {
    if (savePending) return;
    if (status === "published") {
      try {
        const values = await form.validateFields();
        saveMut.mutate({ ...form.getFieldsValue(true), ...values, status });
      } catch {
        const cats = form.getFieldValue("category_ids") || [];
        if (!cats.length) {
          setSettingsOpen(true);
          message.warning("请选择分类");
        }
      }
      return;
    }
    const values = form.getFieldsValue(true);
    const snap = articleDraftSnapshot(values);
    if (!canAutosaveDraft(snap)) {
      message.warning("请先写标题或正文");
      return;
    }
    if (!articleDraftIsDirty(snap, savedSnap.current)) {
      message.success("已保存");
      return;
    }
    const nextTitle = autosaveTitle(values.title || "");
    if (!values.title?.trim()) {
      form.setFieldValue("title", nextTitle);
    }
    saveMut.mutate({ ...values, title: nextTitle, status: "draft" });
  };
  persistRef.current = persist;

  if (!isNew && detailQuery.isLoading) {
    return (
      <div className={styles.loading}>
        <Spin />
      </div>
    );
  }

  if (capQuery.isSuccess && !canWrite) {
    return (
      <div className={styles.guard}>
        <Result
          status="403"
          title="没有发文权限"
          extra={
            <Button onClick={() => navigate(TAVERN_PATH)}>返回酒馆</Button>
          }
        />
      </div>
    );
  }

  return (
    <Form<FormValues>
      form={form}
      layout="vertical"
      className={styles.page}
      onFinish={() => undefined}
      initialValues={
        isNew || !initial ? EMPTY_ARTICLE_FORM : articleEditorFormValues(initial)
      }
    >
      <Form.Item name="slug" hidden>
        <Input />
      </Form.Item>
      <Form.Item name="tag_ids" hidden>
        <Select mode="multiple" />
      </Form.Item>
      <Form.Item name="cover_url" hidden>
        <Input />
      </Form.Item>
      <div className={styles.stickyStack}>
      <header className={styles.topbar}>
        <Link className={styles.crumb} to={TAVERN_PATH}>
          战鸽酒馆
        </Link>
        <span className={styles.crumbNow}>
          {isNew ? "写文章" : "编辑"}
        </span>
        <div className={styles.topbarActions}>
            <Button icon={<SettingOutlined />} onClick={() => setSettingsOpen(true)}>
              设置
            </Button>
            <Tooltip title="保存（Ctrl+S）">
            <Button
              loading={saveMut.isPending && !silentSaving}
              onClick={() => {
                void persist("draft").catch(() => undefined);
              }}
            >
              保存
            </Button>
            </Tooltip>
            <Button
              type="primary"
              loading={saveMut.isPending && !silentSaving}
              onClick={() => {
                void persist("published").catch(() => undefined);
              }}
            >
              发布
            </Button>
          </div>
      </header>
      <div className={styles.belowBar}>
        {saveHint ? <p className={styles.saveHint}>{saveHint}</p> : null}
        <div className={styles.formatbar} ref={setToolbarHost} />
      </div>
      </div>

          <div className={`${styles.sheet} ${styles.sheetAttached}`}>
            <Form.Item
              name="title"
              className={styles.titleItem}
              rules={[{ required: true, message: "请填写标题" }]}
            >
              <Input
                className={styles.titleInput}
                bordered={false}
                maxLength={200}
                placeholder="请输入标题"
              />
            </Form.Item>
            <Form.Item name="body_format" hidden>
              <Input />
            </Form.Item>
            <Form.Item name="body" className={styles.bodyItem}>
              <ArticleComposer
                key={isNew ? "new" : String(id)}
                format={bodyFormat === "markdown" ? "markdown" : "html"}
                disabled={uploading}
                uploadFiles={uploadImages}
                toolbarHost={toolbarHost}
                onSave={() => {
                  void persistRef.current("draft").catch(() => undefined);
                }}
              />
            </Form.Item>
          </div>

          <Modal
            title="设置"
            open={settingsOpen}
            onCancel={() => setSettingsOpen(false)}
            onOk={() =>
              form.validateFields(["category_ids"]).then(() => {
                setSettingsOpen(false);
              })
            }
            okText="完成"
            cancelText="关闭"
            width="min(560px, calc(100vw - 24px))"
            destroyOnClose={false}
          >
            <div className={styles.settingsForm}>
              <Form.Item
                name="category_ids"
                label="分类"
                layout="vertical"
                colon={false}
                rules={[
                  { required: true, message: "请选择分类" },
                  { type: "array", min: 1, message: "请选择分类" },
                ]}
              >
                <Select
                  mode="multiple"
                  placeholder="选择分类"
                  options={selectableArticleCategories(
                    catsQuery.data || [],
                    canAdmin,
                  ).map((c) => ({
                    value: c.id,
                    label: articleCategoryOptionLabel(c),
                  }))}
                />
              </Form.Item>
              <Form.Item
                name="summary"
                label="摘要"
                layout="vertical"
                colon={false}
              >
                <Input.TextArea rows={3} maxLength={512} />
              </Form.Item>
            </div>
          </Modal>
    </Form>
  );
}
