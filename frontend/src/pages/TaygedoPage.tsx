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
      bindName="塔吉多"
      bindPanel={<TaygedoBindPanel title="绑定塔吉多账号" />}
      statusQueryKey={["taygedo-status"]}
      fetchStatus={fetchTaygedoStatus}
      triggerCheckin={triggerTaygedoCheckin}
      updateBind={updateTaygedoBind}
    />
  );
}
