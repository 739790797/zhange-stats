export { client, formatRequestError } from "./http";

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
  startQqOAuthLogin,
} from "./authApi";

export {
  fetchSteamFriends,
  fetchMembers,
  fetchSteamOverview,
  fetchMemberPlayStats,
  fetchSteamCalendar,
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
  previewSteamBind,
  startSteamOpenIdBind,
  startQqOAuthBind,
  unbindQq,
  updateMyProfile,
  uploadMyAvatar,
  uploadMemberAvatar,
  deleteMyAvatar,
  fetchMemberProfile,
  updateMemberProfile,
} from "./usersApi";

export type {
  EmailSettings,
  ScheduledJobLastRun,
  JobExecutor,
  ScheduledJob,
  ScheduledJobsResponse,
  PlatformFeatureNode,
  PlatformFeaturesResponse,
  JobRunRecord,
  JobRunsPage,
  JobTriggerResult,
  CheckinLogItem,
  CheckinLogsPage,
  JobMemberOption,
  UserCheckinTask,
  UserCheckinTasksPage,
  IntegrationsSettings,
  AuthSettings,
  UpdateCheckResult,
  UpdateStatusResult,
} from "./settingsApi";

export {
  fetchEmailSettings,
  fetchScheduledJobs,
  fetchPlatformFeaturesEffective,
  fetchPlatformFeaturesAdmin,
  updatePlatformFeatures,
  triggerScheduledJob,
  fetchJobRuns,
  fetchJobCheckinLogs,
  fetchJobFilterMembers,
  fetchUserCheckinTasks,
  fetchMyDailyTasks,
  fetchMyDailyTaskLogs,
  fetchIntegrationsSettings,
  updateIntegrationsSettings,
  fetchAuthSettings,
  updateAuthSettings,
  updateEmailSettings,
  testEmailSettings,
  checkUpdate,
  fetchUpdateStatus,
  triggerUpdate,
} from "./settingsApi";

export {
  fetchSklandStatus,
  fetchArknightsBox,
  fetchEndfieldBox,
  fetchArknightsCompareCandidates,
  fetchArknightsBoxCompare,
  fetchSklandLogs,
  bindSkland,
  bindSklandPassword,
  sendSklandSms,
  bindSklandSms,
  unbindSkland,
  updateSklandBind,
  triggerSklandCheckin,
  startSklandQrBind,
  pollSklandQrBind,
} from "./sklandApi";

export {
  fetchTaygedoStatus,
  fetchTaygedoLogs,
  bindTaygedoPassword,
  sendTaygedoSms,
  bindTaygedoSms,
  unbindTaygedo,
  updateTaygedoBind,
  triggerTaygedoCheckin,
} from "./taygedoApi";

export {
  fetchExiliumStatus,
  bindExiliumPassword,
  sendExiliumSms,
  bindExiliumSms,
  unbindExilium,
  updateExiliumBind,
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
  triggerKujiequCheckin,
} from "./kujiequApi";

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
