"""Vendored from Womsxd/MihoyoBBSTools setting.py (MIT).

https://github.com/Womsxd/MihoyoBBSTools
Keep salt / version / act_id / luna URLs in sync with upstream master.
Cloud games, 国际服, 七圣召唤 omitted — not used by 战鸽.
"""

# 米游社的 Salt（与 version 必须配套）
mihoyobbs_salt = "47f15f1b66bee46b816115d8e8e6ebb6"
mihoyobbs_salt_web = "d9200c846b10886e8c874fc33c8f308b"
mihoyobbs_salt_x4 = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"
mihoyobbs_salt_x6 = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"
mihoyobbs_verify_key = "bll8iq97cem8"
mihoyobbs_version = "2.109.0"
mihoyobbs_Client_type = "2"  # 1 ios / 2 android
mihoyobbs_Client_type_web = "5"  # 4 pc web / 5 mobile web

mihoyobbs_List = {
    1: {"id": "1", "forumId": "1", "name": "崩坏3"},
    2: {"id": "2", "forumId": "26", "name": "原神"},
    3: {"id": "3", "forumId": "30", "name": "崩坏2"},
    4: {"id": "4", "forumId": "37", "name": "未定事件簿"},
    5: {"id": "5", "forumId": "34", "name": "大别野"},
    6: {"id": "6", "forumId": "52", "name": "崩坏：星穹铁道"},
    8: {"id": "8", "forumId": "57", "name": "绝区零"},
    9: {"id": "9", "forumId": "948", "name": "崩坏：因缘精灵"},
    10: {"id": "10", "forumId": "950", "name": "星布谷地"},
}

bbs_api = "https://bbs-api.miyoushe.com"
web_api = "https://api-takumi.mihoyo.com"
passport_api = "https://passport-api.mihoyo.com"

account_Info_url = web_api + "/binding/api/getUserGameRolesByCookie"
bbs_account_info = "https://webapi.account.mihoyo.com/Api/cookie_accountinfo_by_loginticket"
bbs_get_multi_token_by_login_ticket = f"{web_api}/auth/api/getMultiTokenByLoginTicket"
bbs_get_cookie_token_by_stoken = f"{web_api}/auth/api/getCookieAccountInfoBySToken"
bbs_tasks_list = f"{bbs_api}/apihub/wapi/getUserMissionsState"
bbs_sign_url = f"{bbs_api}/apihub/app/api/signIn"
bbs_sign_info_url = f"{bbs_api}/apihub/app/api/signInInfo"
bbs_post_list_url = f"{bbs_api}/post/api/getForumPostList"
bbs_detail_url = f"{bbs_api}/post/api/getPostFull"
bbs_share_url = f"{bbs_api}/apihub/api/getShareConf"
bbs_like_url = f"{bbs_api}/apihub/sapi/upvotePost"
bbs_user_full_info = f"{bbs_api}/user/api/getUserFullInfo"
bbs_user_businesses = f"{bbs_api}/user/api/getUserBusinesses"

cn_game_lang = "zh-cn"
cn_game_checkin_rewards = f"{web_api}/event/luna/home?lang={cn_game_lang}"
cn_game_is_signurl = f"{web_api}/event/luna/info?lang={cn_game_lang}"
cn_game_sign_url = f"{web_api}/event/luna/sign"

honkai2_act_id = "e202203291431091"
honkai3rd_act_id = "e202306201626331"
genshin_act_id = "e202311201442471"
honkai_sr_act_id = "e202304121516551"

zzz_web_api = "https://act-nap-api.mihoyo.com"
zzz_game_checkin_rewards = f"{zzz_web_api}/event/luna/zzz/home?lang={cn_game_lang}"
zzz_game_is_signurl = f"{zzz_web_api}/event/luna/zzz/info?lang={cn_game_lang}"
zzz_game_sign_url = f"{zzz_web_api}/event/luna/zzz/sign"
zzz_act_id = "e202406242138391"

# 米游币商城：对齐 nonebot-plugin-mystool / Mys_Goods_Tool
mall_point_sn = "myb"
mall_app_id = 1
mall_page_size = 20
url_myb_points = f"{web_api}/common/homutreasure/v1/web/user/point"
url_good_list = f"{web_api}/mall/v1/web/goods/list"
url_good_detail = f"{web_api}/mall/v1/web/goods/detail"
url_exchange = "https://api-takumi.miyoushe.com/mall/v1/web/goods/exchange"
url_address = f"{web_api}/account/address/list"

# 商品分区 game= 查询参数（无 _cn 后缀）
mall_game_keys = ("bh3", "hk4e", "nxx", "hkrpg", "nap", "bh2", "bbs")

headers = {
    "Accept": "application/json, text/plain, */*",
    "DS": "",
    "x-rpc-channel": "miyousheluodi",
    "Origin": "https://webstatic.mihoyo.com",
    "x-rpc-app_version": mihoyobbs_version,
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 "
        f"miHoYoBBS/{mihoyobbs_version}"
    ),
    "x-rpc-client_type": mihoyobbs_Client_type_web,
    "Referer": "",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,en-US;q=0.8",
    "X-Requested-With": "com.mihoyo.hyperion",
    "Cookie": "",
    "x-rpc-device_id": "",
}

BBS_OKHTTP_UA = "okhttp/4.9.3"
