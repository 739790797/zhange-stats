"""Aggregate the site's records for one day, with match and role deduplication."""

from collections import Counter, defaultdict
from collections.abc import Iterable

from app.schemas.stronghold import (
    StrongholdCoverageOut,
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
    bond_display,
    selected_member: int | None,
    names: dict[RoleKey, str | None],
):
    members: dict[int, StrongholdMemberOut] = {}
    role_names = defaultdict(set)
    winning_names = defaultdict(set)
    selected_names = set()
    owners = defaultdict(set)
    roles_with_bonds = set()
    wins = defaultdict(dict)
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
        name = names.get((row.member_id, row.channel_id, row.uid))
        if name:
            role_names[identity].add(name)
            if row.member_id == selected_member:
                selected_names.add(name)
        if row.bonds_known:
            roles_with_bonds.add(identity)
        if row.complete_state is True:
            if name:
                winning_names[row.member_id].add(name)
            previous = wins[row.member_id].get(row.match_id)
            if previous is None or (row.pass_round is not None and row.pass_round > previous):
                wins[row.member_id][row.match_id] = row.pass_round

    rank_data = [
        (member_id, len(rounds), sum(rounds.values()) if None not in rounds.values() else None)
        for member_id, rounds in wins.items()
    ]
    rank_data.sort(key=lambda row: (-row[1], row[2] is None, -(row[2] or 0), row[0]))
    ranking = [
        StrongholdRankOut(
            rank=index,
            member=members[member_id].model_copy(update={"role_names": sorted(winning_names[member_id])}),
            wins=count,
            rounds=rounds,
        )
        for index, (member_id, count, rounds) in enumerate(rank_data[:3], 1)
    ]

    names = {}
    icons = {}
    uses = defaultdict(set)
    role_layers = defaultdict(set)
    team_layers = defaultdict(set)
    unknown_layers = set()
    for row in bonds:
        bond = (row.season_id, row.version_id, row.bond_id)
        if row.name:
            names[bond] = min(names.get(bond, row.name), row.name)
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
        return {"bond_id": bond[-1], "name": names.get(bond), "icon_url": icons.get(bond), **bond_display(bond)}

    def order(bond):
        return bond[0], bond[1] or "", bond[2]

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
    return (
        ranking,
        popular,
        layer_stats,
        StrongholdCoverageOut(
            records=len(owners),
            roles_with_bonds=len(roles_with_bonds),
            roles_with_layers=len(roles_with_layers),
            matches=match_count,
            records_with_unknown_layers=len(unknown_layers),
            roles_with_conflicting_layers=len(conflicting_roles),
        ),
        sorted(selected_names),
    )
