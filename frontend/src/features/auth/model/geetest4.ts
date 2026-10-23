/** 库街区官方极验 4（GeeTest）人机验证封装，不绕过。 */

const GT4_SCRIPT_URL = "https://static.geetest.com/v4/gt4.js";

/** 库街区 APP 端 captchaId，与后端 GEETEST_CAPTCHA_ID 一致 */
export const KUJIEQU_GEETEST_CAPTCHA_ID =
  "3f7e2d848ce0cb7e7d019d621e556ce2";

export type Geetest4Validate = {
  captcha_id: string;
  lot_number: string;
  pass_token: string;
  gen_time: string;
  captcha_output: string;
};

type Geetest4Captcha = {
  showCaptcha: () => void;
  getValidate: () => Omit<Geetest4Validate, "captcha_id"> | false | null;
  reset: () => void;
  onReady: (cb: () => void) => Geetest4Captcha;
  onSuccess: (cb: () => void) => Geetest4Captcha;
  onError: (cb: (err?: unknown) => void) => Geetest4Captcha;
  onClose: (cb: () => void) => Geetest4Captcha;
};

declare global {
  interface Window {
    initGeetest4?: (
      config: Record<string, unknown>,
      callback: (captcha: Geetest4Captcha) => void,
    ) => void;
  }
}

let scriptPromise: Promise<void> | null = null;

function loadGt4Script(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("极验仅可在浏览器中使用"));
  }
  if (window.initGeetest4) {
    return Promise.resolve();
  }
  if (scriptPromise) {
    return scriptPromise;
  }
  scriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${GT4_SCRIPT_URL}"]`,
    );
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () =>
        reject(new Error("极验脚本加载失败")),
      );
      if (window.initGeetest4) resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = GT4_SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      scriptPromise = null;
      reject(new Error("极验脚本加载失败，请检查网络后重试"));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

type PendingRun = {
  captchaId: string;
  resolve: (value: Geetest4Validate) => void;
  reject: (reason: Error) => void;
};

type CaptchaSlot = {
  captcha: Geetest4Captcha;
  ready: Promise<void>;
  pending: PendingRun | null;
};

const captchaCache = new Map<string, Promise<CaptchaSlot>>();

function getCaptchaSlot(captchaId: string): Promise<CaptchaSlot> {
  const existing = captchaCache.get(captchaId);
  if (existing) return existing;

  const created = new Promise<CaptchaSlot>((resolve, reject) => {
    if (!window.initGeetest4) {
      captchaCache.delete(captchaId);
      reject(new Error("极验未就绪"));
      return;
    }
    window.initGeetest4(
      {
        captchaId,
        product: "bind",
        language: "zho",
        protocol: "https://",
        timeout: 15000,
      },
      (captcha) => {
        let readyResolve: () => void = () => undefined;
        const ready = new Promise<void>((r) => {
          readyResolve = r;
        });
        const slot: CaptchaSlot = { captcha, ready, pending: null };

        captcha.onReady(() => readyResolve());

        captcha.onSuccess(() => {
          const pending = slot.pending;
          slot.pending = null;
          if (!pending) return;
          const raw = captcha.getValidate();
          try {
            captcha.reset();
          } catch {
            /* ignore */
          }
          if (!raw || typeof raw !== "object") {
            pending.reject(new Error("极验结果无效，请重试"));
            return;
          }
          pending.resolve({
            captcha_id: pending.captchaId,
            lot_number: String(raw.lot_number || ""),
            pass_token: String(raw.pass_token || ""),
            gen_time: String(raw.gen_time || ""),
            captcha_output: String(raw.captcha_output || ""),
          });
        });

        captcha.onClose(() => {
          const pending = slot.pending;
          slot.pending = null;
          if (!pending) return;
          pending.reject(new Error("请完成人机验证后再发送短信"));
        });

        captcha.onError(() => {
          const pending = slot.pending;
          slot.pending = null;
          if (pending) {
            pending.reject(new Error("极验加载异常，请刷新后重试"));
          }
        });

        resolve(slot);
      },
    );
  });

  captchaCache.set(captchaId, created);
  created.catch(() => captchaCache.delete(captchaId));
  return created;
}

/**
 * 弹出官方极验验证框，成功后返回可提交给库街区的 geeTestData 字段对象。
 * 用户关闭未完成时 reject。
 */
export async function runGeetest4(
  captchaId: string = KUJIEQU_GEETEST_CAPTCHA_ID,
): Promise<Geetest4Validate> {
  const id = (captchaId || KUJIEQU_GEETEST_CAPTCHA_ID).trim();
  await loadGt4Script();
  const slot = await getCaptchaSlot(id);
  await slot.ready;

  if (slot.pending) {
    slot.pending.reject(new Error("已有进行中的人机验证"));
    slot.pending = null;
  }

  return new Promise((resolve, reject) => {
    slot.pending = { captchaId: id, resolve, reject };
    try {
      slot.captcha.showCaptcha();
    } catch (e) {
      slot.pending = null;
      reject(e instanceof Error ? e : new Error("无法打开极验验证"));
    }
  });
}

/** 预加载脚本并初始化（挂载绑定面板时调用，便于采集行为数据） */
export async function prefetchGeetest4(
  captchaId: string = KUJIEQU_GEETEST_CAPTCHA_ID,
): Promise<void> {
  try {
    await loadGt4Script();
    const slot = await getCaptchaSlot(captchaId);
    await slot.ready;
  } catch {
    /* 预加载失败不阻断；真正发送时会再试 */
  }
}
