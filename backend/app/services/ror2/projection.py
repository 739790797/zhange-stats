"""从 Wiki 解析模型投影出令牌边界明确的公开 API 响应。"""

from __future__ import annotations

from app.services.ror2.schemas import (
    Ror2ArtifactResponse,
    Ror2CatalogOut,
    Ror2CatalogResponse,
    Ror2ChallengeResponse,
    Ror2DroneResponse,
    Ror2EnvironmentResponse,
    Ror2GalleryImageResponse,
    Ror2HistoryResponse,
    Ror2InteractableResponse,
    Ror2ItemOut,
    Ror2ItemResponse,
    Ror2MonsterResponse,
    Ror2SkillGroupResponse,
    Ror2SkillResponse,
    Ror2StatResponse,
    Ror2SurvivorDetailOut,
    Ror2SurvivorDetailResponse,
    Ror2SurvivorResponse,
    Ror2TextOut,
    Ror2WikiArticleOut,
    Ror2WikiBlockResponse,
    Ror2WikiColumnOut,
    Ror2WikiItemResponse,
    Ror2WikiSectionOut,
    Ror2WikiTableOut,
)
from app.services.ror2.strings import (
    resolve_catalog_texts,
    resolve_context_text,
    resolve_detail_texts,
    slot_result_key,
)
from app.services.ror2.wiki_structure import ArticleSource, SourceText


def catalog_response(
    catalog: Ror2CatalogOut,
    sources: dict[str, str],
    units: dict[str, dict[str, str]],
    articles: list[ArticleSource],
) -> Ror2CatalogResponse:
    resolved = resolve_catalog_texts(catalog, sources, units)
    return Ror2CatalogResponse(
        source=catalog.source,
        fetched_at=catalog.fetched_at,
        items=[_item(row, "item", resolved) for row in catalog.items],
        equipment=[_item(row, "equipment", resolved) for row in catalog.equipment],
        survivors=[
            Ror2SurvivorResponse(
                name=_text(resolved, f"survivor.{row.name}.name", row.name),
                umbra=_text(resolved, f"survivor.{row.name}.umbra", row.umbra),
                description=_text(resolved, f"survivor.{row.name}.desc", row.description),
                unlock=_text(resolved, f"survivor.{row.name}.unlock", row.unlock),
                expansion=row.expansion,
                phrase_escape=_text(resolved, f"survivor.{row.name}.phrase_escape", row.phrase_escape),
                phrase_vanish=_text(resolved, f"survivor.{row.name}.phrase_vanish", row.phrase_vanish),
                health=row.health,
                health_per_level=row.health_per_level,
                damage=row.damage,
                damage_per_level=row.damage_per_level,
                regen=row.regen,
                regen_per_level=row.regen_per_level,
                speed=row.speed,
                acceleration=row.acceleration,
                mass=row.mass,
                armor=row.armor,
                wiki_url=row.wiki_url,
                image_url=row.image_url,
            )
            for row in catalog.survivors
        ],
        monsters=[
            Ror2MonsterResponse(
                name=_text(
                    resolved,
                    slot_result_key(_record_id("monster", row.name, row.internal_name) + ".name", row.name, row.internal_name),
                    row.name,
                ),
                kind=row.kind,
                role=row.role,
                expansion=row.expansion,
                boss_name=_text(
                    resolved,
                    slot_result_key(_record_id("monster", row.name, row.internal_name) + ".boss", row.name, row.internal_name),
                    row.boss_name,
                ),
                internal_name=row.internal_name,
                categories=row.categories,
                is_ally=row.is_ally,
                do_not_count=row.do_not_count,
                is_subtype=row.is_subtype,
                health=row.health,
                health_per_level=row.health_per_level,
                damage=row.damage,
                damage_per_level=row.damage_per_level,
                regen=row.regen,
                regen_per_level=row.regen_per_level,
                speed=row.speed,
                armor=row.armor,
                wiki_url=row.wiki_url,
                image_url=row.image_url,
            )
            for row in catalog.monsters
        ],
        drones=[
            Ror2DroneResponse(
                name=_text(
                    resolved,
                    slot_result_key(_record_id("drone", row.name, row.internal_name) + ".name", row.name, row.internal_name),
                    row.name,
                ),
                kind=row.kind,
                quote=_text(
                    resolved,
                    slot_result_key(_record_id("drone", row.name, row.internal_name) + ".quote", row.name, row.internal_name),
                    row.quote,
                ),
                description=_text(
                    resolved,
                    slot_result_key(_record_id("drone", row.name, row.internal_name) + ".desc", row.name, row.internal_name),
                    row.description,
                ),
                internal_name=row.internal_name,
                rarity=row.rarity,
                type2=row.type2,
                cost=row.cost,
                health=row.health,
                health_per_level=row.health_per_level,
                damage=row.damage,
                damage_per_level=row.damage_per_level,
                regen=row.regen,
                regen_per_level=row.regen_per_level,
                speed=row.speed,
                armor=row.armor,
                wiki_url=row.wiki_url,
                image_url=row.image_url,
            )
            for row in catalog.drones
        ],
        environments=[
            Ror2EnvironmentResponse(
                name=_text(resolved, f"environment.wiki.{row.name}.name", row.name),
                stage=row.stage,
                subtitle=_text(resolved, f"environment.wiki.{row.name}.subtitle", row.subtitle),
                description=_text(resolved, f"environment.wiki.{row.name}.desc", row.description),
                soundtrack=row.soundtrack,
                lunar_seer=row.lunar_seer,
                expansion=row.expansion,
                wiki_url=row.wiki_url,
                image_url=row.image_url,
            )
            for row in catalog.environments
        ],
        challenges=[
            Ror2ChallengeResponse(
                name=_text(resolved, f"challenge.wiki.{row.name}.name", row.name),
                kind=row.kind,
                description=_text(resolved, f"challenge.wiki.{row.name}.desc", row.description),
                unlock=[
                    _text(resolved, f"challenge.wiki.{row.name}.unlock.{index}", value)
                    for index, value in enumerate(row.unlock, start=1)
                ],
                coins=row.coins,
                expansion=row.expansion,
                wiki_url=row.wiki_url,
            )
            for row in catalog.challenges
        ],
        interactables=[
            Ror2InteractableResponse(
                name=_text(resolved, f"interactable.wiki.{row.name}.name", row.name),
                category=row.category,
                effect=_text(resolved, f"interactable.wiki.{row.name}.effect", row.effect),
                expansion=row.expansion,
                cost=row.cost,
                link=row.link,
                location=row.location,
                wiki_url=row.wiki_url,
                image_url=row.image_url,
            )
            for row in catalog.interactables
        ],
        artifacts=[
            Ror2ArtifactResponse(
                name=_text(resolved, f"artifact.wiki.{row.name}.name", row.name),
                description=_text(resolved, f"artifact.wiki.{row.name}.desc", row.description),
                code=row.code,
                expansion=row.expansion,
                unlock=_text(resolved, f"artifact.wiki.{row.name}.unlock", row.unlock),
                wiki_url=row.wiki_url,
                image_url=row.image_url,
            )
            for row in catalog.artifacts
        ],
        wiki_articles=[_article(article, sources, units) for article in articles],
    )


def detail_response(
    detail: Ror2SurvivorDetailOut,
    sources: dict[str, str],
    units: dict[str, dict[str, str]],
) -> Ror2SurvivorDetailResponse:
    resolved = resolve_detail_texts(detail, sources, units)
    root = f"survivor.{detail.name}"
    stems: dict[str, int] = {}
    skill_groups: list[Ror2SkillGroupResponse] = []
    for group_index, group in enumerate(detail.skills, start=1):
        skills: list[Ror2SkillResponse] = []
        for skill in group.skills:
            stem = _skill_stem(stems, detail.name, skill.name)
            skills.append(
                Ror2SkillResponse(
                    name=_text(resolved, f"{stem}.name", skill.name),
                    skill_type=_text(
                        resolved,
                        f"{root}.skill_group.{group_index}.skill_type.{skill.name}",
                        skill.skill_type,
                    ),
                    cooldown=skill.cooldown,
                    proc=skill.proc,
                    description=_text(resolved, f"{stem}.desc", skill.description),
                    notes=[
                        _wiki_item(item, f"{stem}.note", index, resolved)
                        for index, item in enumerate(skill.notes, start=1)
                    ],
                    unlock=_text(resolved, f"{stem}.unlock", skill.unlock),
                    image_url=skill.image_url,
                )
            )
        skill_groups.append(
            Ror2SkillGroupResponse(
                skill_type=_text(resolved, f"{root}.skill_group.{group_index}.title", group.skill_type),
                skills=skills,
            )
        )
    history_counts: dict[str, int] = {}
    history: list[Ror2HistoryResponse] = []
    for index, group in enumerate(detail.history, start=1):
        label = group.version or str(index)
        count = history_counts.get(label, 0) + 1
        history_counts[label] = count
        stem = f"{root}.history.{label}" if count == 1 else f"{root}.history.{label}#{count}"
        history.append(
            Ror2HistoryResponse(
                version=_text(resolved, f"{stem}.version", group.version),
                items=[
                    _wiki_item(item, stem, item_index, resolved)
                    for item_index, item in enumerate(group.items, start=1)
                ],
            )
        )
    return Ror2SurvivorDetailResponse(
        name=_text(resolved, f"{root}.name", detail.name),
        summary=_text(resolved, f"{root}.summary", detail.summary),
        umbra=_text(resolved, f"{root}.umbra", detail.umbra),
        phrase_escape=_text(resolved, f"{root}.phrase_escape", detail.phrase_escape),
        phrase_vanish=_text(resolved, f"{root}.phrase_vanish", detail.phrase_vanish),
        expansion=detail.expansion,
        health=detail.health,
        health_per_level=detail.health_per_level,
        regen=detail.regen,
        regen_per_level=detail.regen_per_level,
        damage=detail.damage,
        damage_per_level=detail.damage_per_level,
        speed=detail.speed,
        acceleration=detail.acceleration,
        mass=detail.mass,
        armor=detail.armor,
        image_url=detail.image_url,
        wiki_url=detail.wiki_url,
        lore=_text(resolved, f"{root}.lore", detail.lore),
        skills=skill_groups,
        behaviors=_blocks(detail.behaviors, f"{root}.behavior", resolved),
        tips=_blocks(detail.tips, f"{root}.tip", resolved),
        trivia=_blocks(detail.trivia, f"{root}.trivia", resolved),
        gallery=[
            Ror2GalleryImageResponse(
                image_url=image.image_url,
                spin_url=image.spin_url,
                caption=_text(resolved, f"{root}.gallery.{index}.caption", image.caption),
                expansion=image.expansion,
            )
            for index, image in enumerate(detail.gallery, start=1)
        ],
        history=history,
    )


def _item(row: Ror2ItemOut, kind: str, resolved: dict[str, Ror2TextOut]) -> Ror2ItemResponse:
    name = row.name
    token = row.internal_name
    base = _record_id(kind, name, token)
    return Ror2ItemResponse(
        name=_text(resolved, slot_result_key(f"{base}.name", name, token), name),
        rarity=_text(resolved, slot_result_key(f"{base}.rarity", name, token), row.rarity),
        quote=_text(resolved, slot_result_key(f"{base}.quote", name, token), row.quote),
        description=_text(resolved, slot_result_key(f"{base}.desc", name, token), row.description),
        lore=_text(resolved, f"{base}.lore", row.lore),
        categories=row.categories,
        unlock=_text(resolved, slot_result_key(f"{base}.unlock", name, token), row.unlock),
        expansion=row.expansion,
        internal_name=row.internal_name,
        code=row.code,
        corrupt=row.corrupt,
        uncorrupt=row.uncorrupt,
        boss=row.boss,
        cooldown=row.cooldown,
        wiki_url=row.wiki_url,
        image_url=row.image_url,
        stats=[
            Ror2StatResponse(
                label=stat.label,
                value=stat.value,
                stack=_text(
                    resolved,
                    slot_result_key(_stat_slot_id(base, stat.source_key, index), name, token),
                    stat.stack,
                ),
                add=stat.add,
            )
            for index, stat in enumerate(row.stats, start=1)
        ],
    )


def _article(article: ArticleSource, sources: dict[str, str], units: dict[str, dict[str, str]]) -> Ror2WikiArticleOut:
    return Ror2WikiArticleOut(
        id=article.id,
        title=_source_text(article.title, sources, units),
        sections=[
            Ror2WikiSectionOut(
                id=section.id,
                level=section.level,
                title=_source_text(section.title, sources, units),
                tables=[
                    Ror2WikiTableOut(
                        id=table.id,
                        caption=(
                            _source_text(table.caption, sources, units)
                            if table.caption is not None
                            else None
                        ),
                        columns=[
                            Ror2WikiColumnOut(
                                id=column.id,
                                label=_source_text(column.label, sources, units),
                            )
                            for column in table.columns
                        ],
                    )
                    for table in section.tables
                ],
            )
            for section in article.sections
        ],
    )


def _source_text(source: SourceText, sources: dict[str, str], units: dict[str, dict[str, str]]) -> Ror2TextOut:
    return resolve_context_text(source.text, source.context, sources, units, source_format="plain")


def _blocks(
    blocks: list[object], prefix: str, resolved: dict[str, Ror2TextOut]
) -> list[Ror2WikiBlockResponse]:
    projected: list[Ror2WikiBlockResponse] = []
    for index, block in enumerate(blocks, start=1):
        stem = f"{prefix}.{index}"
        projected.append(
            Ror2WikiBlockResponse(
                kind=block.kind,
                text=_text(resolved, stem, block.text),
                items=[
                    _wiki_item(item, stem, item_index, resolved)
                    for item_index, item in enumerate(block.items, start=1)
                ],
                images=[
                    Ror2GalleryImageResponse(
                        image_url=image.image_url,
                        spin_url=image.spin_url,
                        caption=_text(resolved, f"{stem}.image.{image_index}.caption", image.caption),
                        expansion=image.expansion,
                    )
                    for image_index, image in enumerate(block.images, start=1)
                ],
            )
        )
    return projected


def _wiki_item(
    item: object,
    prefix: str,
    index: int,
    resolved: dict[str, Ror2TextOut],
) -> Ror2WikiItemResponse:
    stem = f"{prefix}.{index}"
    return Ror2WikiItemResponse(
        text=_text(resolved, stem, item.text),
        children=[
            _wiki_item(child, stem, child_index, resolved)
            for child_index, child in enumerate(item.children, start=1)
        ],
    )


def _stat_slot_id(base: str, source_key: str | None, index: int) -> str:
    key = source_key if source_key is not None else "unmapped-" + str(index)
    return f"{base}.stats.{key}.stack"


def _text(resolved: dict[str, Ror2TextOut], key: str, original: str) -> Ror2TextOut:
    return resolved.get(key) or Ror2TextOut(text=original, original=original, token=None)


def _record_id(kind: str, name: str, token: str) -> str:
    return f"{kind}.{token.strip()}" if token.strip() else f"{kind}.wiki.{name}"


def _skill_stem(counts: dict[str, int], survivor: str, skill: str) -> str:
    base = f"skill.{survivor}.{skill}"
    count = counts.get(base, 0) + 1
    counts[base] = count
    return base if count == 1 else f"{base}#{count}"