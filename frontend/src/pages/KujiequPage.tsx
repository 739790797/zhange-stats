import {
  fetchKujiequStatus,
  triggerKujiequCheckin,
  updateKujiequBind,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { KujiequBindPanel } from "@/components/KujiequBindPanel";

export default function KujiequPage() {
  return (
    <CheckinPageTemplate
      title="库街区"
      subtitle="自动完成库街区社区签到，以及鸣潮 / 战双的游戏签到"
      bindName="库街区"
      bindDescription="使用手机号短信验证码绑定库街区账号。"
      bindPanel={<KujiequBindPanel title="绑定库街区账号" />}
      statusQueryKey={["kujiequ-status"]}
      fetchStatus={fetchKujiequStatus}
      triggerCheckin={triggerKujiequCheckin}
      updateBind={updateKujiequBind}
    />
  );
}
