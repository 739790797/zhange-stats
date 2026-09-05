import { message } from "antd";
import { useCallback, useState } from "react";
import { formatLogSyncActionLabel } from "@/lib/tarkovLiveWatch";
import type { TarkovLogSessionStub } from "@/lib/tarkovGameLogs";
import type { TarkovLogSyncRange } from "@/lib/tarkovLogSyncRange";
import { useTarkovLiveWatch } from "@/lib/useTarkovLiveWatch";

const DEFAULT_TITLE =
  "本机解析日志，只把任务状态回填到账号，不会上传原文。先选日期范围，默认本赛季。";

export function useTarkovLogSyncDialog() {
  const live = useTarkovLiveWatch();
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<TarkovLogSessionStub[]>([]);
  const [listing, setListing] = useState(false);

  const closeDialog = useCallback(() => {
    setOpen(false);
  }, []);

  const openDialog = useCallback(async () => {
    if (live.logSyncBusy) {
      live.cancelLogSync();
      return;
    }
    setListing(true);
    try {
      const preview = await live.previewLogSessions();
      if (!preview.ok) {
        if (preview.hint) message.error(preview.hint);
        return;
      }
      setSessions(preview.sessions);
      setOpen(true);
    } finally {
      setListing(false);
    }
  }, [live]);

  const confirm = useCallback(
    (range: TarkovLogSyncRange) => {
      setOpen(false);
      void live.syncLogs(range).then((result) => {
        if (!result.hint) return;
        if (result.ok) message.success(result.hint);
        else message.error(result.hint);
      });
    },
    [live],
  );

  return {
    open,
    sessions,
    listing,
    busy: live.logSyncBusy,
    scan: live.logSyncScan,
    label: formatLogSyncActionLabel(live.logSyncBusy, live.logSyncScan, listing),
    title: live.logSyncBusy ? "再次点击可取消" : DEFAULT_TITLE,
    openDialog,
    closeDialog,
    confirm,
  };
}
