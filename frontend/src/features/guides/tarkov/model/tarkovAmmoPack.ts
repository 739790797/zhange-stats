import { hdPreviewUrl, transparentThumbUrl } from "./tarkovItemImages";

/** 仅手册弹药包图；对不上包时留空，不拿单发子弹图充数。 */
export function ammoPackDisplayUrls(row: {
  pack_icon_link?: string | null;
}): { thumb: string; hd: string } {
  const pack = (row.pack_icon_link || "").trim();
  if (!pack) return { thumb: "", hd: "" };
  const thumb = transparentThumbUrl(pack) || pack;
  return { thumb, hd: hdPreviewUrl(pack) || thumb };
}
