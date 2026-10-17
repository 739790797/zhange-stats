import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchRor2Survivor, type Ror2GalleryImage, type Ror2WikiBlock, type Ror2WikiItem } from "@/api/ror2Api";
import { apiError } from "@/lib/apiError";
import { ror2Number } from "@/lib/ror2Catalog";
import { ror2LoadoutSkillRank, ror2LoadoutSkillZh } from "@/lib/ror2ItemZh";
import {
  ror2DrizzleArmor,
  ror2DlcMark,
  ror2ExpansionIconUrl,
  ror2InfoboxAcceleration,
  ror2PerLevel,
  ror2TierValue,
} from "@/lib/ror2Home";
import { Ror2ExpansionIcon } from "./Ror2ExpansionIcon";
import { useRor2TermText } from "./Ror2TermScope";
import { Ror2RichText } from "./Ror2RichText";
import styles from "./Ror2SurvivorDetailView.module.css";
import theme from "./ror2Theme.module.css";

const TIERS = [
  { label: "In Drizzle", icon: "Drizzle.png", factor: 1.5, color: "#9ce562" },
  { label: "In Rainstorm", icon: "Rainstorm.png", factor: 1, color: "#e5c962" },
  { label: "In Monsoon", icon: "Monsoon.png", factor: 0.6, color: "#e58262" },
] as const;

export function Ror2SurvivorDetailView() {
  const params = useParams();
  const name = params.name ? safeDecode(params.name) : "";
  const detail = useQuery({
    queryKey: ["guides-ror2-survivor", name],
    queryFn: () => fetchRor2Survivor(name),
    enabled: Boolean(name),
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
  const survivor = detail.data;
  const dlc = survivor ? ror2DlcMark(survivor.expansion) : null;
  const skills = survivor?.skills ?? [];
  const behaviors = survivor?.behaviors ?? [];
  const tips = survivor?.tips ?? [];
  const trivia = survivor?.trivia ?? [];
  const history = survivor?.history ?? [];
  const termText = useRor2TermText();
  const skillGroups = [...skills].sort(
    (a, b) => ror2LoadoutSkillRank(a.skill_type) - ror2LoadoutSkillRank(b.skill_type) || a.skill_type.localeCompare(b.skill_type),
  );

  return (
    <div className={styles.page}>
      {detail.isPending ? <p className={styles.status}>正在读取图鉴</p> : null}
      {detail.isError ? (
        <div className={styles.status}>
          <p>{apiError(detail.error, "图鉴暂时拉不下来，请稍后再试")}</p>
          <button type="button" className={theme.wikiBtn} onClick={() => void detail.refetch()}>
            重试
          </button>
        </div>
      ) : null}
      {survivor ? (
        <>
          <section className={styles.section} aria-labelledby="ror2-survivor-card">
            <h2 id="ror2-survivor-card">幸存者</h2>
            <div className={styles.hero}>
              <div className={styles.portrait}>
                <p className={styles.portraitName}>
                  {dlc ? <Ror2ExpansionIcon src={dlc.iconUrl} label={dlc.label} /> : null}
                  {survivor.name_zh || survivor.name}
                </p>
                <Portrait src={survivor.image_url} />
              </div>
              <dl className={styles.stats}>
                <dt>Health</dt>
                <dd>{growth(survivor.health, survivor.health_per_level)}</dd>
                <dt>Health Regen</dt>
                <dd>
                  <div className={styles.tiers}>
                    {TIERS.map((tier) => (
                      <span key={tier.label} className={styles.tier} style={{ color: tier.color }}>
                        <WikiIcon file={tier.icon} label={tier.label} />
                        {growth(ror2TierValue(survivor.regen, tier.factor), ror2TierValue(survivor.regen_per_level, tier.factor), "/s")}
                      </span>
                    ))}
                  </div>
                </dd>
                <dt>Damage</dt>
                <dd>{growth(survivor.damage, survivor.damage_per_level)}</dd>
                <dt>Speed</dt>
                <dd>{survivor.speed == null ? "—" : `${ror2Number(survivor.speed)} m/s`}</dd>
                <dt>Acceleration</dt>
                <dd>{ror2Number(ror2InfoboxAcceleration(survivor.acceleration))}</dd>
                <dt>Mass</dt>
                <dd>{ror2Number(survivor.mass ?? 0)}</dd>
                <dt>Armor</dt>
                <dd>
                  <span className={styles.tier}>
                    {ror2Number(survivor.armor ?? 0)}
                    <span className={styles.tier} style={{ color: "#9ce562" }}>
                      (<WikiIcon file="Drizzle.png" label="In Drizzle" />
                      {ror2Number(ror2DrizzleArmor(survivor.armor))})
                    </span>
                  </span>
                </dd>
                <dt>Umbra Title</dt>
                <dd>{survivor.umbra_zh || survivor.umbra || "—"}</dd>
                <dt>Ending Phrase</dt>
                <dd className={styles.ending}>
                  <span>Escaped : {survivor.phrase_escape_zh || survivor.phrase_escape}</span>
                  <span>Vanished : {survivor.phrase_vanish_zh || survivor.phrase_vanish}</span>
                </dd>
              </dl>
            </div>
            {survivor.summary ? (
              <p className={styles.summary}>
                <Ror2RichText text={survivor.summary_zh || survivor.summary} />
              </p>
            ) : null}
          </section>
          {survivor.lore_zh || survivor.lore ? (
            <section className={styles.section}>
              <h2>日志</h2>
              <div className={styles.lore}>
                <Ror2RichText text={survivor.lore_zh || survivor.lore} />
              </div>
            </section>
          ) : null}
          {skills.length ? (
            <section className={styles.section}>
              <h2>技能</h2>
              {skillGroups.map((group) => (
                <div key={group.skill_type} className={styles.group}>
                  <h3>{ror2LoadoutSkillZh(group.skill_type)}</h3>
                  {(group.skills ?? []).map((skill) => (
                    <article key={`${group.skill_type}-${skill.name}`} className={styles.skill}>
                      <SkillIcon src={skill.image_url} />
                      <div>
                        <h4 className={styles.skillName}>{skill.name_zh || skill.name}</h4>
                        <p className={styles.meta}>
                          {skill.cooldown ? <span>冷却 {skill.cooldown}</span> : null}
                          {skill.proc ? <span>触发系数 {skill.proc}</span> : null}
                          {skill.unlock_zh || skill.unlock ? (
                            <span>解锁 {skill.unlock_zh || termText(skill.unlock)}</span>
                          ) : null}
                        </p>
                        {skill.description_zh || skill.description ? (
                          <p className={styles.skillDesc}>
                            <Ror2RichText text={skill.description_zh || skill.description} />
                          </p>
                        ) : null}
                        {(skill.notes ?? []).length ? (
                          <ul className={styles.notes}>
                            <ItemList items={skill.notes ?? []} />
                          </ul>
                        ) : null}
                      </div>
                    </article>
                  ))}
                </div>
              ))}
            </section>
          ) : null}
          <ProseSection title="特性" blocks={behaviors} />
          <ProseSection title="小技巧" blocks={tips} />
          <ProseSection title="一些琐事" blocks={trivia} />
          {history.length ? (
            <section className={styles.section}>
              <h2>版本历史记录</h2>
              {history.map((group) => (
                <div key={group.version || group.items?.[0]?.text} className={styles.history}>
                  {group.version ? <h3>{termText(group.version)}</h3> : null}
                  <ul className={styles.list}>
                    <ItemList items={group.items ?? []} />
                  </ul>
                </div>
              ))}
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function ProseSection({ title, blocks }: { title: string; blocks: Ror2WikiBlock[] }) {
  if (!blocks.length) return null;
  return (
    <section className={styles.section}>
      <h2>{title}</h2>
      <div className={styles.prose}>
        {blocks.map((block, index) => (
          <Block key={`${block.kind}-${index}`} block={block} />
        ))}
      </div>
    </section>
  );
}

function Block({ block }: { block: Ror2WikiBlock }) {
  if (block.kind === "images") return <Gallery images={block.images ?? []} />;
  if (block.kind === "ol" || block.kind === "ul") {
    const Tag = block.kind === "ol" ? "ol" : "ul";
    return (
      <Tag className={styles.list}>
        <ItemList items={block.items ?? []} />
      </Tag>
    );
  }
  return (
    <p>
      <Ror2RichText text={block.text_zh || block.text} />
    </p>
  );
}

function ItemList({ items }: { items: Ror2WikiItem[] }) {
  return items.map((item, index) => (
    <li key={`${item.text}-${index}`}>
      <Ror2RichText text={item.text_zh || item.text} />
      {(item.children ?? []).length ? (
        <ul className={styles.list}>
          <ItemList items={item.children ?? []} />
        </ul>
      ) : null}
    </li>
  ));
}

function Gallery({ images }: { images: Ror2GalleryImage[] }) {
  return (
    <ul className={styles.gallery}>
      {images.map((image) => (
        <li key={`${image.image_url}-${image.caption}`}>
          <figure className={styles.shot}>
            <Shot src={image.image_url} />
            {image.spin_url ? <Shot src={image.spin_url} className={styles.spin} /> : null}
            {image.caption || image.expansion ? (
              <figcaption>
                {image.expansion ? <ExpansionMark id={image.expansion} /> : null}
                {image.caption_zh || image.caption}
              </figcaption>
            ) : null}
          </figure>
        </li>
      ))}
    </ul>
  );
}

function ExpansionMark({ id }: { id: string }) {
  const src = ror2ExpansionIconUrl(id);
  if (!src) return null;
  return <Ror2ExpansionIcon src={src} />;
}

function growth(base: number | null | undefined, per: number | null | undefined, unit = ""): string {
  if (base == null) return "—";
  const extra = per == null ? "" : ` (${ror2PerLevel(per)} per level)`;
  return `${ror2Number(base)}${unit}${extra}`;
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function Portrait({ src }: { src?: string | null }) {
  const [hidden, setHidden] = useState(false);
  if (!src || hidden) return <span className={styles.portraitFallback} aria-hidden />;
  return (
    <img
      className={styles.portraitImg}
      src={src}
      alt=""
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setHidden(true)}
    />
  );
}

function SkillIcon({ src }: { src?: string | null }) {
  const [hidden, setHidden] = useState(false);
  if (!src || hidden) return <span className={styles.skillFallback} aria-hidden />;
  return (
    <img
      className={styles.skillIcon}
      src={src}
      alt=""
      width={64}
      height={64}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setHidden(true)}
    />
  );
}

function WikiIcon({ file, label }: { file: string; label: string }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  return (
    <img
      className={styles.tierIcon}
      src={`https://riskofrain2.wiki.gg/images/${file}`}
      alt={label}
      title={label}
      width={18}
      height={18}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setHidden(true)}
    />
  );
}

function Shot({ src, className }: { src: string; className?: string }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  return (
    <img
      className={className}
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setHidden(true)}
    />
  );
}
