import { describe, expect, it } from "vitest";
import { formatRequestError } from "./formatRequestError";

describe("formatRequestError", () => {
  it("uses fallback for empty input", () => {
    expect(formatRequestError(null, "兜底")).toBe("兜底");
  });

  it("unwraps JSON string detail with msg", () => {
    expect(
      formatRequestError(
        {
          response: {
            status: 400,
            data: {
              detail:
                '{"retcode": -464, "msg": "请使用最新版本产品/链接以获得更佳体验，或前往user.mihoyo.com完成操作。"}',
            },
          },
        },
        "失败",
      ),
    ).toBe("请使用最新版本产品/链接以获得更佳体验，或前往user.mihoyo.com完成操作。");
  });

  it("joins validation array detail", () => {
    expect(
      formatRequestError(
        {
          response: {
            status: 422,
            data: { detail: [{ msg: "缺字段" }, { msg: "格式错" }] },
          },
        },
        "失败",
      ),
    ).toBe("缺字段；格式错");
  });

  it("maps axios network failure", () => {
    expect(
      formatRequestError(
        { isAxiosError: true, message: "Network Error", request: {} },
        "失败",
      ),
    ).toBe("无法连接服务器，请确认服务已启动");
  });

  it("keeps plain Error.message", () => {
    expect(formatRequestError(new Error("等待超时"), "失败")).toBe("等待超时");
  });

  it("maps 429 / 5xx defaults", () => {
    expect(
      formatRequestError({ response: { status: 429, data: {} } }, "失败"),
    ).toBe("请求过于频繁，请稍后再试");
    expect(
      formatRequestError({ response: { status: 503, data: {} } }, "失败"),
    ).toBe("服务暂时不可用，请稍后重试");
  });
});
