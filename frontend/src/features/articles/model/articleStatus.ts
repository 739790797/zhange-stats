export const ARTICLE_STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  published: "已发布",
};

export function articleStatusLabel(status: string): string {
  return ARTICLE_STATUS_LABEL[status] || status;
}

export function articleStatusColor(
  status: string,
): "default" | "success" {
  if (status === "published") return "success";
  return "default";
}
