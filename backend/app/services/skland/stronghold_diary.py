"""Aggregate the site's records for one day, with match and role deduplication."""

from collections import Counter, defaultdict
from collections.abc import Iterable

from app.schemas.stronghold import (
    StrongholdCoverageOut,
    StrongholdDiaryBondOut,
    StrongholdDiaryStrategyOut,
    StrongholdLayerMemberOut,
    StrongholdLayerOut,
    StrongholdMemberOut,
    StrongholdPopularBondOut,
    StrongholdRankOut,
)
from app.services.skland.arknights_identity import RoleKey


def aggregate_diary(
    views: Iterable,
    bonds: Iterable,
    match_count: int,
    display_entry,
    catalog_bonds: set[tuple[str, str, str]],
    selected_member: int | None,
    names: dict[RoleKey, str | None],
):
    members: dict[int, StrongholdMemberOut] = {}
    role_names = defaultdict(set)
    member_names = defaultdict(set)
    member_matches = defaultdict(set)
    selected_names = set()
    owners = defaultdict(set)
    roles_with_bonds = set()
    wins = defaultdict(dict)
    strategy_views = defaultdict(set)
    strategy_fallbacks = defaultdict(dict)
    for row in views:
        identity = (row.match_id, row.channel_id, row.uid)
        members.setdefault(
            row.member_id,
            StrongholdMemberOut(
                id=row.member_id,
                nickname=row.nickname,
                avatar_url=row.avatar_url,
            ),
        )
        owners[identity].add(row.member_id)
        member_matches[row.member_id].add(row.match_id)
        name = names.get((row.member_id, row.channel_id, row.uid))
        if name:
            role_names[identity].add(name)
            member_names[row.member_id].add(name)
            if row.member_id == selected_member:
                selected_names.add(name)
        if row.bonds_known:
            roles_with_bonds.add(identity)
        if row.strategy_id:
            strategy = (row.season_id, row.version_id, row.strategy_id)
            strategy_views[identity].add(strategy)
            fallback = strategy_fallbacks[strategy]
            for field in ("name", "icon_url", "description"):
                if value := getattr(row, f"strategy_{field}"):
                    fallback[field] = min(fallback.get(field, value), value)
        if row.complete_state is True:
            previous = wins[row.member_id].get(row.match_id)
            if previous is None or (row.pass_round is not None and row.pass_round > previous):
                wins[row.member_id][row.match_id] = row.pass_round

    ranked_members = sorted(member_matches, key=lambda member_id: (-len(member_matches[member_id]), member_id))
    ranking = []
    for index, member_id in enumerate(ranked_members[:3], 1):
        rounds = wins.get(member_id, {})
        ranking.append(
            StrongholdRankOut(
                rank=index,
                member=members[member_id].model_copy(update={"role_names": sorted(member_names[member_id])}),
                matches=len(member_matches[member_id]),
                wins=len(rounds),
                rounds=sum(rounds.values()) if rounds and None not in rounds.values() else None,
            )
        )

    def order(entry):
        return entry[0], entry[1] or "", entry[2]

    # As with layers, duplicate snapshots of one role in the same match do not add counts.
    strategy_counts = Counter(next(iter(ids)) for ids in strategy_views.values() if len(ids) == 1)
    strategies = [
        StrongholdDiaryStrategyOut(
            strategy_id=strategy[-1],
            count=strategy_counts[strategy],
            **{**strategy_fallbacks[strategy], **display_entry(strategy, "strategy")},
        )
        for strategy in sorted(strategy_counts, key=lambda item: (-strategy_counts[item], order(item)))
    ]

    bond_names = {}
    icons = {}
    uses = defaultdict(set)
    role_layers = defaultdict(set)
    team_layers = defaultdict(set)
    unknown_layers = set()
    for row in bonds:
        bond = (row.season_id, row.version_id, row.bond_id)
        if row.name:
            bond_names[bond] = min(bond_names.get(bond, row.name), row.name)
        if row.icon_url:
            icons[bond] = min(icons.get(bond, row.icon_url), row.icon_url)
        if row.active is not True:
            continue
        uses[bond].add(row.match_id)
        if row.layer is None:
            continue
        role = (row.match_id, row.channel_id, row.uid)
        if row.layer_scope == "team":
            team_layers[(row.match_id, bond)].add(row.layer)
        else:
            # Count the recorded view without inferring who produced the layers.
            role_layers[(*role, bond)].add(row.layer)
            if row.layer_scope != "role":
                unknown_layers.add(role)

    def display(bond):
        return {
            "bond_id": bond[-1],
            "name": bond_names.get(bond),
            "icon_url": icons.get(bond),
            **display_entry(bond, "bond"),
        }

    most_used = max(map(len, uses.values()), default=0)
    popular = [
        StrongholdPopularBondOut(**display(bond), matches=len(uses[bond]))
        for bond in sorted(uses, key=order)
        if len(uses[bond]) == most_used
    ]
    layers = Counter()
    unattributed = Counter()
    contributors = defaultdict(Counter)
    contributor_names = defaultdict(set)
    roles_with_layers = set()
    conflicting_roles = set()
    for role_bond, values in role_layers.items():
        role, bond_id = role_bond[:3], role_bond[-1]
        if len(values) != 1:
            conflicting_roles.add(role)
            continue
        value = next(iter(values))
        roles_with_layers.add(role)
        layers[bond_id] += value
        if len(owners[role]) == 1:
            member_id = next(iter(owners[role]))
            contributors[bond_id][member_id] += value
            contributor_names[bond_id, member_id].update(role_names[role])
        else:
            unattributed[bond_id] += value
    team_totals = Counter()
    for (_, bond_id), values in team_layers.items():
        if len(values) == 1:
            team_totals[bond_id] += next(iter(values))
    layer_stats = [
        StrongholdLayerOut(
            **display(bond_id),
            layers=layers[bond_id],
            unattributed_layers=unattributed[bond_id],
            team_layers=team_totals.get(bond_id),
            contributors=[
                StrongholdLayerMemberOut(
                    member=members[member_id].model_copy(
                        update={"role_names": sorted(contributor_names[bond_id, member_id])}
                    ),
                    layers=member_layers,
                )
                for member_id, member_layers in sorted(
                    contributors[bond_id].items(), key=lambda item: (-item[1], item[0])
                )
            ],
        )
        for bond_id in sorted(layers.keys() | team_totals.keys(), key=lambda bond: (-layers[bond], order(bond)))
    ]
    covenants = [
        StrongholdDiaryBondOut(
            **display(bond),
            matches=len(uses.get(bond, ())),
            layers=layers.get(bond) if bond in uses else 0,
        )
        for bond in sorted(catalog_bonds | uses.keys(), key=lambda bond: (-layers[bond], order(bond)))
    ]
    return {
        "ranking": ranking,
        "popular_bonds": popular,
        "layers": layer_stats,
        "strategies": strategies,
        "covenants": covenants,
        "coverage": StrongholdCoverageOut(
            records=len(owners),
            roles_with_bonds=len(roles_with_bonds),
            roles_with_layers=len(roles_with_layers),
            matches=match_count,
            records_with_unknown_layers=len(unknown_layers),
            roles_with_conflicting_layers=len(conflicting_roles),
        ),
        "filtered_role_names": sorted(selected_names),
    }
