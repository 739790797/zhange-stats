/** 与后端 User.is_admin_user 对齐：role === admin 或 is_admin。 */
export function isAdminUser(user: {
  is_admin?: boolean | null;
  role?: string | null;
} | null | undefined): boolean {
  if (!user) return false;
  return user.role === "admin" || Boolean(user.is_admin);
}
