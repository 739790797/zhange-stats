import { Alert, Button } from "antd";
import { useState } from "react";
import { useServerAppVersion } from "@/hooks/useServerAppVersion";
import { appBundleOutdated } from "@/lib/appVersionCheck";

/** 站点换了版本而本页还是旧包：提示刷新。关掉后同一版本不再提示。 */
export function AppReloadBanner() {
  const { data: serverVersion } = useServerAppVersion({ watch: true });
  const [dismissed, setDismissed] = useState<string | null>(null);
  if (
    !serverVersion ||
    dismissed === serverVersion ||
    !appBundleOutdated(__APP_VERSION__, serverVersion)
  ) {
    return null;
  }
  return (
    <Alert
      banner
      type="info"
      closable
      style={{ flexShrink: 0 }}
      message={`站点已更新到 v${serverVersion}，刷新页面即可使用新版本。`}
      action={
        <Button size="small" onClick={() => window.location.reload()}>
          刷新
        </Button>
      }
      onClose={() => setDismissed(serverVersion)}
    />
  );
}
