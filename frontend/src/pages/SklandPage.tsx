import {
  fetchSklandStatus,
  triggerSklandCheckin,
  updateSklandBind,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { SklandBindPanel } from "@/components/SklandBindPanel";

export default function SklandPage() {
  return (
    <CheckinPageTemplate
      title="森空岛"
      subtitle="自动完成明日方舟与明日方舟：终末地的每日签到"
      bindName="森空岛"
      bindDescription="支持扫码、短信验证码或账号密码登录鹰角通行证，用于方舟 / 终末地签到。"
      bindPanel={<SklandBindPanel title="绑定森空岛账号" />}
      statusQueryKey={["skland-status"]}
      fetchStatus={fetchSklandStatus}
      triggerCheckin={triggerSklandCheckin}
      updateBind={updateSklandBind}
    />
  );
}
