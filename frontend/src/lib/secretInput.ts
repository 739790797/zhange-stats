/** 只写密钥栏的占位：服务端只回是否已设（*_set）与末几位（*_hint），从不回原值。 */
export function secretPlaceholder({
  set,
  hint,
  clearing,
  empty,
}: {
  set: boolean;
  hint?: string | null;
  clearing?: boolean;
  empty: string;
}): string {
  if (clearing) return "保存后清除";
  if (!set) return empty;
  const tail = (hint || "").trim();
  return tail ? `已设置（…${tail}），留空不修改` : "已设置，留空不修改";
}

/** 留空发 null（后端保留原值）；要清除时不带新值，清除标记另发 clear_*。 */
export function secretPayloadValue(
  value: string | null | undefined,
  clearing: boolean,
): string | null {
  if (clearing) return null;
  return (value || "").trim() || null;
}
