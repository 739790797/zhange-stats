import { message } from "antd";
import { useCallback, useState } from "react";
import { formatLogSyncActionLabel } from "@/lib/tarkovLiveWatch";
import type { TarkovLogSessionStub } from "@/lib/tarkovGameLogs";
import type { TarkovLogSyncRange } from "@/lib/tarkovLogSyncRange";
import { useTarkovLogSync } from "@/lib/useTarkovLiveWatch";
import { confirmTarkovQuestReset } from "@/lib/tarkovQuestResetConfirm";

const DEFAULT_TITLE =
  "本机解析日志，只把任务状态回填到账号，不会上传原文。默认从本赛季当前角色第一次出现读到现在。";

export function useTarkovLogSyncDialog() {
  const live = useTarkovLogSync();
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<TarkovLogSessionStub[]>([]);
  const [listing, setListing] = useState(false);

  const closeDialog = useCallback(() => {
    setOpen(false);
  }, []);

  const openDialog = useCallback(async () => {
    if (live.busy) {
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
      void live.syncLogs({ ...range, confirmReset: confirmTarkovQuestReset }).then((result) => {
        if (result.review?.rows.length || result.review?.dropHint) return;
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
    busy: live.busy,
    scan: live.scan,
    label: formatLogSyncActionLabel(live.busy, live.scan, listing),
    title: live.busy ? "再次点击可取消" : DEFAULT_TITLE,
    openDialog,
    closeDialog,
    confirm,
  };
}
