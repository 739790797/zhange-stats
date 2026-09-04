import { describe, expect, it } from "vitest";
import {
  ICP_BEIAN_HREF,
  ICP_BEIAN_NO,
  LEGAL_DOCS,
  LEGAL_PRIVACY_PATH,
  LEGAL_TERMS_PATH,
  RAID_ROOM_TITLE_POLICY,
  TARKOV_PUBLIC_DISCLAIMER,
  legalDoc,
} from "./legalDocs";

describe("legal docs", () => {
  it("exposes terms and privacy routes", () => {
    expect(LEGAL_TERMS_PATH).toBe("/legal/terms");
    expect(LEGAL_PRIVACY_PATH).toBe("/legal/privacy");
  });

  it("exposes the ICP filing number for the site footer", () => {
    expect(ICP_BEIAN_NO).toBe("浙ICP备2025147006号");
    expect(ICP_BEIAN_HREF).toBe("https://beian.miit.gov.cn/");
    expect(legalDoc("terms").paragraphs.join("\n")).toContain(ICP_BEIAN_NO);
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
