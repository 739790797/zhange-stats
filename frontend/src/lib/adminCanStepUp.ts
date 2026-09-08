export function adminCanStepUp(user: {
  email?: string | null;
  email_verified?: boolean;
} | null): boolean {
  return Boolean(user?.email && user.email_verified);
}
