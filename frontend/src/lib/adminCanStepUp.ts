export type StepUpUser = {
  email?: string | null;
  email_verified?: boolean;
  admin_step_up_required?: boolean;
} | null;

export const ADMIN_STEP_UP_BLOCKED = "请先在个人中心绑定并验证邮箱";

/** 缺字段时当生产（仍要验证码），避免旧 /auth/me 误跳过。 */
export function adminStepUpRequired(user: StepUpUser): boolean {
  return user?.admin_step_up_required !== false;
}

export function adminCanStepUp(user: StepUpUser): boolean {
  if (!user) return false;
  if (!adminStepUpRequired(user)) return true;
  return Boolean(user.email && user.email_verified);
}

export function requestAdminStepUp(
  user: StepUpUser,
  handlers: {
    onNeedCode: () => void;
    onSkip: () => void;
    onBlocked?: () => void;
  },
): void {
  if (!adminCanStepUp(user)) {
    handlers.onBlocked?.();
    return;
  }
  if (!adminStepUpRequired(user)) {
    handlers.onSkip();
    return;
  }
  handlers.onNeedCode();
}
