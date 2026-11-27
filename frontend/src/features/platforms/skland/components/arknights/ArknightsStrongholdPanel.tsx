import { FilterOutlined, LeftOutlined, RightOutlined, SyncOutlined } from "@ant-design/icons";
import { Alert, App, Button, DatePicker, Drawer, Empty, Spin, Switch } from "antd";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchStrongholdCommunity,
  fetchStrongholdHistory,
  fetchStrongholdOwn,
  fetchStrongholdRecord,
  fetchStrongholdReport,
  strongholdQueryKey as queryKey,
  syncStrongholdRole,
  type StrongholdCommunity,
  type StrongholdHistory,
  type StrongholdHistoryResult,
  type StrongholdMatch,
  type StrongholdMode,
  type StrongholdOwn,
  type StrongholdRecordDetail,
  type StrongholdRoleSelection,
} from "@/features/platforms/skland/api/strongholdApi";
import type { SklandStatus } from "@/features/platforms/skland/api/types";
import { apiError, apiStatus } from "@/shared/api/apiError";
import { formatBeijing, nowBeijing, parseBeijing } from "@/shared/lib/time";
import { BattleScope, ResultMark } from "./StrongholdBattleUI";
import { DiaryMember, StrongholdDiaryMetrics } from "./StrongholdDiaryMetrics";
import { StrongholdReportBoard } from "./StrongholdReportBoard";
import {
  boundRoleNames,
  modeLabels,
  preferredRoleName,
  roleLabel,
  withOwnRoleNames,
} from "./strongholdLabels";
import arkStyles from "./Arknights.module.css";
import styles from "./ArknightsStronghold.module.css";
import reportStyles from "./StrongholdReport.module.css";

const diaryPageSize = 12;
const historyPageSize = 10;
const scopePattern = /^[a-z0-9][a-z0-9_.-]{0,63}$/;
const versionPattern = /^[a-z0-9][a-z0-9_.-]{0,63}:[A-Za-z0-9_:.-]{1,128}$/;
const recordPattern = /^[a-f0-9]{32}$/;
const queryOptions = { staleTime: 0, gcTime: 0, retry: false };
const results = { complete: "模拟完成", interrupted: "模拟中断", unknown: "结果未知" } as const;
const defaultDifficulty = "abyss";
const diaryDateFormat = "YYYY-MM-DD";
const earliestDiaryDate = "2019-01-01";
const retiredDiaryFilters = { member: null, season: null, role: null };
const resetDiaryDates = { date: null, start_date: null, end_date: null };
const resetViewFilters = {
  ...retiredDiaryFilters,
  ...resetDiaryDates,
  version: null,
  difficulty: null,
  mode: null,
  result: null,
};

type SearchPatch = Record<string, string | number | null | undefined>;
type SearchLink = (updates: SearchPatch) => string;
type ReportLinkClick = (event: MouseEvent<HTMLAnchorElement>, id: string) => void;
type DiaryDateRange = { start: string; end: string };
type ReportFilters = {
  season?: string;
  version: string;
  difficulty: string;
  mode?: StrongholdMode;
  dateRange?: DiaryDateRange;
  result?: StrongholdHistoryResult;
};
type ControlProps = { bound: boolean; bindFallback: ReactNode; roles?: SklandStatus["roles"] };
type BindingNames = ReadonlyMap<string, string>;

function searchWith(params: URLSearchParams, updates: SearchPatch) {
  const next = new URLSearchParams(params);
  for (const [key, value] of Object.entries(updates)) {
    if (value) next.set(key, String(value));
    else next.delete(key);
  }
  return next;
}

function diaryListKey(params: URLSearchParams) {
  const list = searchWith(params, { ...retiredDiaryFilters, report: null, battle: null });
  list.sort();
  return list.toString();
}

function positiveParam(value: string | null) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 && parsed <= 2_147_483_647 ? parsed : undefined;
}

function validDate(value: string | null) {
  if (
    !value ||
    !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
    value < earliestDiaryDate ||
    value > "2100-12-31"
  )
    return undefined;
  return parseBeijing(value).format(diaryDateFormat) === value ? value : undefined;
}

function diaryDateRange(params: URLSearchParams): DiaryDateRange | undefined {
  const start = validDate(params.get("start_date"));
  const end = validDate(params.get("end_date"));
  if (start && end && start <= end) return { start, end };
  const date = validDate(params.get("date"));
  return date ? { start: date, end: date } : undefined;
}

function Loading() {
  return (
    <div className={styles.loading} aria-label="加载战报">
      <Spin />
    </div>
  );
}

function Failed({ error, retry }: { error: unknown; retry: () => void }) {
  return (
    <Alert
      type="error"
      showIcon
      message={apiError(error, "无法加载卫戍战报")}
      action={
        <Button size="small" onClick={retry}>
          重试
        </Button>
      }
    />
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
  disabled,
  wide,
}: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
  disabled?: boolean;
  wide?: boolean;
}) {
  const caption = useId();
  return (
    <label className={wide ? `${styles.field} ${styles.wideField}` : styles.field}>
      <span id={caption}>{label}</span>
      <select
        aria-labelledby={caption}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        {options.map(([key, name]) => (
          <option key={key} value={key}>
            {name}
          </option>
        ))}
        {value && !options.some(([key]) => key === value) ? (
          <option value={value}>当前筛选</option>
        ) : null}
      </select>
    </label>
  );
}

function Pager({
  total,
  offset,
  pageSize,
  change,
  showSinglePage = false,
}: {
  total: number;
  offset: number;
  pageSize: number;
  change: (offset: number) => void;
  showSinglePage?: boolean;
}) {
  return offset > 0 || total > pageSize || (showSinglePage && total > 0) ? (
    <nav className={styles.pager} aria-label="战报分页">
      <Button
        aria-label="上一页"
        icon={<LeftOutlined />}
        disabled={offset === 0}
        onClick={() => change(Math.max(0, offset - pageSize))}
      />
      <span>
        第 {Math.floor(offset / pageSize) + 1} 页 · 共 {total} 条
      </span>
      <Button
        aria-label="下一页"
        icon={<RightOutlined />}
        disabled={offset + pageSize >= total}
        onClick={() => change(offset + pageSize)}
      />
    </nav>
  ) : null;
}

function OwnControls({
  bound,
  bindFallback,
  data,
  names,
}: ControlProps & { data: StrongholdOwn; names: BindingNames }) {
  const { message } = App.useApp();
  const queries = useQueryClient();
  const [roleKey, setRoleKey] = useState("");
  const [extraOpen, setExtraOpen] = useState(false);
  const eligible = new Map<string, { body: StrongholdRoleSelection; label: string }>();
  // The API scopes sync status to enrolled roles. The binding list only supplies display names.
  for (const entry of data.sync_status) {
    if (entry.channel_id && entry.uid) {
      const key = `${entry.channel_id}:${entry.uid}`;
      const name = preferredRoleName(names.get(key), entry.role_name, entry.uid);
      eligible.set(key, {
        body: { channel_id: entry.channel_id, uid: entry.uid },
        label: `${roleLabel(name)} · ${entry.channel_id === "1" ? "官服" : "B 服"}`,
      });
    }
  }
  const selected = eligible.has(roleKey)
    ? roleKey
    : eligible.size === 1
      ? (eligible.keys().next().value ?? "")
      : "";
  const options = Array.from(eligible, ([key, item]): [string, string] => [key, item.label]);
  if (options.length !== 1) options.unshift(["", "请选择角色"]);
  const role = eligible.get(selected);
  const synced = data.roles.find((entry) => `${entry.channel_id}:${entry.uid}` === selected);
  const state =
    data.sync_status.find((entry) => `${entry.channel_id}:${entry.uid}` === selected) ??
    data.sync_status.find((entry) => entry.uid == null);
  const sync = useMutation({
    mutationFn: syncStrongholdRole,
    onSuccess: async (out) => {
      await queries.invalidateQueries({ queryKey });
      if (out.state === "reauth") void message.warning("请重新绑定森空岛以恢复同步");
      else if (out.state === "retrying") void message.info("同步将在退避结束后重试");
      else void message.success("已提交同步请求");
    },
  });
  const next = state?.next_sync_at ? formatBeijing(state.next_sync_at, "MM-DD HH:mm") : null;
  const last = state?.last_success_at ?? synced?.synced_at;
  const status =
    state?.state === "reauth"
      ? "绑定已失效，请重新绑定森空岛"
      : state?.state === "discovering"
        ? "正在获取绑定角色"
        : state?.state === "syncing"
          ? "正在同步战绩"
          : state?.state === "queued"
            ? "等待同步"
            : state?.state === "retrying"
              ? `暂时无法同步${next ? ` · ${next} 后重试` : ""}`
              : last
                ? `上次成功同步 ${formatBeijing(last, "MM-DD HH:mm")}`
                : eligible.size
                  ? "战绩将自动同步"
                  : "没有已加入本站的可同步角色";
  return (
    <div className={styles.ownControls}>
      {!bound ? (
        <details onToggle={(event) => setExtraOpen(event.currentTarget.open)}>
          <summary>绑定森空岛</summary>
          {extraOpen ? bindFallback : null}
        </details>
      ) : !data.sync_available ? (
        <Alert type="info" showIcon message="官方战绩同步暂不可用" />
      ) : (
        <div className={styles.syncBar}>
          <SelectField
            label="同步角色"
            value={selected}
            options={options}
            onChange={setRoleKey}
            disabled={!eligible.size || sync.isPending}
          />
          <Button
            type="primary"
            icon={<SyncOutlined />}
            disabled={!role || state?.state === "syncing" || state?.state === "reauth"}
            loading={sync.isPending}
            onClick={() => role && sync.mutate(role.body)}
          >
            立即同步
          </Button>
          <span className={styles.muted} role="status">
            {status}
          </span>
        </div>
      )}
      {sync.isError ? (
        <Alert type="error" showIcon message={apiError(sync.error, "同步失败，已有战绩仍保留")} />
      ) : null}
    </div>
  );
}

function PersonalSummary({ data }: { data: StrongholdOwn }) {
  const rate = data.known_results
    ? `${((data.wins * 100) / data.known_results).toFixed(1).replace(/\.0$/, "")}%`
    : "—";
  return (
    <dl className={styles.recordStats} aria-label="个人战绩统计">
      <div>
        <dt>已同步个人战报</dt>
        <dd>{data.scoped_total}</dd>
      </div>
      <div>
        <dt>个人模拟完成</dt>
        <dd>
          {data.wins} <small>/ {data.known_results} 局已知结果</small>
        </dd>
      </div>
      <div>
        <dt>个人已知胜率</dt>
        <dd>{rate}</dd>
      </div>
    </dl>
  );
}

function isPlainLinkClick(event: MouseEvent<HTMLAnchorElement>) {
  return (
    !event.defaultPrevented &&
    event.button === 0 &&
    !event.metaKey &&
    !event.altKey &&
    !event.shiftKey &&
    !event.ctrlKey
  );
}

function isStackedHistory(element: HTMLElement) {
  return getComputedStyle(element).getPropertyValue("--sh-history-stacked").trim() === "1";
}

function focusHistoryReport(heading: HTMLHeadingElement | null) {
  if (heading && isStackedHistory(heading)) {
    heading.focus({ preventScroll: true });
    heading.scrollIntoView({ block: "start", behavior: "instant" });
  }
}

function HistoryList({
  request,
  related,
  toggleRelated,
  selected,
  offset,
  link,
  onSelect,
  changePage,
}: {
  request: UseQueryResult<StrongholdHistory>;
  related: boolean;
  toggleRelated: (checked: boolean) => void;
  selected: string | null;
  offset: number;
  link: SearchLink;
  onSelect: ReportLinkClick;
  changePage: (offset: number) => void;
}) {
  const relatedId = useId();
  const busy = request.isPending || request.isPlaceholderData;
  const data = busy ? undefined : request.data;
  return (
    <section className={`${styles.feed} ${styles.history}`} aria-label="战绩列表" aria-busy={busy}>
      <header className={`${styles.bandHeader} ${styles.historyHeader}`}>
        <div>
          <h3>战绩列表</h3>
          {data ? <small>共 {data.total} 局</small> : null}
        </div>
        <label className={styles.relatedToggle} htmlFor={relatedId}>
          <Switch id={relatedId} size="small" checked={related} onChange={toggleRelated} />
          <span>与我相关</span>
        </label>
      </header>
      {busy ? (
        <Loading />
      ) : request.isError ? (
        <Failed error={request.error} retry={() => void request.refetch()} />
      ) : data?.matches.length ? (
        <ul
          className={styles.recordList}
          style={{ "--history-page-size": historyPageSize } as CSSProperties}
        >
          {data.matches.map(({ id, preview, success, difficulty_label, mode_type, ended_at }) => (
            <li key={id} className={styles.recordItem} data-selected={id === selected}>
              <Link
                className={styles.recordRow}
                to={link({ report: id, battle: preview?.id ?? null })}
                preventScrollReset
                onClick={(event) => onSelect(event, id)}
                aria-current={id === selected ? "true" : undefined}
              >
                <span className={styles.recordRowTop}>
                  <strong title={difficulty_label}>{difficulty_label}</strong>
                  <span>{preview?.pass_round == null ? "—" : `${preview.pass_round} 回合`}</span>
                </span>
                <span className={styles.recordRowTop}>
                  <span>{mode_type ? modeLabels[mode_type] : "模式未记录"}</span>
                  <ResultMark result={success} />
                </span>
                <time dateTime={ended_at}>{formatBeijing(ended_at, "YYYY-MM-DD HH:mm")}</time>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前检索条件下没有战绩" />
      )}
      {data && !request.isError ? (
        <Pager
          total={data.total}
          offset={offset}
          pageSize={historyPageSize}
          change={changePage}
          showSinglePage
        />
      ) : null}
    </section>
  );
}

function SearchControl({
  children,
  filtered,
  reset,
}: {
  children: ReactNode;
  filtered: boolean;
  reset: () => void;
}) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const statusId = `${titleId}-status`;
  const close = () => setOpen(false);
  return (
    <>
      <button
        className={styles.searchTrigger}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-describedby={filtered ? statusId : undefined}
        data-filtered={filtered}
        onClick={() => setOpen(true)}
      >
        <span className={styles.searchIcon} aria-hidden="true">
          <FilterOutlined />
        </span>
        检索条件
        {filtered ? (
          <span id={statusId} hidden>
            已调整检索条件
          </span>
        ) : null}
      </button>
      <Drawer
        title={<span id={titleId}>检索条件</span>}
        aria-labelledby={titleId}
        rootClassName={`${arkStyles.portalTheme} ${styles.searchDrawer}`}
        width="min(420px, 100%)"
        open={open}
        onClose={close}
        footer={
          <div className={styles.searchFooter}>
            <Button onClick={reset} disabled={!filtered}>
              恢复默认
            </Button>
            <Button type="primary" onClick={close}>
              完成
            </Button>
          </div>
        }
      >
        {children}
      </Drawer>
    </>
  );
}

function ReportSearchFields({
  filters,
  data,
  applied,
  update,
  history,
  roles,
  roleId,
  names,
}: {
  filters: ReportFilters;
  data?: StrongholdCommunity | StrongholdHistory;
  applied: boolean;
  update: (patch: SearchPatch) => void;
  history: boolean;
  roles?: StrongholdOwn["roles"];
  roleId?: number;
  names: BindingNames;
}) {
  const dateId = useId();
  const [calendarOpen, setCalendarOpen] = useState<keyof DiaryDateRange | null>(null);
  const today = data?.today ?? nowBeijing().format(diaryDateFormat);
  const day = { start: today, end: today };
  const appliedDates = filters.dateRange ?? (history ? undefined : day);
  // Keep a selected range while URL navigation is pending so the picker cannot restore an older range.
  const [pendingDates, setPendingDates] = useState<{
    previous?: DiaryDateRange;
    selected: DiaryDateRange;
  }>();
  const editing =
    pendingDates &&
    pendingDates.previous?.start === appliedDates?.start &&
    pendingDates.previous?.end === appliedDates?.end;
  if (pendingDates && !editing) setPendingDates(undefined);
  const dates = editing ? pendingDates.selected : appliedDates;
  const startValue = useMemo(
    () => (dates?.start ? parseBeijing(dates.start) : null),
    [dates?.start],
  );
  const endValue = useMemo(() => (dates?.end ? parseBeijing(dates.end) : null), [dates?.end]);
  const updateDate = (edge: keyof DiaryDateRange, value: string) => {
    if (value === dates?.[edge]) return;
    const selected = dates
      ? {
          start: edge === "start" || value < dates.start ? value : dates.start,
          end: edge === "end" || value > dates.end ? value : dates.end,
        }
      : { start: value, end: value };
    setPendingDates({ previous: appliedDates, selected });
    update({ ...resetDiaryDates, start_date: selected.start, end_date: selected.end });
  };
  const latest =
    filters.version === "latest" && applied
      ? data?.versions.find(({ key }) => key === data.selected_version_key)
      : undefined;
  const difficulties = new Map([[defaultDifficulty, "终极模拟"]]);
  for (const scope of data?.scopes ?? []) {
    if (scope.difficulty_id !== "unknown" && !difficulties.has(scope.difficulty_id)) {
      difficulties.set(scope.difficulty_id, scope.difficulty_label);
    }
  }
  return (
    <div className={styles.searchFields}>
      {roles ? (
        <SelectField
          label="查看角色"
          wide
          value={String(roleId ?? "")}
          options={[
            ["", "全部角色"],
            ...roles.map(({ id, channel_id, uid, role_name }): [string, string] => {
              const name = preferredRoleName(names.get(`${channel_id}:${uid}`), role_name, uid);
              return [String(id), `${roleLabel(name)} · ${channel_id === "1" ? "官服" : "B 服"}`];
            }),
          ]}
          onChange={(role) => update({ role })}
        />
      ) : null}
      {filters.season ? (
        <Button className={styles.legacyScope} onClick={() => update({ season: null })}>
          清除旧赛季筛选
        </Button>
      ) : null}
      <SelectField
        label="版本"
        wide
        value={filters.version}
        options={[
          [
            "latest",
            latest
              ? `${latest.label}（最新）`
              : applied && filters.version === "latest"
                ? "暂无版本"
                : "最新版本",
          ],
          ["all", "全部版本"],
          ...(data?.versions ?? []).map(({ key, label }): [string, string] => [key, label]),
        ]}
        onChange={(version) =>
          update({
            version: (history ? version === "all" : version === "latest") ? null : version,
            season: null,
          })
        }
      />
      <div className={styles.diaryDate} role="group" aria-labelledby={dateId}>
        <div className={styles.diaryDateHeader}>
          <span id={dateId}>
            日期范围 <small>北京时间</small>
          </span>
          <div className={styles.dateShortcuts}>
            {history ? (
              <Button
                disabled={!appliedDates}
                onClick={() => {
                  setPendingDates(undefined);
                  update(resetDiaryDates);
                }}
              >
                全部日期
              </Button>
            ) : null}
            <Button
              onClick={() => {
                setPendingDates(undefined);
                update(
                  history
                    ? { ...resetDiaryDates, start_date: today, end_date: today }
                    : resetDiaryDates,
                );
              }}
            >
              今日
            </Button>
          </div>
        </div>
        {(["start", "end"] as const).map((edge) => {
          const inputId = `${dateId}-${edge}`;
          return (
            <div key={edge} className={styles.field}>
              <label htmlFor={inputId}>{edge === "start" ? "开始日期" : "结束日期"}</label>
              <DatePicker
                id={inputId}
                value={edge === "start" ? startValue : endValue}
                format={diaryDateFormat}
                allowClear={false}
                placeholder={history ? "不限" : undefined}
                onOpenChange={(open) =>
                  setCalendarOpen((current) => (open ? edge : current === edge ? null : current))
                }
                onKeyDown={(event) => {
                  if (event.key === "Escape" && calendarOpen === edge) event.stopPropagation();
                }}
                disabledDate={(day) => {
                  const date = day.format(diaryDateFormat);
                  return date < earliestDiaryDate || date > today;
                }}
                onChange={(day) => day && updateDate(edge, day.format(diaryDateFormat))}
              />
            </div>
          );
        })}
      </div>
      <SelectField
        label="难度"
        value={filters.difficulty}
        options={[["all", "全部难度"], ...difficulties]}
        onChange={(difficulty) => update({ difficulty })}
      />
      <SelectField
        label="玩法"
        value={filters.mode ?? ""}
        options={[["", "全部玩法"], ...Object.entries(modeLabels)]}
        onChange={(mode) => update({ mode })}
      />
      <SelectField
        label="结局"
        wide
        value={filters.result ?? ""}
        options={[
          ["", "全部结局"],
          ["interrupted", results.interrupted],
          ["complete", results.complete],
          ...(history ? [["unknown", results.unknown] as [string, string]] : []),
        ]}
        onChange={(result) => update({ result })}
      />
    </div>
  );
}

function Diary({
  data,
  loadingFeed,
  offset,
  reportLink,
  changePage,
  rememberList,
}: {
  data?: StrongholdCommunity;
  loadingFeed: boolean;
  offset: number;
  reportLink: (id: string, index: number) => string;
  changePage: (offset: number) => void;
  rememberList: ReportLinkClick;
}) {
  if (!data) return null;
  const timeFormat = data.start_date === data.end_date ? "HH:mm:ss" : "YYYY-MM-DD HH:mm:ss";
  return (
    <>
      <StrongholdDiaryMetrics data={data} />
      <section className={styles.feed} aria-label="日报对局列表" aria-busy={loadingFeed}>
        <header className={styles.bandHeader}>
          <h3>对局记录</h3>
          <span>共 {data.total} 局</span>
        </header>
        {loadingFeed ? (
          <Loading />
        ) : data.matches.length ? (
          <ol className={styles.feedList}>
            {data.matches.map((match, index) => (
              <li className={styles.feedRow} key={match.id}>
                <div className={styles.feedMatch}>
                  <time dateTime={match.ended_at}>{formatBeijing(match.ended_at, timeFormat)}</time>
                  <BattleScope scope={match} version={match.version?.label} />
                  <ResultMark result={match.success} />
                </div>
                <div className={styles.feedMembers} aria-label="战报角色">
                  {match.participants.map((person) => (
                    <DiaryMember key={person.id} member={person} />
                  ))}
                </div>
                <Link
                  id={`stronghold-feed-${match.id}`}
                  className={styles.feedAction}
                  to={reportLink(match.id, index)}
                  preventScrollReset
                  onClick={(event) => rememberList(event, match.id)}
                  aria-label={`查看 ${formatBeijing(match.ended_at, timeFormat)} 的战报详情`}
                >
                  战报详情 <RightOutlined aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ol>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前筛选暂无对局" />
        )}
        {loadingFeed ? null : (
          <Pager total={data.total} offset={offset} pageSize={diaryPageSize} change={changePage} />
        )}
      </section>
    </>
  );
}

function Report({
  id,
  headingRef,
  report,
  battle,
  legacy,
  ownRoles,
  names,
}: {
  id: string;
  headingRef: RefObject<HTMLHeadingElement>;
  report: UseQueryResult<StrongholdMatch>;
  battle: string | null;
  legacy?: UseQueryResult<StrongholdRecordDetail>;
  ownRoles?: StrongholdOwn["roles"];
  names: BindingNames;
}) {
  const valid = recordPattern.test(id);
  const match = report.data;
  const request = legacy ?? report;
  return (
    <section className={reportStyles.report} data-embedded="true" aria-label="对局战报">
      <header className={reportStyles.reportHeader}>
        <h3 ref={headingRef} className={reportStyles.reportTitle} tabIndex={-1}>
          对局战报
        </h3>
      </header>
      {!valid || apiStatus(request.error) === 404 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={legacy ? "未找到此个人战报" : "战报不存在"}
        />
      ) : request.isError ? (
        <Failed error={request.error} retry={() => void request.refetch()} />
      ) : match ? (
        <StrongholdReportBoard
          key={`${match.id}:${battle ?? ""}`}
          match={ownRoles ? withOwnRoleNames(match, ownRoles, names) : match}
          requestedView={battle}
        />
      ) : (
        <Loading />
      )}
    </section>
  );
}

export function ArknightsStrongholdPanel({ title, ...controls }: ControlProps & { title: string }) {
  const [params, setParams] = useSearchParams();
  const oldMine = params.get("view") === "mine";
  const report = params.get("report");
  const battle = params.get("battle");
  const historyView =
    params.get("view") === "history" || oldMine || report !== null || battle !== null;
  const related = historyView && (oldMine || params.get("related") === "1");
  const legacyId = report === null ? battle : null;
  const season = params.get("season") ?? "";
  const difficulty = params.get("difficulty") ?? "";
  const mode = params.get("mode");
  const version = params.get("version") ?? "";
  const defaultVersion = historyView ? "all" : "latest";
  const baseDifficulty = historyView ? "all" : defaultDifficulty;
  const activeVersion = versionPattern.test(version) ? version : undefined;
  const resultParam = params.get("result");
  const result: StrongholdHistoryResult | undefined =
    resultParam === "complete" ||
    resultParam === "interrupted" ||
    (historyView && resultParam === "unknown")
      ? resultParam
      : undefined;
  const roleId = related ? positiveParam(params.get("role")) : undefined;
  const pageSize = historyView ? historyPageSize : diaryPageSize;
  const offset = Math.floor((positiveParam(params.get("offset")) ?? 0) / pageSize) * pageSize;
  const filters: ReportFilters = {
    version:
      version === "all" || version === "latest" ? version : (activeVersion ?? defaultVersion),
    season: historyView && scopePattern.test(season) ? season : undefined,
    difficulty: scopePattern.test(difficulty) ? difficulty : baseDifficulty,
    mode: mode === "single" || mode === "multi" || mode === "local" ? mode : undefined,
    dateRange: diaryDateRange(params),
    result,
  };
  const conditions = {
    version: filters.version === "all" ? undefined : filters.version,
    difficulty: filters.difficulty === "all" ? undefined : filters.difficulty,
    start_date: filters.dateRange?.start,
    end_date: filters.dateRange?.end,
    mode: filters.mode,
  };
  const diaryConditions = { ...conditions, result: result === "unknown" ? undefined : result };
  const diaryScopeKey = JSON.stringify(diaryConditions);
  const diaryParams = { ...diaryConditions, offset, limit: diaryPageSize };
  const diary = useQuery({
    ...queryOptions,
    queryKey: [...queryKey, "diary", diaryParams],
    queryFn: async () => ({
      scopeKey: diaryScopeKey,
      data: await fetchStrongholdCommunity(diaryParams),
    }),
    enabled: !historyView,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
  const appliedDiary = diary.data?.scopeKey === diaryScopeKey ? diary.data.data : undefined;

  const historyParams = {
    ...conditions,
    offset,
    limit: historyPageSize,
    season: filters.season,
    result,
    related,
    role_id: roleId,
  };
  const history = useQuery({
    ...queryOptions,
    queryKey: [...queryKey, "history", historyParams],
    queryFn: () => fetchStrongholdHistory(historyParams),
    enabled: historyView,
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
  const historyData = history.isPlaceholderData ? undefined : history.data;
  const latest = filters.version === "latest";
  const resolvedVersion = latest ? (historyData?.selected_version_key ?? undefined) : activeVersion;
  const ownParams = {
    limit: 1,
    ...(related
      ? { ...conditions, version: resolvedVersion, season: filters.season, role_id: roleId }
      : {}),
  };
  const own = useQuery({
    ...queryOptions,
    queryKey: [...queryKey, "own", ownParams],
    queryFn: () => fetchStrongholdOwn(ownParams),
    enabled: historyView,
    placeholderData: keepPreviousData,
    refetchInterval: ({ state }) =>
      state.data?.sync_status.some(
        ({ state: status }) =>
          status === "queued" || status === "discovering" || status === "syncing",
      )
        ? 8_000
        : 60_000,
  });
  const selectedEntry =
    report === null
      ? historyData?.matches[0]
      : historyData?.matches.find(({ id }) => id === report);
  const reportId = report ?? (legacyId === null ? selectedEntry?.id : null) ?? null;
  const detailId = reportId ?? legacyId;
  const requestedView = battle ?? selectedEntry?.preview?.id ?? null;
  const reportQuery = useQuery({
    ...queryOptions,
    queryKey: [...queryKey, "report", reportId],
    queryFn: () => fetchStrongholdReport(reportId!),
    enabled: historyView && reportId !== null && recordPattern.test(reportId),
  });
  const reportHeading = useRef<HTMLHeadingElement>(null);
  const pendingHistoryFocus = useRef<string | null>(null);
  const selectHistoryReport: ReportLinkClick = (event, id) => {
    if (!isPlainLinkClick(event) || !isStackedHistory(event.currentTarget)) return;
    if (report === id && !reportQuery.isPending) focusHistoryReport(reportHeading.current);
    else pendingHistoryFocus.current = id;
  };
  useLayoutEffect(() => {
    if (!historyView || pendingHistoryFocus.current !== report) pendingHistoryFocus.current = null;
    if (pendingHistoryFocus.current === null || reportQuery.isPending) return;
    // Wait for the detail to occupy its final space before scrolling past the list.
    pendingHistoryFocus.current = null;
    focusHistoryReport(reportHeading.current);
  }, [historyView, report, reportQuery.isPending]);
  const legacy = useQuery({
    ...queryOptions,
    queryKey: [...queryKey, "record", legacyId],
    queryFn: () => fetchStrongholdRecord(legacyId!),
    enabled: legacyId !== null && recordPattern.test(legacyId),
  });
  useEffect(() => {
    if (!legacyId || !legacy.data) return;
    const { id, match_id } = legacy.data;
    setParams(
      (previous) =>
        searchWith(previous, {
          view: "history",
          related: related ? 1 : null,
          report: match_id,
          battle: id,
        }),
      { replace: true, preventScrollReset: true },
    );
  }, [legacyId, legacy.data, related, setParams]);

  const listKey = diaryListKey(params);
  const listPosition = useRef<{ key: string; id: string; page: number } | null>(null);
  const rememberList: ReportLinkClick = (event, id) => {
    if (!isPlainLinkClick(event)) return;
    pendingHistoryFocus.current = id;
    listPosition.current = {
      key: listKey,
      id: event.currentTarget.id,
      page: document.getElementById("app-main")?.scrollTop ?? 0,
    };
    document.getElementById("app-main")?.scrollTo({ top: 0 });
  };
  const pageSearch: SearchPatch = historyView
    ? { view: "history", related: related ? 1 : null }
    : retiredDiaryFilters;
  const link: SearchLink = (patch) => `?${searchWith(params, { ...pageSearch, ...patch })}`;
  const update = (patch: SearchPatch) =>
    setParams((previous) => searchWith(previous, { ...pageSearch, ...patch }), {
      preventScrollReset: true,
    });
  const updateFilters = (patch: SearchPatch) =>
    update({ ...patch, offset: null, report: null, battle: null });
  const changePage = (next: number) => update({ offset: next, report: null, battle: null });
  const statsLink =
    historyView && listPosition.current
      ? `?${listPosition.current.key}`
      : link({
          view: null,
          related: null,
          report: null,
          battle: null,
          ...retiredDiaryFilters,
          offset: historyView ? null : offset,
          result: result === "unknown" ? null : result,
        });
  const diaryReportLink = (id: string, index: number) =>
    link({
      view: "history",
      related: null,
      version: filters.version,
      difficulty: filters.difficulty,
      ...resetDiaryDates,
      start_date: appliedDiary?.start_date,
      end_date: appliedDiary?.end_date,
      offset: Math.floor((offset + index) / historyPageSize) * historyPageSize || null,
      report: id,
      battle: null,
    });
  useLayoutEffect(() => {
    const old = listPosition.current;
    if (historyView || !old) return;
    if (old.key !== listKey) {
      listPosition.current = null;
      return;
    }
    if (!appliedDiary || diary.isPlaceholderData) return;
    document.getElementById("app-main")?.scrollTo({ top: old.page });
    document.getElementById(old.id)?.focus({ preventScroll: true });
    listPosition.current = null;
  }, [historyView, listKey, appliedDiary, diary.isPlaceholderData]);

  const names = boundRoleNames(controls.roles);
  const filtered = Boolean(
    filters.version !== defaultVersion ||
      filters.difficulty !== baseDifficulty ||
      filters.season ||
      filters.dateRange ||
      filters.mode ||
      filters.result ||
      roleId,
  );
  const reportPanel =
    detailId !== null ? (
      <Report
        id={detailId}
        headingRef={reportHeading}
        report={reportQuery}
        battle={requestedView}
        legacy={legacyId !== null ? legacy : undefined}
        ownRoles={own.data?.roles}
        names={names}
      />
    ) : null;

  return (
    <div className={styles.protocol} data-view={historyView ? "history" : "diary"}>
      <header className={`${arkStyles.sectionHeader} ${styles.protocolHeader}`}>
        <h2>{title}</h2>
        <div className={styles.headerActions}>
          <nav className={styles.viewNav} aria-label="卫戍协议视图">
            <Link aria-current={!historyView ? "page" : undefined} to={statsLink}>
              统计
            </Link>
            <Link
              aria-current={historyView ? "page" : undefined}
              to={link(
                historyView ? {} : { view: "history", report: null, battle: null, offset: null },
              )}
            >
              历史战绩
            </Link>
          </nav>
          <SearchControl
            key={historyView ? "history" : "diary"}
            filtered={filtered}
            reset={() => updateFilters(resetViewFilters)}
          >
            <ReportSearchFields
              filters={filters}
              data={historyView ? history.data : diary.data?.data}
              applied={historyView ? historyData !== undefined : appliedDiary !== undefined}
              history={historyView}
              roles={related ? (own.data?.roles ?? []) : undefined}
              roleId={roleId}
              names={names}
              update={updateFilters}
            />
            {historyView ? (
              <section className={styles.syncSection} aria-label="战绩同步">
                <h3>战绩同步</h3>
                {own.data ? (
                  <OwnControls {...controls} data={own.data} names={names} />
                ) : own.isError ? (
                  <Failed error={own.error} retry={() => void own.refetch()} />
                ) : (
                  <Loading />
                )}
              </section>
            ) : null}
          </SearchControl>
        </div>
      </header>
      {historyView ? (
        <>
          {related && own.data && !own.isPlaceholderData && (!latest || resolvedVersion) ? (
            <PersonalSummary data={own.data} />
          ) : null}
          <div className={styles.historyWorkbench}>
            <HistoryList
              request={history}
              related={related}
              toggleRelated={(checked) =>
                updateFilters({ related: checked ? 1 : null, role: null })
              }
              selected={reportQuery.data?.id ?? reportId}
              offset={offset}
              link={link}
              onSelect={selectHistoryReport}
              changePage={changePage}
            />
            {reportPanel ?? (
              <section className={reportStyles.report} data-embedded="true" aria-label="对局战报">
                <header className={reportStyles.reportHeader}>
                  <h3 className={reportStyles.reportTitle}>对局战报</h3>
                </header>
                {history.isPending || history.isPlaceholderData ? (
                  <Loading />
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无战报可查看" />
                )}
              </section>
            )}
          </div>
        </>
      ) : (
        <>
          <Diary
            data={appliedDiary}
            loadingFeed={diary.isPlaceholderData}
            offset={offset}
            reportLink={diaryReportLink}
            changePage={changePage}
            rememberList={rememberList}
          />
          {diary.isError ? (
            <Failed error={diary.error} retry={() => void diary.refetch()} />
          ) : diary.isPending || (diary.isPlaceholderData && !appliedDiary) ? (
            <Loading />
          ) : null}
        </>
      )}
    </div>
  );
}
