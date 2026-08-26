import {
  CheckCircleFilled,
  ClockCircleOutlined,
  ReloadOutlined,
  WarningFilled,
} from "@ant-design/icons";
import { Button, Empty, Progress, Skeleton, Typography, theme } from "antd";
import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import type { UserCheckinTask } from "@/api/client";
import { TodayCheckinAwards } from "@/components/CheckinAwardsLine";
import { CheckinStatusTag } from "@/components/CheckinStatusTag";
import { CheckinTreeNameLabel } from "@/components/checkinTaskDisplay";
import { CHECKIN_STATUS, isCheckinSuccess } from "@/lib/checkinStatus";
import { formatCheckinTime, displayCheckinChannelName } from "@/lib/checkinDisplay";
import {
  DAILY_CRED_BROKEN_HINT,
  DAILY_CRED_BROKEN_TITLE,
  checkinPlatformHref,
  dailyHeadline,
  dailyRoleLabel,
  type DailyPlatformGroup,
  type DailySummary,
} from "@/lib/myDaily";
import styles from "./MyDailyBoard.module.css";

function AutoHint({ task }: { task: UserCheckinTask }) {
  if (!task.auto_checkin) {
    return (
      <Typography.Text type="secondary" className={styles.autoHint}>
        手动
      </Typography.Text>
    );
  }
  return (
    <Typography.Text type="secondary" className={styles.autoHint}>
      <ClockCircleOutlined />
      {formatCheckinTime(task.checkin_hour, task.checkin_minute)}
    </Typography.Text>
  );
}

function RoleRow({
  task,
  platform,
}: {
  task: UserCheckinTask;
  platform: string;
}) {
  const signed = isCheckinSuccess(task.today_status);
  const failed = (task.today_status || "").trim() === CHECKIN_STATUS.ERROR;
  const className = [
    styles.roleRow,
    signed ? styles.roleRowSigned : "",
    failed ? styles.roleRowFailed : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={className}>
      <div className={styles.gameCell}>
        {task.game_code ? (
          <CheckinTreeNameLabel
            kind="game"
            platform={platform}
            gameCode={task.game_code}
            label={task.game_name || task.game_code}
            iconSize={16}
          />
        ) : (
          <Typography.Text type="secondary">平台任务</Typography.Text>
        )}
      </div>
      <Typography.Text type="secondary" className={styles.channelCell} ellipsis>
        {displayCheckinChannelName(task.channel_name) || "—"}
      </Typography.Text>
      <Typography.Text className={styles.roleName} ellipsis>
        {dailyRoleLabel(task)}
      </Typography.Text>
      <div className={styles.statusCell}>
        <CheckinStatusTag
          status={task.today_status || CHECKIN_STATUS.PENDING}
          statusLabel={task.today_status_label}
        />
      </div>
      <div className={styles.awards}>
        <TodayCheckinAwards
          status={task.today_status || CHECKIN_STATUS.PENDING}
          awards={task.today_awards}
          awardsText={task.today_awards_text}
          gameCode={task.game_code}
          channelName={task.channel_name}
        />
      </div>
      <div className={styles.autoCell}>
        <AutoHint task={task} />
      </div>
    </div>
  );
}

function CredPlatformRow({
  group,
}: {
  group: DailyPlatformGroup<UserCheckinTask>;
}) {
  const href = checkinPlatformHref(group.platform);
  return (
    <div className={styles.credRow}>
      <div className={styles.credCopy}>
        <CheckinTreeNameLabel
          kind="platform"
          platform={group.platform}
          label={group.platform_name}
          strong
          iconSize={20}
        />
        <Typography.Text type="secondary">
          {DAILY_CRED_BROKEN_TITLE} · {DAILY_CRED_BROKEN_HINT}
        </Typography.Text>
      </div>
      {href ? (
        <Link to={href}>
          <Button type="primary" size="small">
            重新绑定
          </Button>
        </Link>
      ) : null}
    </div>
  );
}

function PlatformSection({
  group,
}: {
  group: DailyPlatformGroup<UserCheckinTask>;
}) {
  const { token } = theme.useToken();
  const href = checkinPlatformHref(group.platform);
  const allSigned = group.total > 0 && group.signed === group.total;
  const actionLabel = allSigned ? "查看" : "去签到";

  return (
    <section className={styles.section}>
      <div className={styles.sectionHead}>
        <span className={styles.sectionTitle}>
          <CheckinTreeNameLabel
            kind="platform"
            platform={group.platform}
            label={group.platform_name}
            strong
            iconSize={20}
          />
          <Typography.Text type="secondary">
            {group.signed}/{group.total}
          </Typography.Text>
          {allSigned ? (
            <CheckCircleFilled style={{ color: token.colorSuccess }} />
          ) : null}
        </span>
        {href ? (
          <Link to={href}>
            <Button type="link" size="small">
              {actionLabel}
            </Button>
          </Link>
        ) : null}
      </div>
      <div className={styles.colHead} aria-hidden>
        <span>游戏</span>
        <span>区服</span>
        <span>角色</span>
        <span>状态</span>
        <span>奖励</span>
        <span>计划</span>
      </div>
      {group.games.flatMap((game) =>
        game.tasks.map((task) => (
          <RoleRow key={task.task_key} task={task} platform={group.platform} />
        )),
      )}
    </section>
  );
}

export function MyDailyBoard({
  groups,
  summary,
  loading,
  refreshing,
  onRefresh,
}: {
  groups: DailyPlatformGroup<UserCheckinTask>[];
  summary: DailySummary;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const { token } = theme.useToken();
  const percent =
    summary.total > 0 ? Math.round((summary.signed / summary.total) * 100) : 0;
  const complete =
    summary.total > 0 &&
    summary.signed === summary.total &&
    summary.credBroken === 0;
  const headline = dailyHeadline(summary);
  const credGroups = groups.filter((group) => group.credBroken);
  const liveGroups = groups.filter((group) => !group.credBroken);

  if (loading) {
    return (
      <div className={styles.board}>
        <div className={styles.summary}>
          <Skeleton active paragraph={{ rows: 2 }} title={false} />
        </div>
        <div className={styles.section}>
          <Skeleton active paragraph={{ rows: 5 }} style={{ padding: 16 }} />
        </div>
      </div>
    );
  }

  if (summary.total === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="暂无已加入本站的角色"
      >
        <Link to="/profile">
          <Button type="primary">去个人中心选择角色</Button>
        </Link>
      </Empty>
    );
  }

  return (
    <div
      className={styles.board}
      style={
        {
          "--daily-hover": token.colorFillSecondary,
          "--daily-fail-bg": token.colorErrorBg,
          "--daily-line": token.colorBorderSecondary,
        } as CSSProperties
      }
    >
      <div className={styles.summary}>
        <div className={styles.summaryScore}>
          <div className={styles.summaryNums}>
            <span
              className={styles.summarySigned}
              style={{
                color: complete ? token.colorSuccess : token.colorPrimary,
              }}
            >
              {summary.signed}
            </span>
            <Typography.Text type="secondary">/ {summary.total}</Typography.Text>
          </div>
          <Typography.Text type="secondary">今日已签</Typography.Text>
        </div>
        <div className={styles.summaryBody}>
          <Typography.Text strong>{headline}</Typography.Text>
          <Progress
            percent={percent}
            showInfo={false}
            strokeWidth={8}
            strokeColor={complete ? token.colorSuccess : token.colorPrimary}
            style={{ margin: "8px 0 0" }}
          />
          <div className={styles.summaryMeta}>
            <span className={styles.summaryMetaItem}>
              <Typography.Text type="secondary">待签</Typography.Text>
              <Typography.Text>{summary.pending}</Typography.Text>
            </span>
            {summary.failed > 0 ? (
              <span className={styles.summaryMetaItem}>
                <Typography.Text type="danger">失败</Typography.Text>
                <Typography.Text type="danger">{summary.failed}</Typography.Text>
              </span>
            ) : null}
            {summary.unknown > 0 ? (
              <span className={styles.summaryMetaItem}>
                <Typography.Text type="warning">待确认</Typography.Text>
                <Typography.Text>{summary.unknown}</Typography.Text>
              </span>
            ) : null}
            {summary.credPlatforms > 0 ? (
              <span className={styles.summaryMetaItem}>
                <Typography.Text type="danger">凭证失效</Typography.Text>
                <Typography.Text type="danger">
                  {summary.credPlatforms}
                </Typography.Text>
              </span>
            ) : null}
            <span className={styles.summaryMetaItem}>
              <Typography.Text type="secondary">自动开启</Typography.Text>
              <Typography.Text>
                {summary.autoOn}/{summary.total}
              </Typography.Text>
            </span>
          </div>
        </div>
        {onRefresh ? (
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            loading={refreshing}
            onClick={() => onRefresh()}
          >
            刷新
          </Button>
        ) : null}
      </div>

      {credGroups.length ? (
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <span className={styles.sectionTitle}>
              <WarningFilled style={{ color: token.colorError }} />
              <Typography.Text strong>需要重新绑定</Typography.Text>
            </span>
          </div>
          {credGroups.map((group) => (
            <CredPlatformRow key={group.platform} group={group} />
          ))}
        </section>
      ) : null}

      {liveGroups.map((group) => (
        <PlatformSection key={group.platform} group={group} />
      ))}
    </div>
  );
}
