export { client } from "./http";

export {
  login,
  register,
  sendRegisterCode,
  sendBindEmailCode,
  bindEmail,
  linkExistingAccount,
  verifyEmail,
  resendCode,
  fetchMe,
  fetchPasswordPolicy,
  changeOwnPassword,
  changeOwnUsername,
  startQqOAuthLogin,
  exchangeQqTicket,
} from "./authApi";

export {
  fetchMemberPlayStats,
  fetchSteamDay,
  fetchSteamNow,
  fetchSteamAppStore,
  fetchSteamAppIcon,
  triggerSteamPoll,
} from "./steamApi";

export {
  fetchUsers,
  createUser,
  updateUser,
  deleteUser,
  fetchMyProfile,
  startSteamOpenIdBind,
  startQqOAuthBind,
  unbindQq,
  updateMyProfile,
  uploadMyAvatar,
  uploadMemberAvatar,
  fetchMemberProfile,
  updateMemberProfile,
} from "./usersApi";

export type {
  EmailSettings,
  PlatformFeatureNode,
  PlatformFeaturesResponse,
  JobTriggerResult,
  CheckinLogItem,
  CheckinLogsPage,
  JobMemberOption,
  UserCheckinTask,
  UserCheckinTasksPage,
  IntegrationsSettings,
  IntegrationsStatus,
  AuthSettings,
} from "./settingsApi";

export {
  fetchEmailSettings,
  fetchPlatformFeaturesEffective,
  fetchPlatformFeaturesAdmin,
  updatePlatformFeatures,
  triggerScheduledJob,
  fetchJobCheckinLogs,
  fetchJobFilterMembers,
  fetchUserCheckinTasks,
  fetchMyDailyTasks,
  fetchMyDailyTaskLogs,
  fetchIntegrationsSettings,
  fetchIntegrationsStatus,
  updateIntegrationsSettings,
  fetchAuthSettings,
  updateAuthSettings,
  updateEmailSettings,
  testEmailSettings,
} from "./settingsApi";

export {
  fetchAppUpdateStatus,
  fetchAppUpdateReleases,
  checkAppUpdate,
  doAppUpdate,
  waitForHealthVersion,
} from "./appUpdateApi";
export type {
  AppUpdateStatus,
  AppUpdateRelease,
  AppUpdateCheckResult,
  AppUpdateDoResult,
} from "./appUpdateApi";

export { fetchRuntimeLogs, clearRuntimeLogs } from "./runtimeLogsApi";
export type {
  RuntimeLogLine,
  RuntimeLogsResult,
  FetchRuntimeLogsParams,
} from "./runtimeLogsApi";

export { fetchSetupStatus, completeSetupAdmin } from "./setupApi";
export type { SetupStatus, SetupAdminResult } from "./setupApi";

export {
  fetchSklandStatus,
  fetchEndfieldBox,
  fetchArknightsCompareCandidates,
  fetchArknightsBoxCompare,
  fetchArknightsAttendanceCalendar,
  fetchArknightsRogue,
  bindSklandPassword,
  sendSklandSms,
  bindSklandSms,
  unbindSkland,
  updateSklandBind,
  updateSklandRolePref,
  triggerSklandCheckin,
  startSklandQrBind,
  pollSklandQrBind,
} from "./sklandApi";

export {
  fetchTaygedoStatus,
  bindTaygedoPassword,
  sendTaygedoSms,
  bindTaygedoSms,
  unbindTaygedo,
  updateTaygedoBind,
  updateTaygedoRolePref,
  triggerTaygedoCheckin,
  fetchTaygedoAttendanceCalendar,
  fetchExastrisBox,
  fetchTaygedoExchange,
  exchangeTaygedoItem,
} from "./taygedoApi";

export {
  fetchExiliumStatus,
  bindExiliumPassword,
  sendExiliumSms,
  bindExiliumSms,
  unbindExilium,
  updateExiliumBind,
  updateExiliumRolePref,
  triggerExiliumCheckin,
  fetchExiliumExchange,
  exchangeExiliumItem,
} from "./exiliumApi";

export {
  fetchKujiequStatus,
  sendKujiequSms,
  bindKujiequSms,
  unbindKujiequ,
  updateKujiequBind,
  updateKujiequRolePref,
  triggerKujiequCheckin,
  fetchKujiequExchange,
  exchangeKujiequItem,
  fetchKujiequAttendanceCalendar,
  fetchWwBox,
} from "./kujiequApi";

export {
  fetchRoleMembershipTree,
  replaceRoleMemberships,
} from "./roleMembershipApi";
export type { CheckinPlatformKey } from "./roleMembershipApi";

export type {
  NapCatGroup,
  NapCatSiteMember,
  NapCatGroupMember,
  NapCatGroupsResponse,
  NapCatGroupMembersResponse,
} from "./napcatApi";

export {
  testNapCatConnection,
  fetchNapCatGroups,
  fetchNapCatGroupMembers,
} from "./napcatApi";
