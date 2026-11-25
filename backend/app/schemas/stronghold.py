from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

StrongholdUid = Annotated[str, Field(pattern=r"^[0-9]{1,32}$")]
StrongholdScopeId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")]
StrongholdVersionKey = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}:[A-Za-z0-9_:.\-]{1,128}$")]
StrongholdChannel = Literal["1", "2"]
StrongholdMode = Literal["single", "multi", "local"]
StrongholdResult = Literal["complete", "interrupted", "unknown"]


class StrongholdSyncIn(BaseModel):
    uid: StrongholdUid
    channel_id: StrongholdChannel


class StrongholdSyncOut(BaseModel):
    role_id: int
    new_matches: int
    new_records: int
    records_seen: int
    skipped: int = 0
    resources_available: bool
    synced_at: datetime


class StrongholdSyncStatus(BaseModel):
    channel_id: StrongholdChannel | None = None
    uid: str | None = None
    role_name: str | None = None
    state: Literal["queued", "syncing", "idle", "retrying", "reauth", "discovering"]
    last_success_at: datetime | None = None
    next_sync_at: datetime | None = None


class StrongholdRoleOut(BaseModel):
    id: int
    uid: str
    channel_id: StrongholdChannel
    role_name: str
    synced_at: datetime


class StrongholdMemberOut(BaseModel):
    id: int
    nickname: str
    avatar_url: str | None = None
    role_names: list[str] = Field(default_factory=list)


class StrongholdScopeOut(BaseModel):
    season_id: str
    season_label: str
    difficulty_id: str
    difficulty_label: str
    mode_type: StrongholdMode | None = None
    version_key: str | None = None


class StrongholdVersionOut(BaseModel):
    key: str
    label: str
    banner_url: str | None = None
    emblem_url: str | None = None
    last_played_date: date | None = None


class StrongholdEquipmentOut(BaseModel):
    id: str
    name: str | None = None
    tier: int | None = None
    description: str | None = None
    icon_url: str | None = None


class StrongholdTraitOut(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    icon_url: str | None = None


class StrongholdOperatorEffectOut(BaseModel):
    name: str | None = None
    description: str | None = None
    icon_url: str | None = None
    config_level: int | None = Field(
        default=None, description="Same-version chess configuration, not a live measurement."
    )
    reference_level: int | None = Field(default=None, description="Level of the reference description.")


class StrongholdOperatorOut(BaseModel):
    id: str
    normal_chess_id: str | None = Field(default=None, description="Normal chess ID in this battle's game version.")
    is_elite: bool | None = Field(default=None, description="Stronghold golden state, independent of evolve phase.")
    char_id: str | None = None
    name: str | None = None
    level: int | None = None
    phase: int | None = None
    tier: int | None = None
    skill_id: str | None = None
    module_id: str | None = None
    skill: StrongholdOperatorEffectOut | None = None
    module: StrongholdOperatorEffectOut | None = None
    profession: str | None = None
    merge_level: int | None = None
    equipment: list[StrongholdEquipmentOut] | None = None
    traits: list[StrongholdTraitOut] | None = None


class StrongholdBondOperatorOut(BaseModel):
    id: str
    char_id: str
    name: str | None = None
    tier: int | None = None


class StrongholdBondOut(BaseModel):
    bond_id: str
    name: str | None = None
    description: str | None = None
    icon_url: str | None = None
    active: bool | None = None
    layer: int | None = None
    layer_scope: Literal["role", "team", "unknown"] | None = None
    is_core: bool | None = None
    activation_count: int | None = None
    activation_rule: Literal["at_least", "at_most", "golden"] | None = None
    operators: list[StrongholdBondOperatorOut] | None = None
    show_operators: bool | None = None


class StrongholdBossOut(BaseModel):
    id: str
    enemy_id: str | None = None
    name: str | None = None
    hidden: bool | None = None
    killed: bool | None = None


class StrongholdBattleData(BaseModel):
    started_at: datetime | None = None
    team_completed: bool | None = None
    strategy_icon_url: str | None = None
    strategy_description: str | None = None
    trophy_before: int | None = None
    trophy_after: int | None = None
    coin_cost: int | None = None
    sync_count: int | None = None
    kill_count: int | None = None
    title: str | None = None
    bosses: list[StrongholdBossOut] | None = None


class StrongholdRecordOut(StrongholdScopeOut):
    id: str
    match_id: str
    ended_at: datetime
    completed: bool | None
    pass_round: int | None
    strategy_id: str | None
    strategy_name: str | None
    strategy_icon_url: str | None = None
    strategy_description: str | None = None


class StrongholdRecordDetailOut(StrongholdRecordOut):
    roster: list[StrongholdOperatorOut] | None
    bonds: list[StrongholdBondOut] | None
    battle: StrongholdBattleData
    author: StrongholdMemberOut | None = None
    role_name: str | None = None
    player_group_id: str | None = Field(default=None, description="Opaque player key scoped to this match.")
    is_own: bool = False
    own_role_id: int | None = Field(default=None, description="Local role ID, only for the viewer's own record.")
    strategy_promoter: str | None = None
    strategy_initial_hp: int | None = None
    version: StrongholdVersionOut | None = None


class StrongholdMatchOut(StrongholdScopeOut):
    id: str
    ended_at: datetime
    success: bool | None
    version: StrongholdVersionOut | None = None
    participants: list[StrongholdMemberOut]
    views: list[StrongholdRecordDetailOut] = Field(default_factory=list)
    my_record_id: str | None = None


class StrongholdRankOut(BaseModel):
    rank: int
    member: StrongholdMemberOut
    wins: int
    rounds: int | None


class StrongholdPopularBondOut(BaseModel):
    bond_id: str
    name: str | None
    description: str | None = None
    icon_url: str | None = None
    version_key: str | None = None
    version_label: str | None = None
    matches: int


class StrongholdLayerMemberOut(BaseModel):
    member: StrongholdMemberOut
    layers: int = Field(description="Sum of layer values recorded in this member's role views.")


class StrongholdLayerOut(BaseModel):
    bond_id: str
    name: str | None
    description: str | None = None
    icon_url: str | None = None
    version_key: str | None = None
    version_label: str | None = None
    layers: int = Field(description="Sum of recorded role-view values, not the team's actual layer total.")
    contributors: list[StrongholdLayerMemberOut]
    unattributed_layers: int
    team_layers: int | None = Field(default=None, description="Separate sum of explicitly reported team values.")


class StrongholdCoverageOut(BaseModel):
    records: int
    roles_with_bonds: int
    roles_with_layers: int
    matches: int
    records_with_unknown_layers: int = Field(description="Views with a numeric layer value of unspecified scope.")
    roles_with_conflicting_layers: int = 0


class StrongholdCommunityOut(BaseModel):
    matches: list[StrongholdMatchOut]
    total: int
    scopes: list[StrongholdScopeOut]
    versions: list[StrongholdVersionOut]
    date: date
    today: date
    ranking: list[StrongholdRankOut]
    filtered_role_names: list[str] = Field(default_factory=list)
    popular_bonds: list[StrongholdPopularBondOut]
    layers: list[StrongholdLayerOut]
    coverage: StrongholdCoverageOut


class StrongholdOwnOut(BaseModel):
    records: list[StrongholdRecordOut]
    total: int
    scopes: list[StrongholdScopeOut]
    versions: list[StrongholdVersionOut]
    roles: list[StrongholdRoleOut]
    sync_available: bool
    sync_status: list[StrongholdSyncStatus]
    wins: int
    known_results: int
    scoped_total: int
