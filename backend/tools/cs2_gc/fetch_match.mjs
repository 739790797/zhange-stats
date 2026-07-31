#!/usr/bin/env node
/**
 * 调用 boiler-writter 拉取 CMsgGCCStrike15_v2_MatchList，解析为 JSON 供 Python 落库。
 * 用法: node fetch_match.mjs <matchId> <outcomeId> <token> [boilerPath]
 * 依赖本机 Steam 已登录。
 */
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { CMsgGCCStrike15_v2_MatchListSchema, fromBinary } from "csgo-protobuf";

const execFileAsync = promisify(execFile);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const EXIT = {
  Success: 0,
  SteamNotRunningOrLoggedIn: 6,
  UserNotLoggedIn: 7,
  NoMatchesFound: 8,
};

/** @see akiver/cs-demo-manager get-map-name */
function getMapName(gameType) {
  const map = (gameType >> 8) & 0xffffff;
  const gameMode = gameType & 0xff;
  const competitiveMode = 8;
  const wingmanMode = 10;
  const mapping = {
    [1 << 0]: "de_grail",
    [1 << 1]: "de_dust2",
    [1 << 2]: "de_train",
    [1 << 3]: "de_ancient",
    [1 << 4]: "de_inferno",
    [1 << 5]: "de_nuke",
    [1 << 6]: "de_vertigo",
    [1 << 7]: {
      [competitiveMode]: "de_mirage",
      [wingmanMode]: "de_palais",
    },
    [1 << 8]: "cs_office",
    [1 << 9]: "de_brewery",
    [1 << 10]: "de_whistle",
    [1 << 11]: "de_dogtown",
    [1 << 12]: "de_cache",
    [1 << 13]: "de_jura",
    [1 << 14]: "de_edin",
    [1 << 15]: "de_anubis",
    [1 << 16]: "de_tuscan",
    [1 << 18]: "de_basalt",
    [1 << 19]: "cs_agency",
    [1 << 20]: "de_overpass",
    [1 << 21]: "de_cobblestone",
    [1 << 22]: "de_canals",
  };
  const hit = mapping[map];
  if (typeof hit === "string") return hit;
  return hit?.[gameMode] ?? "unknown";
}

function steamId3To64(steamId3) {
  return (BigInt("76561197960265728") + BigInt(steamId3)).toString();
}

function lastRound(matchInfo) {
  if (matchInfo.roundstatsLegacy) return matchInfo.roundstatsLegacy;
  const all = matchInfo.roundstatsall || [];
  return all[all.length - 1];
}

function parseMatch(matchInfo) {
  const last = lastRound(matchInfo);
  if (!last) {
    throw new Error("MatchInfo 无 roundstats");
  }
  const reservation = last.reservation || {};
  const accountIds = reservation.accountIds || [];
  const kills = last.kills || [];
  const deaths = last.deaths || [];
  const assists = last.assists || [];
  const scores = last.scores || [];
  const mvps = last.mvps || [];
  let [scoreCt, scoreT] = last.teamScores || [0, 0];
  if (last.bSwitchedTeams) {
    [scoreCt, scoreT] = [scoreT, scoreCt];
  }

  const players = [];
  for (let i = 0; i < accountIds.length; i++) {
    const aid = Number(accountIds[i] || 0);
    if (!aid) continue;
    // 0-4 开局 CT，5-9 开局 T；若最后一回合已换边则对调最终阵营
    let team = i < 5 ? 3 : 2; // 3=CT 2=T（与 CS 惯例一致）
    if (last.bSwitchedTeams) {
      team = team === 3 ? 2 : 3;
    }
    const won =
      last.matchResult === 0
        ? null
        : last.matchResult === 1
          ? team === (last.bSwitchedTeams ? 2 : 3)
          : team === (last.bSwitchedTeams ? 3 : 2);

    players.push({
      steam_id: steamId3To64(aid),
      team,
      kills: Number(kills[i] ?? 0),
      deaths: Number(deaths[i] ?? 0),
      assists: Number(assists[i] ?? 0),
      mvps: Number(mvps[i] ?? 0),
      score: Number(scores[i] ?? 0),
      damage: null,
      won,
      persona_name: null,
    });
  }

  const gameType = Number(reservation.gameType || 0);
  const matchtime = Number(matchInfo.matchtime || 0);
  return {
    match_id: String(matchInfo.matchid ?? ""),
    map_name: getMapName(gameType),
    played_at: matchtime
      ? new Date(matchtime * 1000).toISOString()
      : null,
    score_team0: Number(scoreCt ?? 0),
    score_team1: Number(scoreT ?? 0),
    demo_url: last.map || null,
    players,
  };
}

async function main() {
  const [matchId, outcomeId, token, boilerArg] = process.argv.slice(2);
  if (!matchId || !outcomeId || token === undefined) {
    console.error(
      "Usage: node fetch_match.mjs <matchId> <outcomeId> <token> [boilerPath]",
    );
    process.exit(2);
  }

  const boilerPath =
    boilerArg ||
    path.join(__dirname, "boiler", "bin", "boiler-writter.exe");

  const dir = await mkdtemp(path.join(tmpdir(), "zhange-cs2-"));
  const outFile = path.join(dir, "match.info");
  try {
    let code = 0;
    try {
      await execFileAsync(
        boilerPath,
        [outFile, String(matchId), String(outcomeId), String(token)],
        { windowsHide: true, maxBuffer: 10 * 1024 * 1024 },
      );
    } catch (err) {
      code = typeof err.code === "number" ? err.code : 1;
      const stderr = (err.stderr || err.message || "").toString();
      if (code === EXIT.SteamNotRunningOrLoggedIn || code === EXIT.UserNotLoggedIn) {
        throw new Error(
          "Steam 未运行或未登录。请先打开 Steam 并登录后再补齐对局详情。",
        );
      }
      if (code === EXIT.NoMatchesFound) {
        throw new Error("GC 未返回该对局（可能已过期）");
      }
      if (code !== EXIT.Success) {
        throw new Error(`boiler 退出码 ${code}: ${stderr.slice(0, 400)}`);
      }
    }

    const buf = await readFile(outFile);
    const matchList = fromBinary(CMsgGCCStrike15_v2_MatchListSchema, new Uint8Array(buf));
    const matches = matchList.matches || [];
    if (!matches.length) {
      throw new Error("MatchList 为空");
    }
    const parsed = parseMatch(matches[0]);
    if (!parsed.match_id) {
      parsed.match_id = String(matchId);
    }
    process.stdout.write(JSON.stringify(parsed));
  } finally {
    await rm(dir, { recursive: true, force: true }).catch(() => {});
  }
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
