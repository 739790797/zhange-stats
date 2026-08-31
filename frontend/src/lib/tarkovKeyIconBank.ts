import type { TarkovKeyOcrCatalogKey } from "@/lib/tarkovKeyOcr";
import keyIconIndex from "@/lib/tarkovKeyIconIndex.json";
import {
  templateFromIndexItem,
  type TarkovKeyIconIndexFile,
  type TarkovKeyIconTemplate,
} from "@/lib/tarkovKeyIconMatch";

/** 预计算的钥匙图标指纹。浏览器和夹具共用，不在粘贴时拉 256 张图。 */
export function loadKeyIconTemplates(
  catalog: TarkovKeyOcrCatalogKey[],
): TarkovKeyIconTemplate[] {
  const byId = new Map(catalog.map((key) => [key.id, key]));
  const file = keyIconIndex as TarkovKeyIconIndexFile;
  const out: TarkovKeyIconTemplate[] = [];
  for (const item of file.items || []) {
    const key = byId.get(item.id);
    if (byId.size && !key) continue;
    const tmpl = templateFromIndexItem(item);
    if (tmpl) out.push({ ...tmpl, short_name: key?.short_name });
  }
  return out;
}
