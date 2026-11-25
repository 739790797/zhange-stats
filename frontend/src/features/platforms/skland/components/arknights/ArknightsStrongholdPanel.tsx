import {
  ArrowLeftOutlined,
  FilterOutlined,
  LeftOutlined,
  RightOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { Alert, App, Button, DatePicker, Empty, Spin } from "antd";
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
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchStrongholdCommunity,
  fetchStrongholdOwn,
  fetchStrongholdRecord,
  fetchStrongholdReport,
  strongholdQueryKey as queryKey,
  syncStrongholdRole,
  type StrongholdCommunity,
  type StrongholdMatch,
  type StrongholdMode,
  type StrongholdOwn,
  type StrongholdRecordDetail,
  type StrongholdRoleSelection,
  type StrongholdScope,
  type StrongholdVersion,
} from "@/features/platforms/skland/api/strongholdApi";
import type { SklandStatus } from "@/features/platforms/skland/api/types";
import { apiError, apiStatus } from "@/shared/api/apiError";
import { formatBeijing, nowBeijing, parseBeijing } from "@/shared/lib/time";
import { BattleIcon, BattleScope, ResultMark, StrategyMark } from "./StrongholdBattleUI";
import { DiaryMember, StrongholdDiaryMetrics } from "./StrongholdDiaryMetrics";
import { StrongholdReportBoard } from "./StrongholdReportBoard";
import {
  boundRoleNames,
  modeLabels,
  preferredRoleName,
  roleLabel,
  roleNamesLabel,
  withOwnRoleNames,
} from "./strongholdLabels";
import styles from "./ArknightsStronghold.module.css";
import reportStyles from "./StrongholdReport.module.css";

const pageSize = 12;
const scopePattern = /^[a-z0-9][a-z0-9_.-]{0,63}$/;
const versionPattern = /^[a-z0-9][a-z0-9_.-]{0,63}:[A-Za-z0-9_:.-]{1,128}$/;
const recordPattern = /^[a-f0-9]{32}$/;
const queryOptions = { staleTime: 0, gcTime: 0, retry: false };
const results = { complete: "模拟完成", interrupted: "模拟中断", unknown: "结果未知" } as const;

type SearchPatch = Record<string, string | number | null | undefined>;
type SearchLink = (updates: SearchPatch) => string;
type RememberList = (event: MouseEvent<HTMLAnchorElement>) => void;
type ScopeFilters = {
  season?: string;
  difficulty?: string;
  mode?: StrongholdMode;
  version?: string;
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

function positiveParam(value: string | null) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 && parsed <= 2_147_483_647 ? parsed : undefined;
}

function validDate(value: string | null) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value < "2019-01-01" || value > "2100-12-31")
    return undefined;
  return parseBeijing(value).format("YYYY-MM-DD") === value ? value : undefined;
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
}: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const caption = useId();
  return (
    <label className={styles.field}>
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

function ScopeFields({
  scopes,
  filters,
  update,
}: {
  scopes: StrongholdScope[];
  filters: ScopeFilters;
  update: (patch: SearchPatch) => void;
}) {
  const { season, difficulty, mode, version } = filters;
  const difficulties = new Map(
    scopes
      .filter(
        (scope) =>
          (!season || scope.season_id === season) && (!version || scope.version_key === version),
      )
      .map((scope) => [scope.difficulty_id, scope.difficulty_label]),
  );
  return (
    <>
      {season ? (
        <Button size="small" onClick={() => update({ season: null })}>
          清除旧赛季筛选
        </Button>
      ) : null}
      <SelectField
        label="模式"
        value={mode ?? ""}
        options={[["", "全部模式"], ...Object.entries(modeLabels)]}
        onChange={(value) => update({ mode: value })}
      />
      <SelectField
        label="难度"
        value={difficulty ?? ""}
        options={[["", "全部难度"], ...difficulties]}
        onChange={(value) => update({ difficulty: value })}
      />
    </>
  );
}

function Pager({
  total,
  offset,
  change,
}: {
  total: number;
  offset: number;
  change: (offset: number) => void;
}) {
  return offset || total > pageSize ? (
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

function OwnDesk({
  data,
  loading,
  controls,
  names,
  filters,
  roleId,
  result,
  offset,
  link,
  selectedBattle,
  detail,
  update,
  changePage,
}: {
  data: StrongholdOwn;
  controls: ControlProps;
  names: BindingNames;
  filters: ScopeFilters;
  roleId?: number;
  result?: string;
  loading: boolean;
  offset: number;
  link: SearchLink;
  selectedBattle: string | null;
  detail: ReactNode;
  update: (patch: SearchPatch) => void;
  changePage: (offset: number) => void;
}) {
  const filterPanel = useId();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const filterCount = [roleId, result, filters.mode, filters.difficulty, filters.season].filter(
    Boolean,
  ).length;
  const rate = data.known_results
    ? `${((data.wins * 100) / data.known_results).toFixed(1).replace(/\.0$/, "")}%`
    : "—";
  return (
    <>
      <div className={styles.overviewTools}>
        <button
          className={styles.filterToggle}
          type="button"
          aria-expanded={filtersOpen}
          aria-controls={filterPanel}
          onClick={() => setFiltersOpen((open) => !open)}
        >
          <FilterOutlined aria-hidden="true" /> 筛选与同步{filterCount ? ` · ${filterCount}` : null}
        </button>
        <div id={filterPanel} className={styles.overviewFilters} data-expanded={filtersOpen}>
          <OwnControls {...controls} data={data} names={names} />
          <div className={styles.toolbar}>
            <SelectField
              label="查看角色"
              value={String(roleId ?? "")}
              options={[
                ["", "全部角色"],
                ...data.roles.map(({ id, channel_id, uid, role_name }): [string, string] => {
                  const name = preferredRoleName(names.get(`${channel_id}:${uid}`), role_name, uid);
                  return [
                    String(id),
                    `${roleLabel(name)} · ${channel_id === "1" ? "官服" : "B 服"}`,
                  ];
                }),
              ]}
              onChange={(value) => update({ role: value })}
            />
            <ScopeFields scopes={data.scopes} filters={filters} update={update} />
            <SelectField
              label="结果"
              value={result ?? ""}
              options={[["", "全部结果"], ...Object.entries(results)]}
              onChange={(value) => update({ result: value })}
            />
          </div>
        </div>
        <dl className={styles.recordStats} aria-busy={loading}>
          <div>
            <dt>已同步战报</dt>
            <dd>{data.scoped_total}</dd>
          </div>
          <div>
            <dt>模拟完成</dt>
            <dd>
              {data.wins} <small>/ {data.known_results} 局已知结果</small>
            </dd>
          </div>
          <div>
            <dt>已知胜率</dt>
            <dd>{rate}</dd>
          </div>
        </dl>
      </div>
      <div className={styles.ownWorkbench} data-has-detail={detail != null}>
        <section className={`${styles.feed} ${styles.history}`} aria-label="个人战绩列表">
          <header className={styles.bandHeader}>
            <h3>战绩列表</h3>
            <span>共 {data.total} 条</span>
          </header>
          {loading ? (
            <Loading />
          ) : data.records.length ? (
            <ul className={styles.recordList}>
              {data.records.map((record) => (
                <li
                  key={record.id}
                  className={styles.recordItem}
                  data-result={
                    record.completed == null ? "unknown" : record.completed ? "win" : "loss"
                  }
                  data-selected={record.id === selectedBattle}
                >
                  <div className={styles.recordStrategy}>
                    <StrategyMark
                      icon={record.strategy_icon_url}
                      name={record.strategy_name ?? record.strategy_id}
                      description={record.strategy_description}
                    />
                  </div>
                  <Link
                    className={styles.recordRow}
                    to={link({ report: record.match_id, battle: record.id })}
                    preventScrollReset
                    aria-current={record.id === selectedBattle ? "true" : undefined}
                  >
                    <span className={styles.recordRowTop}>
                      <strong>{record.difficulty_label}</strong>
                      <span>{record.pass_round == null ? "—" : `${record.pass_round} 回合`}</span>
                    </span>
                    <span className={styles.recordRowTop}>
                      <span>{record.mode_type ? modeLabels[record.mode_type] : "模式未记录"}</span>
                      <ResultMark result={record.completed} />
                    </span>
                    <time dateTime={record.ended_at}>
                      {formatBeijing(record.ended_at, "YYYY-MM-DD HH:mm")}
                    </time>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={data.scoped_total ? "当前筛选无战报" : "暂无已同步的个人战报"}
            />
          )}
          {!loading ? <Pager total={data.total} offset={offset} change={changePage} /> : null}
        </section>
        {detail}
      </div>
    </>
  );
}

function Diary({
  data,
  loadingFeed,
  filters,
  date,
  member,
  offset,
  link,
  update,
  changePage,
  rememberList,
}: {
  data?: StrongholdCommunity;
  loadingFeed: boolean;
  filters: ScopeFilters;
  date?: string;
  member?: number;
  offset: number;
  link: SearchLink;
  update: (patch: SearchPatch) => void;
  changePage: (offset: number) => void;
  rememberList: RememberList;
}) {
  const selectedDate = date ?? data?.today ?? nowBeijing().format("YYYY-MM-DD");
  const dateId = useId();
  const lastPlayed = data?.versions.find(({ key }) => key === filters.version)?.last_played_date;
  const linkMember = (id: number) => link({ member: id, offset: null });
  return (
    <>
      <div className={styles.toolbar}>
        <label className={styles.field} htmlFor={dateId}>
          <span>日报日期</span>
          <DatePicker
            id={dateId}
            aria-label="日报日期"
            value={parseBeijing(selectedDate)}
            format="YYYY-MM-DD"
            allowClear={false}
            disabledDate={(day) =>
              day.format("YYYY-MM-DD") < "2019-01-01" ||
              day.format("YYYY-MM-DD") > (data?.today ?? nowBeijing().format("YYYY-MM-DD"))
            }
            onChange={(day) => update({ date: day?.format("YYYY-MM-DD") })}
          />
        </label>
        <Button onClick={() => update({ date: null })}>今日</Button>
        <span className={styles.muted}>北京时间</span>
        {!loadingFeed &&
        lastPlayed &&
        lastPlayed !== selectedDate &&
        data?.coverage.matches === 0 ? (
          <Button onClick={() => update({ date: lastPlayed, member: null })}>
            查看最近战绩日 {lastPlayed}
          </Button>
        ) : null}
      </div>
      {data ? (
        <>
          {loadingFeed ? null : <StrongholdDiaryMetrics data={data} link={linkMember} />}
          <section className={styles.feed} aria-label="日报对局列表">
            <header className={styles.bandHeader}>
              <h3>对局记录</h3>
              <span>{loadingFeed ? "加载中" : `共 ${data.total} 局`}</span>
            </header>
            <div className={`${styles.toolbar} ${styles.listToolbar}`} aria-label="筛选对局列表">
              <ScopeFields scopes={data.scopes} filters={filters} update={update} />
            </div>
            {member ? (
              <div className={styles.memberFilter}>
                <span>
                  仅看{" "}
                  {roleNamesLabel(loadingFeed ? undefined : data.filtered_role_names, "所选成员")}{" "}
                  的对局
                </span>
                <Button size="small" onClick={() => update({ member: null })}>
                  清除
                </Button>
              </div>
            ) : null}
            {loadingFeed ? (
              <Loading />
            ) : data.matches.length ? (
              <ol className={styles.feedList}>
                {data.matches.map((match) => (
                  <li className={styles.feedRow} key={match.id}>
                    <div className={styles.feedMatch}>
                      <time dateTime={match.ended_at}>
                        {formatBeijing(match.ended_at, "HH:mm:ss")}
                      </time>
                      <BattleScope scope={match} version={match.version?.label} />
                      {match.success != null ? <ResultMark result={match.success} /> : null}
                    </div>
                    <div className={styles.feedMembers} aria-label="战报角色">
                      {match.participants.map((person) => (
                        <DiaryMember key={person.id} member={person} link={linkMember} />
                      ))}
                    </div>
                    <Link
                      id={`stronghold-feed-${match.id}`}
                      className={styles.feedAction}
                      to={link({ report: match.id, battle: null })}
                      preventScrollReset
                      onClick={rememberList}
                      aria-label={`查看 ${formatBeijing(match.ended_at, "HH:mm:ss")} 的战报详情`}
                    >
                      战报详情 <RightOutlined aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ol>
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="当天暂无符合筛选条件的对局"
              />
            )}
            {loadingFeed ? null : <Pager total={data.total} offset={offset} change={changePage} />}
          </section>
        </>
      ) : null}
    </>
  );
}

function Report({
  id,
  backTo,
  report,
  battle,
  legacy,
  ownRoles,
  names,
}: {
  id: string;
  backTo?: string;
  report: UseQueryResult<StrongholdMatch>;
  battle: string | null;
  legacy?: UseQueryResult<StrongholdRecordDetail>;
  ownRoles?: StrongholdOwn["roles"];
  names: BindingNames;
}) {
  const valid = recordPattern.test(id);
  const heading = useRef<HTMLHeadingElement>(null);
  useLayoutEffect(() => {
    if (!backTo) return;
    heading.current?.focus({ preventScroll: true });
    document.getElementById("app-main")?.scrollTo({ top: 0 });
  }, [id, backTo]);
  const match = report.data;
  const request = legacy ?? report;
  return (
    <section className={reportStyles.report} data-embedded={!backTo} aria-label="对局战报">
      <header className={reportStyles.reportHeader}>
        <div className={reportStyles.reportTitle}>
          {backTo ? (
            <Link to={backTo} preventScrollReset>
              <ArrowLeftOutlined /> 返回卫戍日报
            </Link>
          ) : null}
          <h3 ref={heading} tabIndex={-1}>
            对局战报
          </h3>
        </div>
        {match ? (
          <div className={reportStyles.matchMeta}>
            <BattleScope scope={match} version={match.version?.label} />
            <ResultMark result={match.success} />
            <time dateTime={match.ended_at}>
              {formatBeijing(match.ended_at, "YYYY-MM-DD HH:mm:ss")}
            </time>
          </div>
        ) : null}
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

function ThemeTitle({ version }: { version?: StrongholdVersion | null }) {
  const [failed, setFailed] = useState<string | null>(null);
  return (
    <>
      {version?.banner_url && failed !== version.banner_url ? (
        <div className={styles.heroArt} aria-hidden="true">
          <img
            src={version.banner_url}
            alt=""
            referrerPolicy="no-referrer"
            onError={() => setFailed(version.banner_url!)}
          />
        </div>
      ) : null}
      <div className={styles.heroTitle}>
        <BattleIcon src={version?.emblem_url} fallback={<SafetyCertificateOutlined />} />
        <div>
          <h2>卫戍协议</h2>
          {version ? <p>{version.label}</p> : null}
        </div>
      </div>
    </>
  );
}

export function ArknightsStrongholdPanel(controls: ControlProps) {
  const [params, setParams] = useSearchParams();
  const mine = params.get("view") === "mine";
  const report = params.get("report");
  const battle = report !== null || mine ? params.get("battle") : null;
  const legacyId = report === null ? battle : null;
  const explicitDetail = report ?? legacyId;
  const season = params.get("season") ?? "";
  const difficulty = params.get("difficulty") ?? "";
  const mode = params.get("mode");
  const version = params.get("version") ?? "";
  const activeVersion = versionPattern.test(version) ? version : undefined;
  const resultParam = params.get("result");
  const result: keyof typeof results | undefined =
    resultParam === "complete" || resultParam === "interrupted" || resultParam === "unknown"
      ? resultParam
      : undefined;
  const date = validDate(params.get("date"));
  const member = positiveParam(params.get("member"));
  const roleId = positiveParam(params.get("role"));
  const offset = positiveParam(params.get("offset")) ?? 0;
  const scope: ScopeFilters = {
    version: activeVersion,
    season: scopePattern.test(season) ? season : undefined,
    difficulty: scopePattern.test(difficulty) ? difficulty : undefined,
    mode: mode === "single" || mode === "multi" || mode === "local" ? mode : undefined,
  };
  const list = { ...scope, offset, limit: pageSize };
  const diaryParams = { ...list, date, member };
  const ownParams = { ...list, role_id: roleId, result };
  const diary = useQuery({
    ...queryOptions,
    queryKey: [...queryKey, "diary", diaryParams],
    queryFn: () => fetchStrongholdCommunity(diaryParams),
    enabled: !mine && explicitDetail === null,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
  const own = useQuery({
    ...queryOptions,
    queryKey: [...queryKey, "own", ownParams],
    queryFn: () => fetchStrongholdOwn(ownParams),
    enabled: mine,
    placeholderData: keepPreviousData,
    refetchInterval: ({ state }) =>
      state.data?.sync_status.some(
        ({ state: status }) =>
          status === "queued" || status === "discovering" || status === "syncing",
      )
        ? 8_000
        : 60_000,
  });
  const pageRecords = own.isPlaceholderData ? undefined : own.data?.records;
  const selectedRecord = mine
    ? explicitDetail === null
      ? pageRecords?.[0]
      : pageRecords?.find((record) => (battle ? record.id === battle : record.match_id === report))
    : undefined;
  const reportId = report ?? (legacyId === null ? selectedRecord?.match_id : null) ?? null;
  const detailId = reportId ?? legacyId;
  const requestedView = battle ?? selectedRecord?.id ?? null;
  const reportQuery = useQuery({
    ...queryOptions,
    queryKey: [...queryKey, "report", reportId],
    queryFn: () => fetchStrongholdReport(reportId!),
    enabled: reportId !== null && recordPattern.test(reportId),
  });
  const legacy = useQuery({
    ...queryOptions,
    queryKey: [...queryKey, "record", legacyId],
    queryFn: () => fetchStrongholdRecord(legacyId!),
    enabled: legacyId !== null && recordPattern.test(legacyId),
  });
  useEffect(() => {
    if (!legacyId || !legacy.data) return;
    const { id, match_id } = legacy.data;
    setParams((previous) => searchWith(previous, { report: match_id, battle: id }), {
      replace: true,
      preventScrollReset: true,
    });
  }, [legacyId, legacy.data, setParams]);

  const listParams = searchWith(params, { report: null, battle: null });
  listParams.sort();
  const listKey = listParams.toString();
  const listPosition = useRef<{ key: string; id: string; page: number } | null>(null);
  const rememberList: RememberList = (event) => {
    if (event.button !== 0 || event.metaKey || event.altKey || event.shiftKey || event.ctrlKey)
      return;
    listPosition.current = {
      key: listKey,
      id: event.currentTarget.id,
      page: document.getElementById("app-main")?.scrollTop ?? 0,
    };
  };
  const link: SearchLink = (patch) => `?${searchWith(params, patch)}`;
  const update = (patch: SearchPatch) =>
    setParams((previous) => searchWith(previous, patch), { preventScrollReset: true });
  const updateFilters = (patch: SearchPatch) =>
    update({ ...patch, offset: null, report: null, battle: null });
  const changePage = (next: number) => update({ offset: next, report: null, battle: null });
  const query = mine ? own : diary;
  useLayoutEffect(() => {
    const old = listPosition.current;
    if (mine || explicitDetail !== null || !old) return;
    if (old.key !== listKey) {
      listPosition.current = null;
      return;
    }
    if (!query.data || query.isPlaceholderData) return;
    document.getElementById("app-main")?.scrollTo({ top: old.page });
    document.getElementById(old.id)?.focus({ preventScroll: true });
    listPosition.current = null;
  }, [mine, explicitDetail, listKey, query.data, query.isPlaceholderData]);

  const versions = query.data?.versions ?? [];
  const names = boundRoleNames(controls.roles);
  const reportPanel =
    detailId !== null ? (
      <Report
        id={detailId}
        backTo={mine ? undefined : link({ report: null, battle: null })}
        report={reportQuery}
        battle={requestedView}
        legacy={legacyId !== null ? legacy : undefined}
        ownRoles={mine ? own.data?.roles : undefined}
        names={names}
      />
    ) : null;
  if (!mine && reportPanel) {
    return <div className={styles.protocol}>{reportPanel}</div>;
  }
  const theme = activeVersion ? versions.find(({ key }) => key === activeVersion) : versions[0];
  return (
    <div className={styles.protocol}>
      <header className={styles.protocolHeader}>
        <ThemeTitle version={theme} />
        <div className={styles.heroControls}>
          {versions.length > 0 || activeVersion ? (
            <SelectField
              label="版本"
              value={activeVersion ?? ""}
              options={[
                ["", "全部版本"],
                ...versions.map(({ key, label }): [string, string] => [key, label]),
              ]}
              onChange={(version) => updateFilters({ version, season: null, difficulty: null })}
            />
          ) : null}
          <nav className={styles.viewNav} aria-label="卫戍协议视图">
            <Link
              aria-current={!mine ? "page" : undefined}
              to={link({ view: null, report: null, battle: null, offset: mine ? null : offset })}
            >
              卫戍日报
            </Link>
            <Link
              aria-current={mine ? "page" : undefined}
              to={link({ view: "mine", report: null, battle: null, offset: mine ? offset : null })}
            >
              战绩总览
            </Link>
          </nav>
        </div>
      </header>
      {mine && own.data ? (
        <OwnDesk
          data={own.data}
          loading={own.isPlaceholderData}
          controls={controls}
          names={names}
          filters={scope}
          roleId={roleId}
          result={result}
          offset={offset}
          link={link}
          selectedBattle={selectedRecord?.id ?? null}
          detail={reportPanel}
          update={updateFilters}
          changePage={changePage}
        />
      ) : mine ? (
        reportPanel
      ) : (
        <Diary
          data={diary.data}
          loadingFeed={diary.isPlaceholderData}
          filters={scope}
          date={date}
          member={member}
          offset={offset}
          link={link}
          update={updateFilters}
          changePage={changePage}
          rememberList={rememberList}
        />
      )}
      {query.isError ? (
        <Failed error={query.error} retry={() => void query.refetch()} />
      ) : query.isPending ? (
        <Loading />
      ) : null}
    </div>
  );
}
