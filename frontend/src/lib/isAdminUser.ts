/** 与后端 User.is_admin_user 对齐：只信 role === admin。 */
export function isAdminUser(user: {
  is_admin?: boolean | null;
  role?: string | null;
} | null | undefined): boolean {
  if (!user) return false;
  if (user.role === "admin") return true;
  // 旧持久化缓存可能只有派生字段、没有 role
  if (user.role == null || user.role === "") return Boolean(user.is_admin);
  return false;
}
