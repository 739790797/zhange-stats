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
  AuthSettings,
  UpdateCheckResult,
  UpdateStatusResult,
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
  fetchEndfieldBox,
  fetchArknightsCompareCandidates,
  fetchArknightsBoxCompare,
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
