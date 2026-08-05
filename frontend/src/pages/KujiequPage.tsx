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
      bindName="库街区"
      bindPanel={<KujiequBindPanel title="绑定库街区账号" />}
      statusQueryKey={["kujiequ-status"]}
      fetchStatus={fetchKujiequStatus}
      triggerCheckin={triggerKujiequCheckin}
      updateBind={updateKujiequBind}
    />
  );
}
