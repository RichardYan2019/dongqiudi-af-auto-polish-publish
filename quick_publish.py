"""
一键快速发布 DongQiuDi 草稿文章
不改稿、不加标签，直接用草稿现有内容发布
用法：
    python quick_publish.py            # 列出草稿，交互选择
    python quick_publish.py 1,3,5      # 直接发布序号 1、3、5
    python quick_publish.py all        # 发布所有 DongQiuDi 草稿
"""
import requests
import json
import os
import sys

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

BASE = "http://admin.allfootballapp.com"


def load_session():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_session(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f)


def make_session(cookies: dict) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"{BASE}/admin/dashboard",
    })
    s.cookies.update(cookies)
    return s


TOP_TEAMS = [
    "real madrid", "barcelona", "atletico madrid",
    "arsenal", "chelsea", "man united", "manchester united",
    "man city", "manchester city", "liverpool",
    "newcastle", "aston villa", "tottenham",
    "bayern", "dortmund",
    "inter", "napoli", "milan", "juventus", "roma", "atalanta",
    "psg", "paris saint-germain",
]


def involves_top_team(title, body):
    content = (title + " " + body).lower()
    return any(t in content for t in TOP_TEAMS)


def refresh_session(cfg: dict) -> dict:
    """用 remember_me cookie 刷新 laravel_session，返回更新后的 cfg。"""
    s = make_session(cfg)
    r = s.get(f"{BASE}/admin/dashboard", timeout=15, allow_redirects=True)
    new_session = s.cookies.get("laravel_session")
    if new_session and new_session != cfg.get("laravel_session"):
        cfg["laravel_session"] = new_session
        save_session(cfg)
    return cfg


def get_drafts(session, limit=100):
    r = session.get(
        f"{BASE}/newarticle/admin/archives/list",
        params={"language": "en", "tab_type": "archive_status", "tab": "0",
                "page": 1, "per_page": limit},
        timeout=15,
    )
    return r.json()["data"]["archives"]


def get_article_detail(session, article_id):
    r = session.get(
        f"{BASE}/newarticle/admin/archives/view",
        params={"type": "article", "id": article_id, "language": "en", "include_body": "1"},
        timeout=15,
    )
    a = r.json()["data"]["archive"]
    a["body"] = a.get("ext", {}).get("archive_body", "")
    ext = a.get("ext", {})

    # 原有专栏 tabs
    raw_tabs = ext.get("archive_tabs", {}).get("common", [])
    a["original_tabs"] = []
    for t in raw_tabs:
        if isinstance(t, dict):
            v = t.get("value") or t.get("id")
            if v is not None:
                a["original_tabs"].append(str(v))
        elif t is not None:
            a["original_tabs"].append(str(t))

    # 原有球队标签 channels
    raw_ch = ext.get("archive_channels", [])
    if isinstance(raw_ch, dict):
        raw_ch = raw_ch.get("common", [])
    a["original_channels"] = []
    for ch in raw_ch:
        if isinstance(ch, dict):
            v = ch.get("value") or ch.get("id")
            if v is not None:
                a["original_channels"].append(str(v))
        elif ch is not None:
            a["original_channels"].append(str(ch))
    return a


def publish(session, article_id, article):
    post = {
        "status": "1",
        "type": "article",
        "title": article["title"],
        "source": article.get("source", ""),
        "source_url": article.get("source_url", ""),
        "writer": article.get("writer", ""),
        "litpic": article.get("litpic", ""),
        "display_time": article.get("display_time", ""),
        "sort_time": article.get("sort_time", ""),
        "language": "en",
        "add_to_tab": "1",
        "antispam_status": "1",
        "style": article.get("style", "default"),
        "redirect_in_app": "0",
        "tab_recommend": "1",
        "body": article.get("body", ""),
        "con": article.get("body", ""),
        "top_tag": "pool" if involves_top_team(article.get("title", ""), article.get("body", "")) else "nil",
        "from_third_part": "0",
        "insert_comment": "0",
        "object_attr_channel": "",
        "object_attr_other": "",
        "event_attr": "",
    }

    # 保留原有球队标签
    channels = article.get("original_channels") or ["264"]
    for i, ch in enumerate(channels):
        post[f"channels[{i}]"] = ch
        post[f"channels_level[{ch}]"] = "A"

    # 保留原有专栏 tabs
    tabs = [str(t) for t in article.get("original_tabs", [])] or ["1", "4"]
    for i, t in enumerate(tabs):
        post[f"tabs[{i}]"] = t

    r = session.post(
        f"{BASE}/newarticle/admin/archives/edit?id={article_id}",
        data=post,
        timeout=30,
    )
    return r.json()


def prompt_cookies():
    print("Cookie 已过期或未配置。请粘贴以下 cookie 值：")
    print("（从浏览器后台 F12 → Network → 任意请求的 cURL 里提取）\n")
    cookies = {}
    for name in ["auth_token", "laravel_session", "afuid"]:
        val = input(f"  {name}: ").strip()
        if len(val) < 10:
            print(f"  {name} 太短，已退出")
            sys.exit(1)
        cookies[name] = val
    save_session(cookies)
    return cookies


def parse_arg(arg, pool):
    """支持：1,3,5 或 1，3，5 或 all"""
    arg = arg.replace("，", ",").strip()
    if arg.lower() == "all":
        return pool
    indices = [int(x.strip()) - 1 for x in arg.split(",")]
    return [pool[i] for i in indices if 0 <= i < len(pool)]


def main():
    cfg = load_session()
    if not cfg:
        cfg = prompt_cookies()
    session = make_session(cfg)

    print("=== 获取草稿列表（DongQiuDi）===")
    try:
        drafts = get_drafts(session)
        if not isinstance(drafts, list):
            raise ValueError("返回格式异常")
    except Exception:
        print("Session 可能已过期，尝试自动刷新...")
        cfg = refresh_session(cfg)
        session = make_session(cfg)
        try:
            drafts = get_drafts(session)
        except Exception:
            print("自动刷新失败，请手动更新 cookie。")
            cfg = prompt_cookies()
            session = make_session(cfg)
            drafts = get_drafts(session)

    pool = [d for d in drafts if d.get("source", "").lower() == "dongqiudi"]
    print(f"共 {len(pool)} 篇 DongQiuDi 草稿\n")
    for i, d in enumerate(pool, 1):
        print(f"  {i:3}. [{d['id']}] {d.get('title', '')[:70]}")

    # 命令行参数
    if len(sys.argv) > 1:
        selected = parse_arg(sys.argv[1], pool)
    else:
        ans = input("\n输入要发布的序号（逗号分隔 / all / 回车=取消）: ").strip()
        if not ans:
            print("已取消")
            return
        selected = parse_arg(ans, pool)

    print(f"\n将发布 {len(selected)} 篇：{[d['id'] for d in selected]}\n")

    for d in selected:
        aid = d["id"]
        try:
            article = get_article_detail(session, aid)
            res = publish(session, aid, article)
            ok = res.get("errno") == 0 or res.get("code") == 1
            tag = "✓" if ok else "✗"
            print(f"  {tag} [{aid}] {article['title'][:60]}")
            if not ok:
                print(f"      返回: {res}")
        except Exception as e:
            import traceback
            print(f"  ✗ [{aid}] 错误: {e}")
            traceback.print_exc()

    print("\n完成")


if __name__ == "__main__":
    main()
