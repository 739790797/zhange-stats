import { describe, expect, it } from "vitest";
import {
  MYSQL_CONN_DEFAULTS,
  REDIS_CONN_DEFAULTS,
  composeMysqlUrl,
  composeRedisUrl,
  parseMysqlUrl,
  parseRedisUrl,
} from "./runtimeConn";

describe("parseMysqlUrl / composeMysqlUrl", () => {
  it("round-trips the common pymysql URL", () => {
    const url = "mysql+pymysql://root:zsb000613@127.0.0.1:3306/circlestats";
    expect(parseMysqlUrl(url)).toEqual({
      host: "127.0.0.1",
      port: 3306,
      user: "root",
      password: "zsb000613",
      database: "circlestats",
    });
    expect(composeMysqlUrl(parseMysqlUrl(url))).toBe(url);
  });

  it("accepts mysql:// and fills the default port", () => {
    expect(parseMysqlUrl("mysql://u:p@db.example.com/zhange")).toEqual({
      host: "db.example.com",
      port: 3306,
      user: "u",
      password: "p",
      database: "zhange",
    });
  });

  it("encodes special characters in the password", () => {
    const conn: Parameters<typeof composeMysqlUrl>[0] = {
      host: "127.0.0.1",
      port: 3306,
      user: "root",
      password: "p@ss:w/d",
      database: "zhange",
    };
    const url = composeMysqlUrl(conn);
    expect(url).toContain(encodeURIComponent("p@ss:w/d"));
    expect(parseMysqlUrl(url)).toEqual(conn);
  });

  it("wraps IPv6 hosts", () => {
    const url = composeMysqlUrl({
      host: "::1",
      port: 3306,
      user: "root",
      password: "x",
      database: "zhange",
    });
    expect(url).toContain("[::1]");
    expect(parseMysqlUrl(url).host).toBe("::1");
  });

  it("returns defaults for empty or unreadable URLs", () => {
    expect(parseMysqlUrl("")).toEqual(MYSQL_CONN_DEFAULTS);
    expect(parseMysqlUrl("not-a-url")).toEqual(MYSQL_CONN_DEFAULTS);
  });
});

describe("parseRedisUrl / composeRedisUrl", () => {
  it("treats empty host as disabled", () => {
    expect(parseRedisUrl("")).toEqual(REDIS_CONN_DEFAULTS);
    expect(composeRedisUrl(REDIS_CONN_DEFAULTS)).toBe("");
    expect(composeRedisUrl({ ...REDIS_CONN_DEFAULTS, password: "x" })).toBe("");
  });

  it("round-trips host / port / db", () => {
    const url = "redis://127.0.0.1:6379/0";
    expect(parseRedisUrl(url)).toEqual({
      host: "127.0.0.1",
      port: 6379,
      user: "",
      password: "",
      db: 0,
      tls: false,
    });
    expect(composeRedisUrl(parseRedisUrl(url))).toBe(url);
  });

  it("parses password-only auth and TLS", () => {
    const url = "rediss://:s3cret@10.0.0.2:6380/2";
    expect(parseRedisUrl(url)).toEqual({
      host: "10.0.0.2",
      port: 6380,
      user: "",
      password: "s3cret",
      db: 2,
      tls: true,
    });
    expect(composeRedisUrl(parseRedisUrl(url))).toBe(url);
  });

  it("keeps ACL username across compose", () => {
    const url = "redis://acl:pw@127.0.0.1:6379/1";
    expect(parseRedisUrl(url).user).toBe("acl");
    expect(composeRedisUrl(parseRedisUrl(url))).toBe(url);
  });
});
