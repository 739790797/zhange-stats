/** 管理端侧栏 4 入口：站点设置 / 运行维护 / 任务管理 / 用户管理。都走 AdminHubLayout。 */

export type AdminHubId = "site" | "ops" | "jobs" | "users";

export type AdminHubTab = {
  path: string;
  label: string;
};

export type AdminHub = {
  id: AdminHubId;
  menuKey: string;
  label: string;
  /** 侧栏点击时的默认落地（无更新标记时）。 */
  path: string;
  tabs: AdminHubTab[];
};

export const ADMIN_USERS_PATH = "/settings/users";

export const ADMIN_HUBS: readonly AdminHub[] = [
  {
    id: "site",
    menuKey: "admin-site",
    label: "站点设置",
    path: "/settings/auth",
    tabs: [
      { path: "/settings/auth", label: "安全设置" },
      { path: "/settings/integrations", label: "集成密钥" },
      { path: "/settings/email", label: "邮箱设置" },
      { path: "/settings/ocr", label: "文字识别" },
    ],
  },
  {
    id: "ops",
    menuKey: "admin-ops",
    label: "运行维护",
    path: "/settings/runtime",
    tabs: [
      { path: "/settings/runtime", label: "运行环境" },
      { path: "/settings/rum", label: "用户等待" },
      { path: "/settings/system", label: "系统更新" },
      { path: "/settings/logs", label: "平台日志" },
      { path: "/settings/files", label: "文件管理" },
    ],
  },
  {
    id: "jobs",
    menuKey: "admin-jobs",
    label: "任务管理",
    path: "/settings/task-config",
    tabs: [
      { path: "/settings/task-config", label: "任务配置" },
      { path: "/settings/jobs", label: "任务调度" },
    ],
  },
  {
    id: "users",
    menuKey: ADMIN_USERS_PATH,
    label: "用户管理",
    path: ADMIN_USERS_PATH,
    tabs: [{ path: ADMIN_USERS_PATH, label: "用户管理" }],
  },
];

export const ADMIN_LEAF_PATHS: readonly string[] = ADMIN_HUBS.flatMap((hub) =>
  hub.tabs.map((tab) => tab.path),
);

function pathMatches(pathname: string, path: string): boolean {
  return pathname === path || pathname.startsWith(`${path}/`);
}

export function adminHubByPath(pathname: string): AdminHub | null {
  let best: { hub: AdminHub; len: number } | null = null;
  for (const hub of ADMIN_HUBS) {
    for (const tab of hub.tabs) {
      if (!pathMatches(pathname, tab.path)) continue;
      if (!best || tab.path.length > best.len) {
        best = { hub, len: tab.path.length };
      }
    }
  }
  return best?.hub ?? null;
}

export function adminHubTabPath(pathname: string): string | null {
  const hub = adminHubByPath(pathname);
  if (!hub) return null;
  const hit = hub.tabs
    .filter((tab) => pathMatches(pathname, tab.path))
    .sort((a, b) => b.path.length - a.path.length)[0];
  return hit?.path ?? hub.path;
}

export function adminMenuSelectedKey(pathname: string): string | null {
  return adminHubByPath(pathname)?.menuKey ?? null;
}

/** 同 Hub 内切 Tab 时外壳不重挂，避免 Tab 条跟着淡入。 */
export function adminPageMotionKey(pathname: string): string {
  return adminHubByPath(pathname)?.id ?? pathname;
}

/** 有待更新时侧栏「运行维护」落到系统更新 Tab。 */
export function adminOpsLandingPath(hasAppUpdate: boolean): string {
  return hasAppUpdate ? "/settings/system" : "/settings/runtime";
}
