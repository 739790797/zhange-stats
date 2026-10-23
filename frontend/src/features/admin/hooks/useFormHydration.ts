import type { FormInstance } from "antd";
import { useEffect, useRef } from "react";

type FieldList<T> = Parameters<FormInstance<T>["setFields"]>[0];

/** 回填并清掉 touched：之后回源的数据还能继续回填到这张表单。 */
export function hydrateForm<T>(form: FormInstance<T>, values: Partial<T>) {
  const fields = Object.entries(values as Record<string, unknown>).map(([name, value]) => ({
    name,
    value,
    touched: false,
  }));
  form.setFields(fields as FieldList<T>);
}

/**
 * data 到达或变化时回填，但用户已动过的表单不覆盖（别的卡片保存、回源刷新都不会冲掉正在填的内容）。
 * 本表单保存成功后由调用方用响应 hydrateForm 一次。
 */
export function useHydrateUntouchedForm<D, T>(
  form: FormInstance<T>,
  data: D | undefined,
  toValues: (data: D) => Partial<T>,
) {
  const toValuesRef = useRef(toValues);
  useEffect(() => {
    toValuesRef.current = toValues;
  });
  useEffect(() => {
    if (data === undefined) return;
    if (form.isFieldsTouched()) return;
    hydrateForm(form, toValuesRef.current(data));
  }, [data, form]);
}
