import { describe, expect, it } from "vitest";
import {
  ICP_BEIAN_HREF,
  LEGAL_DOCS,
  LEGAL_PRIVACY_PATH,
  LEGAL_TERMS_PATH,
  RAID_ROOM_TITLE_POLICY,
  TARKOV_PUBLIC_DISCLAIMER,
  legalDoc,
  siteIcpBeianNo,
  termsTailParagraph,
} from "./legalDocs";

describe("legal docs", () => {
  it("exposes terms and privacy routes", () => {
    expect(LEGAL_TERMS_PATH).toBe("/legal/terms");
    expect(LEGAL_PRIVACY_PATH).toBe("/legal/privacy");
  });

  it("keeps the MIIT lookup URL and omits a baked-in filing number", () => {
    expect(ICP_BEIAN_HREF).toBe("https://beian.miit.gov.cn/");
    expect(LEGAL_DOCS.terms.paragraphs.join("\n")).not.toMatch(/ICP备/);
    expect(siteIcpBeianNo("  浙ICP备1号  ")).toBe("浙ICP备1号");
    expect(termsTailParagraph("")).not.toMatch(/ICP 备案/);
    expect(termsTailParagraph("浙ICP备1号")).toContain("浙ICP备1号");
    expect(legalDoc("terms", "京ICP备2号").paragraphs.join("\n")).toContain(
      "京ICP备2号",
    );
  });

  it("states unofficial, no-cheat, and room title rules", () => {
    expect(TARKOV_PUBLIC_DISCLAIMER).toContain("Battlestate");
    expect(TARKOV_PUBLIC_DISCLAIMER).toContain("作弊");
    expect(TARKOV_PUBLIC_DISCLAIMER).toContain("勾任务");
    expect(RAID_ROOM_TITLE_POLICY).toContain("禁止违法");
    const terms = legalDoc("terms").paragraphs.join("\n");
    expect(terms).toContain("透视");
    expect(terms).toContain(RAID_ROOM_TITLE_POLICY);
    const privacy = legalDoc("privacy").paragraphs.join("\n");
    expect(privacy).toContain("不保存游戏日志原文");
    expect(privacy).toContain("未入座者看不到棋盘、钥匙与人员名单");
  });

  it("covers both documents", () => {
    expect(LEGAL_DOCS.terms.title).toBe("服务条款");
    expect(LEGAL_DOCS.privacy.title).toBe("隐私说明");
  });
});
