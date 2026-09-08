import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Input, Modal, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useState } from "react";
import {
  fetchTarkovWorkbenchCommunityBuilds,
  type TarkovWorkbenchCommunityBuild,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { formatMoney } from "@/lib/tarkovItemFormat";
import {
  communityTagLabel,
  communityTagsInList,
  compareCommunityBuilds,
  filterCommunityBuilds,
  formatCommunityErgo,
  formatCommunityEvoDelta,
  formatCommunityPublishedAt,
  type CommunitySortKey,
} from "@/lib/tarkovCommunityBuilds";
import tableStyles from "@/components/guides/tarkov/TarkovDarkTable.module.css";
import styles from "./TarkovWorkbenchBuild.module.css";

type Props = {
  gunId: string;
  open: boolean;
  onCancel: () => void;
  onPick: (build: TarkovWorkbenchCommunityBuild) => void;
};

const SORT_DIRS: Array<"descend" | "ascend"> = ["descend", "ascend"];

function sorterOf(key: CommunitySortKey) {
  return (a: TarkovWorkbenchCommunityBuild, b: TarkovWorkbenchCommunityBuild) =>
    compareCommunityBuilds(a, b, key);
}

function CommunityTagChip({
  tag,
  active,
  onClick,
}: {
  tag: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const label = communityTagLabel(tag);
  if (onClick) {
    return (
      <button
        type="button"
        className={`${styles.communityChip}${active ? ` ${styles.communityChipActive}` : ""}`}
        data-tag={tag}
        onClick={onClick}
      >
        {label}
      </button>
    );
  }
  return (
    <span className={styles.communityChip} data-tag={tag}>
      {label}
    </span>
  );
}

export function TarkovWorkbenchCommunityModal({
  gunId,
  open,
  onCancel,
  onPick,
}: Props) {
  const gameMode = useTarkovGameMode();
  const [query, setQuery] = useState("");
  const [tags, setTags] = useState<string[]>([]);

  const listQuery = useQuery({
    queryKey: ["guides-tarkov-workbench-community", gameMode, gunId],
    queryFn: () => fetchTarkovWorkbenchCommunityBuilds(gunId),
    enabled: open && Boolean(gunId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const builds = listQuery.data?.builds;
  const tagOptions = useMemo(() => communityTagsInList(builds), [builds]);
  const rows = useMemo(
    () => filterCommunityBuilds(builds, query, tags),
    [builds, query, tags],
  );

  const columns = useMemo<ColumnsType<TarkovWorkbenchCommunityBuild>>(
    () => [
      {
        title: "方案名称",
        dataIndex: "name",
        key: "name",
        align: "left",
        width: 320,
        render: (_value, build) => (
          <div className={styles.communityNameCell}>
            <div className={styles.communityNameRow}>
              {build.featured ? <CommunityTagChip tag="featured" /> : null}
              <span className={styles.communityName}>{build.name}</span>
              {build.tags?.length ? (
                <span className={styles.communityCardTags}>
                  {build.tags.map((tag) => (
                    <CommunityTagChip key={tag} tag={tag} />
                  ))}
                </span>
              ) : null}
            </div>
            <span className={styles.communityMeta}>{build.author || "匿名"}</span>
            {build.dropped_pair_count ? (
              <span className={styles.communityDrop}>
                省略 {build.dropped_pair_count} 件本站没有的配件
              </span>
            ) : null}
          </div>
        ),
      },
      {
        title: "更新日期",
        key: "published_at",
        align: "left",
        width: 108,
        sorter: sorterOf("published_at"),
        sortDirections: SORT_DIRS,
        render: (_value, build) =>
          formatCommunityPublishedAt(build.published_at) || "—",
      },
      {
        title: "加载次数",
        dataIndex: "load_count",
        key: "load_count",
        align: "left",
        width: 80,
        sorter: sorterOf("load_count"),
        sortDirections: SORT_DIRS,
      },
      {
        title: "人工机效",
        key: "ergonomics",
        align: "left",
        width: 88,
        sorter: sorterOf("ergonomics"),
        sortDirections: SORT_DIRS,
        render: (_value, build) => formatCommunityErgo(build.preview?.ergonomics),
      },
      {
        title: "EVO人机DELTA",
        key: "evo_ergo_delta",
        align: "left",
        width: 124,
        sorter: sorterOf("evo_ergo_delta"),
        sortDirections: SORT_DIRS,
        render: (_value, build) => {
          const value = build.preview?.evo_ergo_delta;
          const text = formatCommunityEvoDelta(value);
          if (text === "—") return text;
          return (
            <span className={value != null && value >= 0 ? styles.statGood : styles.statBad}>
              {text}
            </span>
          );
        },
      },
      {
        title: "垂直后坐力",
        key: "recoil_vertical",
        align: "left",
        width: 100,
        sorter: sorterOf("recoil_vertical"),
        sortDirections: SORT_DIRS,
        render: (_value, build) => build.preview?.recoil_vertical ?? "—",
      },
      {
        title: "水平后坐力",
        key: "recoil_horizontal",
        align: "left",
        width: 100,
        sorter: sorterOf("recoil_horizontal"),
        sortDirections: SORT_DIRS,
        render: (_value, build) => build.preview?.recoil_horizontal ?? "—",
      },
      {
        title: "过摆",
        key: "overswing",
        align: "left",
        width: 56,
        sorter: sorterOf("overswing"),
        sortDirections: SORT_DIRS,
        render: (_value, build) => {
          if (!build.preview) return "—";
          return (
            <span className={build.preview.overswing ? styles.statBad : styles.statGood}>
              {build.preview.overswing ? "是" : "否"}
            </span>
          );
        },
      },
      {
        title: "费用",
        key: "price_rub",
        align: "left",
        width: 88,
        sorter: sorterOf("price_rub"),
        sortDirections: SORT_DIRS,
        render: (_value, build) => formatMoney(build.preview?.price_rub),
      },
      {
        title: "操作",
        key: "action",
        align: "left",
        width: 64,
        render: (_value, build) => (
          <Button
            type="link"
            size="small"
            disabled={!build.loadable}
            title={build.loadable ? undefined : "这套方案与当前图鉴对不上，无法装入"}
            onClick={() => onPick(build)}
          >
            加载
          </Button>
        ),
      },
    ],
    [onPick],
  );

  const toggleTag = (tag: string) => {
    setTags((current) =>
      current.includes(tag) ? current.filter((row) => row !== tag) : [...current, tag],
    );
  };

  return (
    <Modal
      open={open}
      title="社区方案"
      footer={
        <p className={styles.communityCredit}>
          列表来自 EFTForge 社区公开方案，按本站图鉴装入。不代为点赞或评论。
        </p>
      }
      destroyOnClose
      centered
      width="min(1180px, calc(100vw - 48px))"
      className={`${styles.gunPickModal} ${styles.communityModal}`}
      classNames={{
        body: styles.communityModalBody,
        content: styles.communityModalContent,
      }}
      onCancel={onCancel}
      afterClose={() => {
        setQuery("");
        setTags([]);
      }}
    >
      <Input
        allowClear
        size="small"
        placeholder="搜索方案或作者"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {tagOptions.length ? (
        <div className={styles.communityTags}>
          {tagOptions.map((tag) => (
            <CommunityTagChip
              key={tag}
              tag={tag}
              active={tags.includes(tag)}
              onClick={() => toggleTag(tag)}
            />
          ))}
        </div>
      ) : null}
      {listQuery.isLoading ? (
        <div className={styles.communityStatus}>
          <Spin tip="加载社区方案…" />
        </div>
      ) : listQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message={apiError(listQuery.error, "无法读取社区方案")}
        />
      ) : (
        <Table<TarkovWorkbenchCommunityBuild>
          className={`${tableStyles.table} ${styles.communityTable}`}
          size="small"
          rowKey="id"
          columns={columns}
          dataSource={rows}
          pagination={{
            align: "start",
            pageSize: 50,
            showSizeChanger: true,
            pageSizeOptions: ["20", "50", "100"],
          }}
          tableLayout="fixed"
          locale={{
            emptyText: builds?.length ? "没有匹配的方案" : "这把枪还没有公开方案",
          }}
        />
      )}
    </Modal>
  );
}
