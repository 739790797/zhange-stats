import { Button, Input, Modal, Popconfirm, message } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState, type ReactNode } from "react";
import {
  createTarkovMapPlace,
  deleteTarkovMapPlace,
  importTarkovMapPlaces,
  patchTarkovMapPlace,
  type TarkovMapDetail,
  type TarkovMapPlace,
  type TarkovMapPlacePatch,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { isAdminUser } from "@/lib/isAdminUser";
import { findInteractiveMap, type TarkovDevMapLayer } from "@/lib/tarkovMapImages";
import {
  fallbackPlacesForImport,
  normalizePlaceName,
  placeLabelMovePatch,
  type TarkovMapPlaceEdit,
  type TarkovMapPlaceEditMode,
} from "@/lib/tarkovMapPlaceLabels";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovMapPlaceEditor.module.css";

type Draft = {
  kind: "point" | "box";
  id?: number;
  name: string;
  x: number;
  z: number;
  x2?: number;
  z2?: number;
  floor: string;
};

type Args = {
  slug: string;
  parentSlug?: string;
  places: TarkovMapPlace[];
  floor: string;
};

export function useTarkovMapPlaceEditor({
  slug,
  parentSlug,
  places,
  floor,
}: Args): {
  isAdmin: boolean;
  bar: ReactNode;
  modal: ReactNode;
  placeEdit?: TarkovMapPlaceEdit;
} {
  const me = useAuthStore((s) => s.user);
  const isAdmin = isAdminUser(me);
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [mode, setMode] = useState<TarkovMapPlaceEditMode>("select");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const layer = useMemo(
    () => findInteractiveMap(slug, parentSlug),
    [slug, parentSlug],
  );

  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({
      queryKey: ["guides-tarkov-map", gameMode, slug],
    });
  }, [gameMode, queryClient, slug]);

  const mergePlace = useCallback(
    (updated: TarkovMapPlace) => {
      queryClient.setQueryData<TarkovMapDetail>(
        ["guides-tarkov-map", gameMode, slug],
        (current) => {
          if (!current) return current;
          const list = current.places || [];
          return {
            ...current,
            places: list.some((row) => row.id === updated.id)
              ? list.map((row) => (row.id === updated.id ? updated : row))
              : [...list, updated],
          };
        },
      );
    },
    [gameMode, queryClient, slug],
  );

  const fail = (exc: unknown, fallback: string) => {
    message.error(apiError(exc, fallback));
  };

  const createMut = useMutation({
    mutationFn: (body: Draft) =>
      createTarkovMapPlace(slug, {
        kind: body.kind,
        name: normalizePlaceName(body.name),
        x: body.x,
        z: body.z,
        x2: body.kind === "box" ? body.x2 : null,
        z2: body.kind === "box" ? body.z2 : null,
        floor: body.floor || "",
      }),
    onSuccess: () => {
      setDraft(null);
      invalidate();
    },
    onError: (exc) => fail(exc, "保存地点失败"),
  });

  const patchMut = useMutation({
    mutationFn: (body: {
      id: number;
      patch: TarkovMapPlacePatch;
      keepDraft?: boolean;
    }) => patchTarkovMapPlace(slug, body.id, body.patch),
    onSuccess: (updated, vars) => {
      mergePlace(updated);
      if (!vars.keepDraft) setDraft(null);
      invalidate();
    },
    onError: (exc) => fail(exc, "更新地点失败"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteTarkovMapPlace(slug, id),
    onSuccess: () => {
      setDraft(null);
      setSelectedId(null);
      invalidate();
    },
    onError: (exc) => fail(exc, "删除地点失败"),
  });

  const importMut = useMutation({
    mutationFn: (layerArg: TarkovDevMapLayer) =>
      importTarkovMapPlaces(slug, fallbackPlacesForImport(layerArg)),
    onSuccess: () => {
      message.success("已接管此地，可以改名或加框");
      setEditing(true);
      setMode("select");
      invalidate();
    },
    onError: (exc) => fail(exc, "接管失败"),
  });

  const hasDb = places.length > 0;

  const placeEdit = useMemo<TarkovMapPlaceEdit | undefined>(() => {
    if (!isAdmin || !editing) return undefined;
    return {
      mode,
      selectedId,
      onPoint: (pt) => {
        setSelectedId(null);
        setDraft({
          kind: "point",
          name: "",
          x: pt.x,
          z: pt.z,
          floor: pt.floor || floor,
        });
      },
      onBox: (box) => {
        setSelectedId(null);
        setDraft({
          kind: "box",
          name: "",
          x: box.x,
          z: box.z,
          x2: box.x2,
          z2: box.z2,
          floor: box.floor || floor,
        });
      },
      onSelect: (id) => {
        const row = places.find((item) => item.id === id);
        if (!row) return;
        setSelectedId(id);
        setDraft({
          kind: row.kind === "box" ? "box" : "point",
          id: row.id,
          name: row.name,
          x: row.x,
          z: row.z,
          x2: row.x2 ?? undefined,
          z2: row.z2 ?? undefined,
          floor: row.floor || "",
        });
      },
      onMove: (id, at) => {
        const row = places.find((item) => item.id === id);
        if (!row) return;
        patchMut.mutate({
          id,
          patch: placeLabelMovePatch(row, at),
          keepDraft: true,
        });
      },
    };
  }, [editing, floor, isAdmin, mode, patchMut, places, selectedId]);

  const saveDraft = () => {
    if (!draft) return;
    const name = normalizePlaceName(draft.name);
    if (!name) {
      message.error("请填写地点名称");
      return;
    }
    if (draft.id) {
      patchMut.mutate({
        id: draft.id,
        patch: { name, floor: draft.floor || "" },
      });
      return;
    }
    createMut.mutate({ ...draft, name });
  };

  if (!isAdmin) {
    return { isAdmin, bar: null, modal: null, placeEdit: undefined };
  }

  const busy =
    createMut.isPending ||
    patchMut.isPending ||
    deleteMut.isPending ||
    importMut.isPending;

  const bar = (
    <div className={styles.bar}>
      <Button
        type="primary"
        onClick={() => {
          setEditing((on) => !on);
          setDraft(null);
          setSelectedId(null);
          setMode("select");
        }}
      >
        {editing ? "完成编辑" : "编辑地点"}
      </Button>
      {!hasDb ? (
        <Button
          onClick={() => {
            if (!layer) {
              message.error("这张图没有互动层，无法接管");
              return;
            }
            importMut.mutate(layer);
          }}
          loading={importMut.isPending}
        >
          接管此地
        </Button>
      ) : null}
      {editing ? (
        <div className={styles.tools}>
          {(
            [
              ["select", "选择"],
              ["point", "点"],
              ["box", "框"],
            ] as const
          ).map(([value, label]) => (
            <Button
              key={value}
              size="small"
              type={mode === value ? "primary" : undefined}
              onClick={() => setMode(value)}
            >
              {label}
            </Button>
          ))}
        </div>
      ) : null}
      <span className={styles.hint}>
        {!hasDb
          ? "尚未接管：加点会整表替换上游译名，建议先接管再改。"
          : editing
            ? mode === "point"
              ? "点击地图放置地点。"
              : mode === "box"
                ? "拖一个矩形圈出区域。"
                : "拖文字挪标注位置；点一下改名或删除。"
            : "全站玩家都会看到这里的社区叫法。"}
      </span>
    </div>
  );

  const modal = (
    <Modal
      title={draft?.id ? "编辑地点" : draft?.kind === "box" ? "新区域" : "新地点"}
      open={Boolean(draft)}
      onCancel={() => setDraft(null)}
      onOk={saveDraft}
      confirmLoading={busy}
      okText="保存"
      destroyOnClose
    >
      <Input.TextArea
        autoFocus
        maxLength={64}
        rows={3}
        placeholder={"社区叫法，可换行居中，如\n真别墅"}
        value={draft?.name || ""}
        onChange={(event) =>
          setDraft((prev) =>
            prev ? { ...prev, name: event.target.value } : prev,
          )
        }
      />
      <p className={`${styles.hint} ${styles.modalExtra}`}>
        回车换行，保存后各行都居中。
      </p>
      {draft?.id ? (
        <div className={styles.modalExtra}>
          <Popconfirm
            title="删除这个地点？"
            okText="删除"
            okButtonProps={{ danger: true }}
            onConfirm={() => deleteMut.mutate(draft.id!)}
          >
            <Button danger>删除</Button>
          </Popconfirm>
        </div>
      ) : !hasDb ? (
        <p className={`${styles.hint} ${styles.modalExtra}`}>
          这张图还没有社区地名，保存后将只显示你加的地点。
        </p>
      ) : null}
    </Modal>
  );

  return { isAdmin, bar, modal, placeEdit };
}
