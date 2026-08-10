import { useEffect, useState } from "react";
import { client } from "@/api/http";

/** 带 Bearer 拉取图片，供 <img> 使用（截图 API 需登录）。 */
export function useAuthedImage(path: string | null, refreshKey = 0) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!path) {
      setUrl(null);
      setError(false);
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;
    setError(false);
    (async () => {
      try {
        const res = await client.get(path.replace(/^\/api/, ""), {
          responseType: "blob",
          // path like /settings/maa/... when baseURL is /api
        });
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data);
        setUrl(objectUrl);
      } catch {
        if (!cancelled) {
          setUrl(null);
          setError(true);
        }
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path, refreshKey]);

  return { url, error };
}
