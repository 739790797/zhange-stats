import { LoadingOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState, type CSSProperties } from "react";

import {
  loadSteamClientIcon,
  resolveSteamIcon,
} from "@/lib/steamIconCache";

function IconPlaceholder({ size }: { size: number }) {
  return (
    <span
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: 2,
        flexShrink: 0,
        display: "inline-block",
        background: "#d9d9d9",
        boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.08)",
      }}
    />
  );
}

function IconLoading({ size }: { size: number }) {
  return (
    <span
      aria-busy
      aria-label="加载图标"
      style={{
        width: size,
        height: size,
        borderRadius: 2,
        flexShrink: 0,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.04)",
        boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.06)",
      }}
    >
      <LoadingOutlined
        spin
        style={{
          fontSize: Math.max(10, Math.round(size * 0.5)),
          color: "rgba(0,0,0,0.35)",
        }}
      />
    </span>
  );
}

/** 库列表 client icon：异步补全时转圈，真失败才灰块。 */
export function SteamClientIcon({
  appId,
  iconUrl,
  size,
  imgStyle,
}: {
  appId?: string | null;
  iconUrl?: string | null;
  size: number;
  imgStyle?: CSSProperties;
}) {
  const known = useMemo(
    () => resolveSteamIcon(appId, iconUrl),
    [appId, iconUrl],
  );
  const [src, setSrc] = useState<string | null>(known);
  const [phase, setPhase] = useState<"loading" | "ready" | "failed">(() =>
    known ? "ready" : appId ? "loading" : "failed",
  );
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    const resolved = resolveSteamIcon(appId, iconUrl);
    if (resolved) {
      setSrc(resolved);
      setPhase("ready");
      setImgFailed(false);
      return;
    }
    if (!appId) {
      setSrc(null);
      setPhase("failed");
      return;
    }
    let cancelled = false;
    setPhase("loading");
    setImgFailed(false);
    void loadSteamClientIcon(appId).then((url) => {
      if (cancelled) return;
      if (url) {
        setSrc(url);
        setPhase("ready");
      } else {
        setSrc(null);
        setPhase("failed");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [appId, iconUrl]);

  if (phase === "loading") return <IconLoading size={size} />;
  if (phase === "failed" || !src || imgFailed) {
    return <IconPlaceholder size={size} />;
  }
  return (
    <img
      key={src}
      src={src}
      alt=""
      draggable={false}
      referrerPolicy="no-referrer"
      onError={() => setImgFailed(true)}
      style={{
        width: size,
        height: size,
        objectFit: "cover",
        objectPosition: "center",
        borderRadius: 2,
        flexShrink: 0,
        display: "block",
        background: "#d9d9d9",
        ...imgStyle,
      }}
    />
  );
}

export function TimelineSegmentLogo({
  appId,
  iconUrl,
  size,
}: {
  appId: string;
  iconUrl?: string | null;
  size: number;
}) {
  return (
    <SteamClientIcon
      appId={appId}
      iconUrl={iconUrl}
      size={size}
      imgStyle={{ boxShadow: "0 0 0 1px rgba(0,0,0,0.2)" }}
    />
  );
}

export function GameIcon({
  appId,
  iconUrl,
  size = 40,
}: {
  appId?: string | null;
  iconUrl?: string | null;
  name: string;
  size?: number;
}) {
  return <SteamClientIcon appId={appId} iconUrl={iconUrl} size={size} />;
}
