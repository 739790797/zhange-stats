import {
  fetchTaygedoStatus,
  triggerTaygedoCheckin,
  updateTaygedoBind,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { TaygedoBindPanel } from "@/components/TaygedoBindPanel";

export default function TaygedoPage() {
  return (
    <CheckinPageTemplate
      title="塔吉多"
      subtitle="自动完成异环 / 幻塔的每日签到"
      bindName="塔吉多"
      bindDescription="使用手机号验证码或密码登录塔吉多账号后即可自动签到。"
      bindPanel={<TaygedoBindPanel title="绑定塔吉多账号" />}
      statusQueryKey={["taygedo-status"]}
      fetchStatus={fetchTaygedoStatus}
      triggerCheckin={triggerTaygedoCheckin}
      updateBind={updateTaygedoBind}
    />
  );
}
