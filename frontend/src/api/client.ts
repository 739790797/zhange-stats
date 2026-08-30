export { client } from "./http";

export {
  login,
  register,
  sendRegisterCode,
  sendResetPasswordCode,
  resetPassword,
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
  JobRun,
  JobRunsPage,
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
  fetchJobRuns,
  fetchJobFilterMembers,
  fetchUserCheckinTasks,
  fetchMyDailyTasks,
  fetchIntegrationsSettings,
  fetchIntegrationsStatus,
  updateIntegrationsSettings,
  testPelicanConnection,
  testMinecraftRconConnection,
  fetchAuthSettings,
  updateAuthSettings,
  updateEmailSettings,
  testEmailSettings,
} from "./settingsApi";

export {
  fetchAppUpdateStatus,
  checkAppUpdate,
  doAppUpdate,
  waitForHealthVersion,
} from "./appUpdateApi";

export { fetchSetupStatus, completeSetupAdmin } from "./setupApi";
export type { SetupStatus, SetupAdminResult } from "./setupApi";

export {
  fetchSklandStatus,
  fetchEndfieldBox,
  fetchEndfieldAttendanceCalendar,
  fetchArknightsCompareCandidates,
  fetchArknightsBoxCompare,
  fetchArknightsAttendanceCalendar,
  fetchSklandGameEvents,
  fetchArknightsRogue,
  bindSklandPassword,
  sendSklandSms,
  bindSklandSms,
  unbindSkland,
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
  updateKujiequRolePref,
  triggerKujiequCheckin,
  fetchKujiequExchange,
  exchangeKujiequItem,
  fetchKujiequAttendanceCalendar,
  fetchWwBox,
} from "./kujiequApi";

export {
  fetchMihoyoStatus,
  sendMihoyoSms,
  bindMihoyoSms,
  bindMihoyoPassword,
  startMihoyoQrBind,
  pollMihoyoQrBind,
  unbindMihoyo,
  updateMihoyoRolePref,
  triggerMihoyoCheckin,
  fetchMihoyoExchange,
  exchangeMihoyoItem,
  fetchMihoyoAttendanceCalendar,
} from "./mihoyoApi";
