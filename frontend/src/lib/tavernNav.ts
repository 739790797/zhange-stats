export const TAVERN_PATH = "/tavern";
export const TAVERN_ADMIN_PATH = "/tavern/admin";
export const TAVERN_WRITE_PATH = "/tavern/write";
export const TAVERN_FEATURE_ID = "tavern";
export const TAVERN_WELCOME_SLUG = "welcome";

export function tavernArticlePath(slug: string): string {
  return `${TAVERN_PATH}/${encodeURIComponent(slug)}`;
}

export function tavernEditPath(articleId: number): string {
  return `${TAVERN_WRITE_PATH}/${articleId}`;
}
