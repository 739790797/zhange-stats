import { client } from "./http";
import type { components } from "./generated/schema";

export type ArticleListOut = components["schemas"]["ArticleListOut"];
export type ArticleListItem = components["schemas"]["ArticleListItemOut"];
export type ArticleDetail = components["schemas"]["ArticleDetailOut"];
export type ArticleComment = components["schemas"]["ArticleCommentOut"];
export type ArticleCategory = components["schemas"]["ArticleCategoryOut"];
export type ArticleTerm = components["schemas"]["ArticleTermOut"];
export type ArticleWriteIn = components["schemas"]["ArticleWriteIn"];
export type ArticlePatchIn = components["schemas"]["ArticlePatchIn"];
export type ArticleCommentCreateIn = components["schemas"]["ArticleCommentCreateIn"];
export type ArticleCategoryWriteIn = components["schemas"]["ArticleCategoryWriteIn"];
export type ArticleTagWriteIn = components["schemas"]["ArticleTagWriteIn"];
export type ArticleCapability = components["schemas"]["ArticleCapabilityOut"];
export type ArticleAuthor = components["schemas"]["ArticleAuthorOut"];
export type ArticleVersionListItem = components["schemas"]["ArticleVersionListItemOut"];
export type ArticleVersionDetail = components["schemas"]["ArticleVersionDetailOut"];
export type ArticleAuthorsPutIn = components["schemas"]["ArticleAuthorsPutIn"];
export type ArticleMathRecognizeOut =
  components["schemas"]["ArticleMathRecognizeOut"];

export async function fetchArticles(params?: {
  page?: number;
  page_size?: number;
  category?: string;
  tag?: string;
  q?: string;
  sort?: "latest" | "hot";
}) {
  const { data } = await client.get<ArticleListOut>("/articles", { params });
  return data;
}

export async function fetchAdminArticles(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}) {
  const { data } = await client.get<ArticleListOut>("/articles/admin", { params });
  return data;
}

export async function fetchArticle(slug: string) {
  const { data } = await client.get<ArticleDetail>(
    `/articles/${encodeURIComponent(slug)}`,
  );
  return data;
}

export async function fetchArticleComments(slug: string) {
  const { data } = await client.get<ArticleComment[]>(
    `/articles/${encodeURIComponent(slug)}/comments`,
  );
  return data;
}

export async function createArticleComment(
  slug: string,
  body: ArticleCommentCreateIn,
) {
  const { data } = await client.post<ArticleComment>(
    `/articles/${encodeURIComponent(slug)}/comments`,
    body,
  );
  return data;
}

export async function deleteArticleComment(slug: string, commentId: number) {
  await client.delete(
    `/articles/${encodeURIComponent(slug)}/comments/${commentId}`,
  );
}

export async function fetchArticleCategories() {
  const { data } = await client.get<ArticleCategory[]>("/articles/categories");
  return data;
}

export async function fetchArticleTags() {
  const { data } = await client.get<ArticleTerm[]>("/articles/tags");
  return data;
}

export async function createArticle(body: ArticleWriteIn) {
  const { data } = await client.post<ArticleDetail>("/articles", body);
  return data;
}

export async function fetchAdminArticle(articleId: number) {
  const { data } = await client.get<ArticleDetail>(`/articles/id/${articleId}`);
  return data;
}

export async function patchArticle(articleId: number, body: ArticlePatchIn) {
  const { data } = await client.patch<ArticleDetail>(
    `/articles/id/${articleId}`,
    body,
  );
  return data;
}

export async function deleteArticle(articleId: number) {
  await client.delete(`/articles/id/${articleId}`);
}

export async function uploadArticleAsset(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<{ url: string }>("/articles/assets", form, {
    timeout: 30000,
  });
  return data;
}

export async function recognizeArticleMath(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<ArticleMathRecognizeOut>(
    "/articles/math/recognize",
    form,
    { timeout: 120000 },
  );
  return data;
}

export async function createArticleCategory(body: ArticleCategoryWriteIn) {
  const { data } = await client.post<ArticleCategory>(
    "/articles/categories",
    body,
  );
  return data;
}

export async function patchArticleCategory(
  categoryId: number,
  body: ArticleCategoryWriteIn,
) {
  const { data } = await client.patch<ArticleCategory>(
    `/articles/categories/${categoryId}`,
    body,
  );
  return data;
}

export async function deleteArticleCategory(categoryId: number) {
  await client.delete(`/articles/categories/${categoryId}`);
}

export async function createArticleTag(body: ArticleTagWriteIn) {
  const { data } = await client.post<ArticleTerm>("/articles/tags", body);
  return data;
}

export async function fetchArticleCapabilities() {
  const { data } = await client.get<ArticleCapability>("/articles/capabilities");
  return data;
}

export async function fetchMineArticles(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}) {
  const { data } = await client.get<ArticleListOut>("/articles/mine", { params });
  return data;
}

export async function fetchArticleAuthors() {
  const { data } = await client.get<ArticleAuthor[]>("/articles/authors");
  return data;
}

export async function putArticleAuthors(body: ArticleAuthorsPutIn) {
  const { data } = await client.put<ArticleAuthor[]>("/articles/authors", body);
  return data;
}

export async function fetchArticleVersions(articleId: number) {
  const { data } = await client.get<ArticleVersionListItem[]>(
    `/articles/id/${articleId}/versions`,
  );
  return data;
}

export async function fetchArticleVersion(articleId: number, versionId: number) {
  const { data } = await client.get<ArticleVersionDetail>(
    `/articles/id/${articleId}/versions/${versionId}`,
  );
  return data;
}

export async function restoreArticleVersion(
  articleId: number,
  versionId: number,
) {
  const { data } = await client.post<ArticleDetail>(
    `/articles/id/${articleId}/versions/${versionId}/restore`,
  );
  return data;
}
