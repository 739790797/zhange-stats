import { Button, Input, Modal, Popover, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  bindTarkovTrackerToken,
  fetchTarkovProgress,
  syncTarkovProgress,
  unbindTarkovTrackerToken,
  type TarkovTrackerStatus,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovTrackerBindButton.module.css";

const QUERY_KEY = ["guides-tarkov-progress"] as const;

function TrackerDetail({
  status,
  onSync,
  onUnbind,
  syncing,
  unbinding,
}: {
  status: TarkovTrackerStatus;
  onSync: () => void;
  onUnbind: () => void;
  syncing: boolean;
  unbinding: boolean;
}) {
  return (
    <div>
      <div className={styles.detail}>
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>角色</span>
          <span>{status.display_name || "—"}</span>
        </div>
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>等级</span>
          <span>Lv.{status.player_level || "—"}</span>
        </div>
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>阵营</span>
          <span>{status.pmc_faction || "—"}</span>
        </div>
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>模式</span>
          <span>{status.game_mode_label || "—"}</span>
        </div>
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>已完成任务</span>
          <span>{status.tasks_complete}</span>
        </div>
        {status.last_error ? (
          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>上次同步</span>
            <span>{status.last_error}</span>
          </div>
        ) : null}
      </div>
      <div className={styles.actions}>
        <Button size="small" loading={syncing} onClick={onSync}>
          刷新
        </Button>
        <Button size="small" danger loading={unbinding} onClick={onUnbind}>
          解绑
        </Button>
      </div>
    </div>
  );
}

export function TarkovTrackerBindButton() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const loggedIn = Boolean(useAuthStore((s) => s.token));
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");

  const statusQuery = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchTarkovProgress,
    enabled: loggedIn,
    staleTime: 60_000,
    retry: false,
  });

  const bindMut = useMutation({
    mutationFn: bindTarkovTrackerToken,
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEY, data);
      queryClient.invalidateQueries({ queryKey: ["guides-tarkov-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["guides-tarkov-task-detail"] });
      setOpen(false);
      setToken("");
      message.success(
        data.player_level
          ? `已绑定 · Lv.${data.player_level}`
          : "已绑定 Tarkov Tracker",
      );
    },
    onError: (err) => {
      message.error(apiError(err, "绑定失败"));
    },
  });

  const syncMut = useMutation({
    mutationFn: syncTarkovProgress,
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEY, data);
      queryClient.invalidateQueries({ queryKey: ["guides-tarkov-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["guides-tarkov-task-detail"] });
      message.success("进度已刷新");
    },
    onError: (err) => {
      message.error(apiError(err, "刷新失败"));
    },
  });

  const unbindMut = useMutation({
    mutationFn: unbindTarkovTrackerToken,
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEY, data);
      queryClient.invalidateQueries({ queryKey: ["guides-tarkov-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["guides-tarkov-task-detail"] });
      message.success("已解绑");
    },
    onError: (err) => {
      message.error(apiError(err, "解绑失败"));
    },
  });

  const status = statusQuery.data;
  const bound = Boolean(status?.bound);

  const onBindClick = () => {
    if (!loggedIn) {
      navigate("/login");
      return;
    }
    setOpen(true);
  };

  return (
    <div className={styles.slot}>
      {bound && status ? (
        <Popover
          trigger="click"
          placement="bottomRight"
          title="Tarkov Tracker"
          content={
            <TrackerDetail
              status={status}
              syncing={syncMut.isPending}
              unbinding={unbindMut.isPending}
              onSync={() => syncMut.mutate()}
              onUnbind={() => unbindMut.mutate()}
            />
          }
        >
          <button type="button" className={styles.chip} aria-label="Tarkov Tracker 进度">
            <span className={styles.level}>
              {status.player_level ? `Lv.${status.player_level}` : "已绑定"}
            </span>
            <span className={styles.meta}>
              {[status.pmc_faction, status.game_mode_label]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </button>
        </Popover>
      ) : (
        <button type="button" className={styles.bindBtn} onClick={onBindClick}>
          绑定 Token
        </button>
      )}

      <Modal
        title="绑定 Tarkov Tracker"
        open={open}
        onCancel={() => setOpen(false)}
        okText="绑定"
        cancelText="取消"
        confirmLoading={bindMut.isPending}
        okButtonProps={{ disabled: !token.trim() }}
        onOk={() => {
          if (!token.trim()) return;
          bindMut.mutate(token);
        }}
        destroyOnClose
      >
        <p className={styles.hint}>
          到{" "}
          <a
            href="https://tarkovtracker.org/settings"
            target="_blank"
            rel="noreferrer"
          >
            tarkovtracker.org 设置页
          </a>{" "}
          创建 API token，勾选 <strong>Get progression</strong>，用复制按钮拷贝后粘贴。
          可与 TarkovMonitor 使用同一枚 token。
        </p>
        <Input.Password
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="PVP_ / PVE_ / SZN_…"
          autoComplete="off"
        />
      </Modal>
    </div>
  );
}
