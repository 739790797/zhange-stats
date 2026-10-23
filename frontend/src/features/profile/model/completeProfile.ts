export const COMPLETE_PROFILE_SKIP_KEY = "zhange-skip-complete-profile";

export function shouldPromptCompleteProfile(email?: string | null): boolean {
  if (email) return false;
  return sessionStorage.getItem(COMPLETE_PROFILE_SKIP_KEY) !== "1";
}
