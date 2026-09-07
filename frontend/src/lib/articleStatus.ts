export const ARTICLE_STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  published: "已发布",
  deleted: "已删除",
};

export function articleStatusLabel(status: string): string {
  return ARTICLE_STATUS_LABEL[status] || status;
}

export function articleStatusColor(
  status: string,
): "default" | "success" | "error" {
  if (status === "published") return "success";
  if (status === "deleted") return "error";
  return "default";
}
