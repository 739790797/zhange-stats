import { createCanvas, loadImage } from "@napi-rs/canvas";
import { setTarkovOcrCanvasFactory } from "@/lib/tarkovOcrEngine";

/** 只补画布和读图，不挂 document，避免 tesseract.js 走浏览器路径。 */
setTarkovOcrCanvasFactory(() => createCanvas(1, 1) as unknown as HTMLCanvasElement);

globalThis.createImageBitmap = async (source: Blob | ImageBitmap) => {
  if (source && typeof source === "object" && "width" in source && "close" in source) {
    return source as ImageBitmap;
  }
  const blob = source as Blob;
  const image = await loadImage(Buffer.from(await blob.arrayBuffer()));
  return Object.assign(image, { close() {} }) as unknown as ImageBitmap;
};
