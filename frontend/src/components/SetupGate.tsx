import { Spin } from "antd";
import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { fetchSetupStatus } from "@/api/client";

/** 未初始化时强制进入 /setup；已初始化时离开 /setup。 */
export function SetupGate({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);
  const onSetup = location.pathname === "/setup";

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const status = await fetchSetupStatus();
        if (!cancelled) setNeedsSetup(status.needs_setup);
      } catch {
        if (!cancelled) setNeedsSetup(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [onSetup]);

  if (needsSetup === null) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  if (needsSetup && !onSetup) {
    return <Navigate to="/setup" replace />;
  }
  if (!needsSetup && onSetup) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
