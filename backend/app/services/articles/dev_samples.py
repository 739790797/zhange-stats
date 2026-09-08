"""开发环境酒馆示例文（幂等）。

仅 ``python -m local_dev.seed_tavern`` 调用；启动与生产更新不会写入。
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.timeutil import now_naive
from app.models.articles import Article, ArticleCategory
from app.models.user import User, UserRole
from app.services.articles import service as articles_svc
from app.services.articles.defaults import (
    drop_legacy_empty_categories,
    ensure_default_categories,
)
from app.services.articles.welcome import (
    WELCOME_BODY,
    WELCOME_SLUG,
    WELCOME_SUMMARY,
    ensure_welcome_article,
)

_SAMPLES: tuple[dict, ...] = (
    {
        "slug": "dev-site-update-sep",
        "title": "本周站点小记",
        "category": "circle",
        "days_ago": 0,
        "hour": 16,
        "minute": 20,
        "summary": "酒馆首页换成信息流了：最新/热门、分类和搜索在上面，右侧是重点关注。欢迎文还在，有问题直接留言。",
        "comments": ("排版清爽多了。", "重点关注里能看到欢迎文，好找。"),
        "body": """酒馆大厅不再做成论坛板块，而是左边文章、右边小组件。

- **最新 / 热门**：热门按评论数排，没有评论就还是按发布时间。
- **分类**：资讯、分享、公告，点一下就能筛。
- **搜索**：只搜标题和摘要，够用就先这样。

右侧「重点关注」会把欢迎文放在最上面。没有阅读量和点赞，数字都是真的评论数。

有想发的攻略或闲聊，作者权限开了就能写。草稿在「我的文稿」里，发布后才进大厅。
""",
    },
    {
        "slug": "dev-weekend-raid",
        "title": "周末开箱与联机备忘",
        "category": "raid",
        "days_ago": 0,
        "hour": 8,
        "minute": 15,
        "summary": "这周末谁还缺人、缺钥匙、缺一把能打的配装，先写在这儿，省得群里翻半天。",
        "comments": (),
        "body": """周六晚如果人齐，优先海关和工厂各一局热身，再决定要不要进大图。

钥匙和保险先在图鉴页对一下，别进门才发现缺一张卡。联机房间要密码的话，只在群里发，不要写进文章正文。

人不够就改打单人准备，别干等。下回把常用配装截一张丢进酒馆也行。
""",
    },
    {
        "slug": "dev-perseid-moon",
        "title": "当满月遇上英仙座流星雨",
        "category": "casual",
        "days_ago": 1,
        "hour": 22,
        "minute": 20,
        "summary": "月亮太亮、流星又不肯打卡。楼下空地站了半小时，最后记住的是蝉鸣和便利店关灯。",
        "comments": ("同款空军。", "下次换没路灯的河堤吧。"),
        "body": """预报写着峰值，实际是满月把天洗白了。流星大概有两三颗，一颗还疑似飞机。

手机拍了全黑，只好用眼睛看。便利店十点关灯之后，蝉还在叫，风倒是凉快。

这种日子不适合当攻略，只适合写进酒馆：出去站一会儿，回来喝一口，明天还是打本。
""",
    },
    {
        "slug": "dev-steam-hours",
        "title": "Steam 游玩时长怎么看才不晕",
        "category": "circle",
        "days_ago": 1,
        "hour": 19,
        "minute": 40,
        "summary": "两周、总时长、深夜还在线——大厅里的数字各有各的口径，这篇把常用口径摊开讲。",
        "comments": (),
        "body": """圈子主页上的时长，默认是 Steam 回报过来的游玩统计，不是我们自己掐表。

看「最近两周」适合问这周谁在猛打；看总时长适合翻冷门库。正在游戏中的状态有延迟，刷新一下再下结论。

没绑定 Steam 的成员不会出现在排行里，不是系统把人吃了。
""",
    },
    {
        "slug": "dev-tarkov-handbook",
        "title": "塔科夫图鉴：子弹、钥匙和地图标点",
        "category": "guides",
        "days_ago": 2,
        "hour": 21,
        "minute": 5,
        "summary": "图鉴页怎么切常规 / PVE，钥匙和子弹去哪查，地图标点又是哪套数据。",
        "comments": ("PVE 和常规别看串了。",),
        "body": """打开塔科夫攻略后，先确认当前是常规还是 PVE，两套价格和任务进度不是同一份。

- **物品**：搜名字或短名，子弹表可以按穿透排序。
- **钥匙**：看箱和门，别只看售价。
- **地图**：标点来自图鉴数据，不是实时雷达。

工作台出图是配装预览，不是图鉴源。工厂和裸枪用静图；自定义配件才走换图。
""",
    },
    {
        "slug": "dev-skland-channel",
        "title": "森空岛签到：官服和 B 服别混着看",
        "category": "guides",
        "days_ago": 3,
        "hour": 12,
        "minute": 30,
        "summary": "已经签过还显示未签、补奖没到账，多半是渠道认错了。对照这篇排一下。",
        "comments": (),
        "body": """官服和 B 服的签到记录不是同一条线。B 服当天若只有空记录，不要直接当成「还没签」。

绑定的时候看清角色渠道。补奖也不要两边各点一遍，容易点到已经领过的。

盒子练度是另一回事：进盒子页会尽量读库，签到展示页则会回源。两个数字对不上时，先看你打开的是哪一页。
""",
    },
    {
        "slug": "dev-tavern-rules",
        "title": "酒馆发文与评论约定",
        "category": "notice",
        "days_ago": 4,
        "hour": 9,
        "minute": 18,
        "summary": "谁能发文、草稿去哪、删除会不会从库里抹掉。先看完再点「写文章」。",
        "comments": (),
        "body": """未登录可以读已发布的文章和评论。留言需要登录。

写文章要管理员把你标成作者；站点管理员不必进作者名单也能写，也能管全部稿。

- 草稿只在「我的文稿」里出现。
- 删除是收回大厅展示，不是从库里抹掉，管理员仍能在酒馆管理里看到。
- 评论一层回复即可，别把长讨论做成楼中楼。

欢迎文可以当模板：先摘要，再分小节。
""",
    },
    {
        "slug": "dev-weekend-plan-draft",
        "title": "（草稿）下周末要不要再开一桌",
        "category": "raid",
        "days_ago": 0,
        "hour": 10,
        "minute": 0,
        "status": "draft",
        "summary": "还没想好人数和地图，先存成草稿，不进大厅。",
        "comments": (),
        "body": """这是开发环境里的草稿示例，大厅里看不到。

作者打开「我的文稿」能继续改，发布后才会出现在列表里。
""",
    },
)


def _stamp(days_ago: int, hour: int, minute: int):
    now = now_naive()
    when = (now - timedelta(days=days_ago)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    if when > now:
        when = now - timedelta(minutes=3)
    return when


def _commenters(db: Session, admin: User) -> list[User]:
    others = (
        db.query(User)
        .filter(User.id != admin.id)
        .order_by(User.id.asc())
        .limit(3)
        .all()
    )
    return others or [admin]


def _refresh_welcome(db: Session, notice: ArticleCategory) -> None:
    row = (
        db.query(Article)
        .options(selectinload(Article.categories))
        .filter(Article.slug == WELCOME_SLUG)
        .first()
    )
    if row is None:
        return
    changed = False
    if "刊头" in (row.body or ""):
        row.body = WELCOME_BODY
        row.summary = WELCOME_SUMMARY
        row.updated_at = now_naive()
        changed = True
    if all(cat.id != notice.id for cat in row.categories):
        row.categories.append(notice)
        changed = True
    if changed:
        db.commit()


def _apply_sample_categories(
    db: Session, cats: dict[str, ArticleCategory]
) -> None:
    mapping = {spec["slug"]: spec["category"] for spec in _SAMPLES}
    mapping[WELCOME_SLUG] = "notice"
    changed = False
    for slug, cat_key in mapping.items():
        cat = cats.get(cat_key)
        if cat is None:
            continue
        row = (
            db.query(Article)
            .options(selectinload(Article.categories))
            .filter(Article.slug == slug)
            .first()
        )
        if row is None:
            continue
        if [item.id for item in row.categories] != [cat.id]:
            row.categories = [cat]
            changed = True
    if changed:
        db.commit()


def ensure_dev_sample_articles(db: Session) -> dict:
    """幂等写入分类、示例稿和少量评论。仅 CLI 灌数；生产与启动路径不调用。"""
    if get_settings().is_production:
        return {"created": 0, "skipped": "production"}
    admin = (
        db.query(User)
        .filter(User.role == UserRole.admin)
        .order_by(User.id.asc())
        .first()
    )
    if admin is None:
        return {"created": 0, "skipped": "no-admin"}

    ensure_welcome_article(db)
    cats = ensure_default_categories(db)
    _refresh_welcome(db, cats["notice"])

    created = 0
    commenters = _commenters(db, admin)
    for spec in _SAMPLES:
        existing = db.query(Article.id).filter(Article.slug == spec["slug"]).first()
        if existing is not None:
            continue
        cat = cats[spec["category"]]
        status = spec.get("status") or articles_svc.STATUS_PUBLISHED
        row = articles_svc.create_article(
            db,
            author=admin,
            title=spec["title"],
            body=spec["body"].strip(),
            slug=spec["slug"],
            summary=spec["summary"],
            status=status,
            category_ids=[cat.id],
        )
        when = _stamp(spec["days_ago"], spec["hour"], spec["minute"])
        row.created_at = when
        row.updated_at = when
        if status == articles_svc.STATUS_PUBLISHED:
            row.published_at = when
        db.commit()
        created += 1
        if status != articles_svc.STATUS_PUBLISHED:
            continue
        for index, text in enumerate(spec.get("comments") or ()):
            user = commenters[index % len(commenters)]
            articles_svc.add_comment(db, row.slug, user=user, body=text)
    _apply_sample_categories(db, cats)
    drop_legacy_empty_categories(db)
    return {"created": created, "skipped": None}
