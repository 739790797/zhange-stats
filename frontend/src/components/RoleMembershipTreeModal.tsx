import { Alert, Modal, Spin, Tree, Typography, message } from "antd";
import type { DataNode } from "antd/es/tree";
import { useEffect, useMemo, useState } from "react";
import { apiError } from "@/lib/apiError";
import {
  CHECKIN_PLATFORM_LABELS,
  CheckinTreeNameLabel,
} from "@/components/checkinTaskDisplay";

export type RoleMembershipNode = {
  game_code: string;
  game_name: string;
  role_uid: string;
  role_name: string;
  channel_name?: string;
  included?: boolean;
};

export type RoleMembershipTree = {
  platform: string;
  roles: RoleMembershipNode[];
};

function leafKey(gameCode: string, roleUid: string) {
  return `role:${gameCode}:${roleUid}`;
}

function buildTreeNodes(
  platform: string,
  roles: RoleMembershipNode[],
): { tree: DataNode[]; defaultChecked: string[]; allLeafKeys: string[] } {
  const byGame = new Map<string, RoleMembershipNode[]>();
  for (const role of roles) {
    const list = byGame.get(role.game_code) || [];
    list.push(role);
    byGame.set(role.game_code, list);
  }

  const defaultChecked: string[] = [];
  const allLeafKeys: string[] = [];
  const tree: DataNode[] = [...byGame.entries()].map(([gameCode, list]) => {
    const gameName = list[0]?.game_name || gameCode;
    const children: DataNode[] = list.map((r) => {
      const key = leafKey(r.game_code, r.role_uid);
      allLeafKeys.push(key);
      // 新探测默认全选；已有 pref 时尊重 included
      const selected = r.included !== false;
      if (selected) defaultChecked.push(key);
      const label = r.channel_name
        ? `${r.role_name} · ${r.channel_name}`
        : r.role_name;
      return {
        key,
        title: <Typography.Text>{label}</Typography.Text>,
        isLeaf: true,
      };
    });
    return {
      key: `game:${gameCode}`,
      title: (
        <CheckinTreeNameLabel
          kind="game"
          platform={platform}
          gameCode={gameCode}
          label={`${gameName}（${list.length}）`}
        />
      ),
      children,
    };
  });

  return { tree, defaultChecked, allLeafKeys };
}

export type RoleMembershipTreeModalProps = {
  open: boolean;
  platform: string;
  /** 加载探测树；打开时调用 */
  loadTree: () => Promise<RoleMembershipTree>;
  /** 提交全部叶子的 included 状态 */
  saveMemberships: (
    roles: Array<{ game_code: string; role_uid: string; included: boolean }>,
  ) => Promise<void>;
  onClose: () => void;
  onSaved?: () => void;
  title?: string;
  /** 绑定后首次选择时默认全选；同步时尊重服务端 included */
  defaultSelectAllWhenUnset?: boolean;
};

export function RoleMembershipTreeModal({
  open,
  platform,
  loadTree,
  saveMemberships,
  onClose,
  onSaved,
  title,
  defaultSelectAllWhenUnset = true,
}: RoleMembershipTreeModalProps) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [roles, setRoles] = useState<RoleMembershipNode[]>([]);
  const [checkedKeys, setCheckedKeys] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    void (async () => {
      try {
        const tree = await loadTree();
        if (cancelled) return;
        const list = tree.roles || [];
        setRoles(list);
        const leafKeys = list.map((r) => leafKey(r.game_code, r.role_uid));
        const includedKeys = list
          .filter((r) => Boolean(r.included))
          .map((r) => leafKey(r.game_code, r.role_uid));
        // 新绑定：尚无任何已加入 → 默认全选；同步：尊重服务端 included
        if (defaultSelectAllWhenUnset && includedKeys.length === 0) {
          setCheckedKeys(leafKeys);
        } else {
          setCheckedKeys(includedKeys);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setLoadError(apiError(e, "探测角色失败"));
          setRoles([]);
          setCheckedKeys([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, platform, loadTree, defaultSelectAllWhenUnset]);

  const { tree, allLeafKeys } = useMemo(
    () => buildTreeNodes(platform, roles),
    [platform, roles],
  );

  const platformLabel =
    CHECKIN_PLATFORM_LABELS[platform] || platform;

  const onOk = async () => {
    const checked = new Set(checkedKeys);
    const payload = roles.map((r) => ({
      game_code: r.game_code,
      role_uid: r.role_uid,
      included: checked.has(leafKey(r.game_code, r.role_uid)),
    }));
    if (!payload.some((r) => r.included)) {
      message.warning("未选择角色：签到页将为空，可稍后在「我的日常」添加");
    }
    setSaving(true);
    try {
      await saveMemberships(payload);
      message.success("已保存加入本站的角色");
      onSaved?.();
      onClose();
    } catch (e: unknown) {
      message.error(apiError(e, "保存失败"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title={title || `选择要加入本站的角色 · ${platformLabel}`}
      onCancel={onClose}
      onOk={() => void onOk()}
      okText="确认加入"
      cancelText="稍后设置"
      confirmLoading={saving}
      destroyOnClose
      width={520}
    >
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        仅勾选的角色会出现在签到页；自动签到可在「我的日常」或签到页另行开启。
      </Typography.Paragraph>
      {loadError ? (
        <Alert type="error" showIcon message={loadError} style={{ marginBottom: 12 }} />
      ) : null}
      {loading ? (
        <div style={{ textAlign: "center", padding: 32 }}>
          <Spin tip="正在探测账号下的游戏角色…" />
        </div>
      ) : roles.length === 0 && !loadError ? (
        <Alert
          type="info"
          showIcon
          message="未探测到可加入的角色"
          description="账号下可能暂无支持的游戏角色，可稍后在「我的日常」同步。"
        />
      ) : (
        <Tree
          checkable
          defaultExpandAll
          checkedKeys={checkedKeys}
          onCheck={(keys) => {
            const next = Array.isArray(keys) ? keys : keys.checked;
            setCheckedKeys(
              (next as string[]).filter((k) => allLeafKeys.includes(k)),
            );
          }}
          treeData={tree}
        />
      )}
    </Modal>
  );
}
