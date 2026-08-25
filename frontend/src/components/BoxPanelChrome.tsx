import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Select, Space, Spin, Typography } from "antd";
import type { ReactNode } from "react";
import { apiError } from "@/lib/apiError";
import { formatSyncedAt } from "@/lib/formatSyncedAt";

export type BoxPanelRoleOption = {
  uid: string;
  label: string;
};

type Props = {
  enabled: boolean;
  disabledDescription: string;
  loading: boolean;
  loadingTip: string;
  error: unknown;
  errorTitle: string;
  empty: boolean;
  refreshing: boolean;
  onRefresh: () => void;
  stale?: boolean;
  title: ReactNode;
  subtitle?: ReactNode;
  roles?: BoxPanelRoleOption[];
  selectedUid?: string | null;
  onSelectUid?: (uid: string) => void;
  syncedAt?: string | null;
  children: ReactNode;
};

/**
 * 盒子页壳：未绑定 / 加载 / 失败 / 空数据 / 过期缓存 + 角色选择 + 刷新。
 * 角色卡、装备栏仍由各游戏面板自己画。
 */
export function BoxPanelChrome({
  enabled,
  disabledDescription,
  loading,
  loadingTip,
  error,
  errorTitle,
  empty,
  refreshing,
  onRefresh,
  stale,
  title,
  subtitle,
  roles = [],
  selectedUid,
  onSelectUid,
  syncedAt,
  children,
}: Props) {
  if (!enabled) {
    return <Empty description={disabledDescription} />;
  }

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <Spin tip={loadingTip} />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message={errorTitle}
        description={apiError(error, "请稍后重试或点击刷新")}
        action={
          <Button size="small" onClick={() => onRefresh()} loading={refreshing}>
            刷新
          </Button>
        }
      />
    );
  }

  if (empty) {
    return <Empty description="暂无数据" />;
  }

  return (
    <div>
      {stale ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="展示的是本地缓存，上游刷新失败"
          action={
            <Button size="small" onClick={() => onRefresh()} loading={refreshing}>
              重试
            </Button>
          }
        />
      ) : null}

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <Space wrap size={12}>
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {title}
            </Typography.Title>
            {subtitle ? (
              <Typography.Text type="secondary">{subtitle}</Typography.Text>
            ) : null}
          </div>
          {roles.length > 1 && onSelectUid ? (
            <Select
              style={{ minWidth: 180 }}
              value={selectedUid || undefined}
              options={roles.map((r) => ({
                value: r.uid,
                label: r.label,
              }))}
              onChange={(v) => onSelectUid(v)}
            />
          ) : null}
        </Space>
        <Space>
          {syncedAt ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              同步于 {formatSyncedAt(syncedAt)}
            </Typography.Text>
          ) : null}
          <Button
            size="small"
            icon={<ReloadOutlined />}
            loading={refreshing}
            onClick={() => onRefresh()}
          >
            刷新
          </Button>
        </Space>
      </div>
      {children}
    </div>
  );
}
