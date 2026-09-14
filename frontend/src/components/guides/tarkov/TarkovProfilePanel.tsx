import { Alert, InputNumber, Spin, message } from "antd";
import { useEffect, useMemo, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovProfile,
  fetchTarkovTraders,
  updateTarkovProfile,
  type TarkovProfileIn,
} from "@/api/guidesApi";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useAuthStore } from "@/stores/authStore";
import { traderDisplayName } from "@/lib/tarkovHomeNav";
import {
  persistTarkovPmcFaction,
  TARKOV_PMC_FACTIONS,
  loadTarkovPmcFaction,
  tarkovPmcFactionLabel,
  parseTarkovPmcFaction,
} from "@/lib/tarkovPmcFaction";
import {
  TARKOV_GAME_EDITIONS,
  TARKOV_PLAYER_LEVEL_MAX,
  TARKOV_PLAYER_LEVEL_MIN,
  TARKOV_PROFILE_TRADER_SLUGS,
  TARKOV_TRADER_LOYALTY_MAX,
  TARKOV_TRADER_LOYALTY_MIN,
  indexTraderLoyaltyBySlug,
  parseTarkovGameEdition,
  parseTarkovPlayerLevel,
  parseTarkovTraderLoyalty,
  tarkovGameEditionLabel,
  traderLoyaltyReqParts,
  traderLoyaltyReqTitle,
  traderLoyaltySpec,
} from "@/lib/tarkovProfile";
import trade from "./TarkovGuideTrade.module.css";
import styles from "./TarkovProfilePanel.module.css";

const EMPTY_TRADERS: Record<string, number> = {};

const LOYALTY_LEVELS = Array.from(
  { length: TARKOV_TRADER_LOYALTY_MAX - TARKOV_TRADER_LOYALTY_MIN + 1 },
  (_, index) => TARKOV_TRADER_LOYALTY_MIN + index,
);

function reqStatusClass(met: boolean | null | undefined): string {
  if (met == null) return styles.reqUnset;
  return met ? styles.reqMet : styles.reqUnmet;
}

export function TarkovProfilePanel() {
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const loggedIn = Boolean(useAuthStore((s) => s.user));
  const migratedRef = useRef(false);

  const query = useQuery({
    queryKey: ["guides-tarkov-profile", gameMode],
    queryFn: fetchTarkovProfile,
    staleTime: 30_000,
    retry: 1,
    enabled: loggedIn,
  });
  const tradersQuery = useQuery({
    queryKey: ["guides-tarkov-traders", gameMode],
    queryFn: fetchTarkovTraders,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const loyaltyBySlug = useMemo(
    () => indexTraderLoyaltyBySlug(tradersQuery.data?.items),
    [tradersQuery.data],
  );

  const mutation = useMutation({
    mutationFn: (patch: TarkovProfileIn) => updateTarkovProfile(patch),
    onSuccess: (data) => {
      queryClient.setQueryData(["guides-tarkov-profile", gameMode], data);
      const nextFaction = parseTarkovPmcFaction(data.pmc_faction);
      if (nextFaction) persistTarkovPmcFaction(gameMode, nextFaction);
      void queryClient.invalidateQueries({
        queryKey: ["guides-tarkov-hideout-levels", gameMode],
      });
    },
    onError: (error) => {
      message.error(apiError(error, "个人资料保存失败"));
    },
  });
  const mutateProfile = mutation.mutate;

  const data = query.data;
  const faction = parseTarkovPmcFaction(data?.pmc_faction);
  const edition = parseTarkovGameEdition(data?.game_edition);
  const playerLevel = parseTarkovPlayerLevel(data?.player_level);
  const traders = data?.trader_levels || EMPTY_TRADERS;

  useEffect(() => {
    if (!data || migratedRef.current) return;
    if (data.pmc_faction) {
      persistTarkovPmcFaction(gameMode, parseTarkovPmcFaction(data.pmc_faction));
      return;
    }
    const local = loadTarkovPmcFaction(gameMode);
    if (!local) return;
    migratedRef.current = true;
    mutateProfile({ pmc_faction: local });
  }, [data, gameMode, mutateProfile]);

  const save = (patch: TarkovProfileIn) => {
    if (mutation.isPending) return;
    mutation.mutate(patch);
  };

  if (query.isLoading) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (query.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="个人资料加载失败"
        description={apiError(query.error, "个人资料加载失败")}
      />
    );
  }

  return (
    <div className={styles.stack}>
      <section className={styles.section}>
        <h3 className={styles.label}>阵营</h3>
        <div
          className={`${trade.chipBar} ${styles.chips}`}
          role="radiogroup"
          aria-label="PMC 阵营"
        >
          {TARKOV_PMC_FACTIONS.map((id) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={faction === id}
              className={`${trade.chipBtn} ${trade.chipAll}${
                faction === id ? ` ${trade.chipOn}` : ""
              }`}
              disabled={mutation.isPending}
              onClick={() => save({ pmc_faction: id })}
            >
              {tarkovPmcFactionLabel(id)}
            </button>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h3 className={styles.label}>游戏版本</h3>
        <div
          className={`${trade.chipBar} ${styles.chips}`}
          role="radiogroup"
          aria-label="游戏版本"
        >
          {TARKOV_GAME_EDITIONS.map((id) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={edition === id}
              className={`${trade.chipBtn} ${trade.chipAll}${
                edition === id ? ` ${trade.chipOn}` : ""
              }`}
              disabled={mutation.isPending}
              onClick={() => save({ game_edition: id })}
            >
              {tarkovGameEditionLabel(id)}
            </button>
          ))}
        </div>
        <p className={styles.hint}>
          蓝边（Edge of Darkness）开局即 4 级仓库，藏身处规划器会按此处理。
        </p>
      </section>

      <section className={styles.section}>
        <h3 className={styles.label}>角色等级</h3>
        <div className={styles.levelRow}>
          <InputNumber
            className={styles.levelInput}
            min={TARKOV_PLAYER_LEVEL_MIN}
            max={TARKOV_PLAYER_LEVEL_MAX}
            value={playerLevel}
            disabled={mutation.isPending}
            onChange={(value) => {
              if (value == null) return;
              const next = parseTarkovPlayerLevel(value);
              if (next === playerLevel) return;
              save({ player_level: next });
            }}
          />
          <span className={styles.hint}>
            {TARKOV_PLAYER_LEVEL_MIN}–{TARKOV_PLAYER_LEVEL_MAX}
          </span>
        </div>
      </section>

      <section className={styles.section}>
        <h3 className={styles.label}>商人好感</h3>
        <p className={styles.hint}>
          点选当前好感等级。每个格子是升到该级所需的角色等级和好感度；等级够不够用颜色标出。
        </p>
        <div className={styles.traders}>
          {TARKOV_PROFILE_TRADER_SLUGS.map((slug) => {
            const current = traders[slug]
              ? parseTarkovTraderLoyalty(traders[slug])
              : 0;
            const levels = loyaltyBySlug.get(slug);
            const name = traderDisplayName(slug);
            return (
              <div key={slug} className={styles.trader}>
                <div className={styles.portrait}>
                  <TarkovTraderThumb slug={slug} size={64} variant="portrait" />
                </div>
                <div className={styles.traderName}>{name}</div>
                <div
                  className={styles.loyalty}
                  role="radiogroup"
                  aria-label={`${name} 好感`}
                >
                  {LOYALTY_LEVELS.map((level) => {
                    const spec = traderLoyaltySpec(levels, level);
                    const parts = traderLoyaltyReqParts(spec, playerLevel, {
                      includeBaseline: true,
                    });
                    return (
                      <button
                        key={level}
                        type="button"
                        role="radio"
                        aria-checked={current === level}
                        title={traderLoyaltyReqTitle(spec) || undefined}
                        className={`${styles.loyaltyBtn}${
                          current === level ? ` ${styles.loyaltyOn}` : ""
                        }`}
                        disabled={mutation.isPending}
                        onClick={() =>
                          save({ trader_levels: { [slug]: level } })
                        }
                      >
                        <span className={styles.loyaltyLabel}>LL{level}</span>
                        {parts.length ? (
                          <span className={styles.loyaltyReqs}>
                            {parts.map((part) => (
                              <span
                                key={part.key}
                                className={reqStatusClass(part.met)}
                              >
                                {part.text}
                              </span>
                            ))}
                          </span>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
