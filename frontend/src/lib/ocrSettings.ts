/** 文字识别管理页：档位分组、多端校验文案、检查更新任务 id。 */

export const OCR_MODEL_SYNC_JOB_ID = "ocr_model_sync";
export const OCR_MODEL_SYNC_JOB_NAME = "文字识别模型";

export type OcrProfileOption = {
  id: string;
  label: string;
  hint?: string;
};

export type OcrProfileSelectGroup = {
  label: string;
  options: Array<{ value: string; label: string }>;
};

export type OcrUseCaseFormValue = {
  engines: string[];
  cross_check: boolean;
};

export function groupOcrProfileOptions(
  rows: OcrProfileOption[] | null | undefined,
): OcrProfileSelectGroup[] {
  const groups = new Map<string, OcrProfileSelectGroup>();
  const order: string[] = [];
  for (const row of rows || []) {
    const id = (row.id || "").trim();
    if (!id) continue;
    const group = (row.hint || "").trim() || "PP-OCR";
    if (!groups.has(group)) {
      order.push(group);
      groups.set(group, { label: group, options: [] });
    }
    groups.get(group)!.options.push({
      value: id,
      label: row.label || id,
    });
  }
  return order.map((key) => groups.get(key)!);
}

export function crossCheckSaveError(input: {
  engines: Record<string, boolean> | null | undefined;
  useCases: Record<string, OcrUseCaseFormValue> | null | undefined;
  labels?: Record<string, string>;
}): string | null {
  const enabled = input.engines || {};
  for (const [id, row] of Object.entries(input.useCases || {})) {
    if (!row?.cross_check) continue;
    const active = (row.engines || []).filter((engine) => enabled[engine] !== false);
    if (active.length < 2) {
      const label = (input.labels && input.labels[id]) || id;
      return `${label} 开启了多端校验，请至少勾选两个不同模型族`;
    }
  }
  return null;
}
