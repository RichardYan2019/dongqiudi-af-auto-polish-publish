"""
置顶池自动管理
- 扫描最近100篇已发布文章，找出 top_tag=pool 的
- 超过12小时的自动设为 nil（不置顶）
- 置顶池超过20篇时，把最旧的挤出去
运行方式：python toppool_manager.py [--dry-run]
"""
import sys, os, json, time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

DRY_RUN = "--dry-run" in sys.argv
MAX_POOL = 20
EXPIRE_HOURS = 12
SCAN_PAGES = 5  # 每页20篇，共扫100篇

sys.path.insert(0, os.path.dirname(__file__))
from auto_publish import session

def get_article_top_tag(article_id):
    """获取单篇文章的 top_tag、sort_time 和发布所需字段"""
    try:
        r = session.get(
            "http://admin.allfootballapp.com/newarticle/admin/archives/view",
            params={"type": "article", "id": article_id, "language": "en", "include_body": "1"},
            timeout=10
        )
        a = r.json()["data"]["archive"]
        return {
            "id": article_id,
            "top_tag": a.get("ext", {}).get("top_tag", "nil"),
            "sort_time": a.get("sort_time", ""),
            "title": a.get("title", "")[:60],
            "_title": a.get("title", ""),
            "_body": a.get("ext", {}).get("archive_body", ""),
            "_source": a.get("source", ""),
            "_source_url": a.get("source_url", ""),
            "_writer": a.get("writer", ""),
            "_display_time": a.get("display_time", ""),
            "_sort_time": a.get("sort_time", ""),
            "_channels": a.get("ext", {}).get("archive_channels", []),
        }
    except Exception as e:
        return {"id": article_id, "top_tag": "nil", "sort_time": "", "title": "", "error": str(e)}

def set_top_tag(article, top_tag_value):
    """修改文章的 top_tag，需要带完整字段"""
    try:
        data = {
            "top_tag": top_tag_value,
            "title": article["_title"],
            "body": article["_body"],
            "con": article["_body"],
            "language": "en",
            "type": "article",
            "status": "1",
            "source": article["_source"],
            "source_url": article["_source_url"],
            "writer": article["_writer"],
            "display_time": article["_display_time"],
            "sort_time": article["_sort_time"],
        }
        for i, ch in enumerate(article["_channels"]):
            data[f"channels[{i}]"] = str(ch["value"])
            data[f"channels_level[{ch['value']}]"] = "A"
        r = session.post(
            f"http://admin.allfootballapp.com/newarticle/admin/archives/edit?id={article['id']}",
            data=data, timeout=15
        )
        return r.json().get("errno") == 0
    except Exception:
        return False

def scan_pool():
    """扫描最近文章，返回 top_tag=pool 的文章列表（按 sort_time 降序）"""
    all_ids = []
    for page in range(1, SCAN_PAGES + 1):
        r = session.get(
            "http://admin.allfootballapp.com/newarticle/admin/archives/list",
            params={"language": "en", "status": "1", "per_page": 20, "page": page},
            timeout=15
        )
        archives = r.json().get("data", {}).get("archives", [])
        if not archives:
            break
        all_ids.extend([a["id"] for a in archives])

    print(f"扫描 {len(all_ids)} 篇文章，并发查询 top_tag...")
    pool_articles = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(get_article_top_tag, aid): aid for aid in all_ids}
        for fut in as_completed(futures):
            result = fut.result()
            if result.get("top_tag") == "pool":
                pool_articles.append(result)

    # 按 sort_time 降序（最新在前）
    pool_articles.sort(key=lambda x: x["sort_time"], reverse=True)
    return pool_articles

def main():
    now = datetime.now()
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}开始扫描置顶池... {now.strftime('%Y-%m-%d %H:%M:%S')}\n")

    pool = scan_pool()
    print(f"当前置顶池共 {len(pool)} 篇：")
    for a in pool:
        print(f"  [{a['sort_time']}] {a['id']} {a['title']}")

    to_remove = []

    # 规则1：超过12小时的下架
    cutoff = now - timedelta(hours=EXPIRE_HOURS)
    for a in pool:
        try:
            t = datetime.strptime(a["sort_time"], "%Y-%m-%d %H:%M:%S")
            if t < cutoff:
                a["reason"] = f"超过{EXPIRE_HOURS}小时"
                to_remove.append(a)
        except Exception:
            pass

    # 规则2：超过20篇时把最旧的挤出
    remaining = [a for a in pool if a not in to_remove]
    if len(remaining) > MAX_POOL:
        overflow = remaining[MAX_POOL:]  # 最旧的
        for a in overflow:
            if a not in to_remove:
                a["reason"] = f"置顶池超过{MAX_POOL}篇"
                to_remove.append(a)

    if not to_remove:
        print("\n无需操作。")
        return

    print(f"\n需要下架 {len(to_remove)} 篇：")
    for a in to_remove:
        print(f"  [{a['sort_time']}] {a['id']} ({a.get('reason')}) {a['title']}")

    if DRY_RUN:
        print("\n[DRY RUN] 不执行实际操作。")
        return

    print("\n执行下架...")
    for a in to_remove:
        ok = set_top_tag(a, "nil")
        print(f"  {'✓' if ok else '✗'} {a['id']} {a['title']}")
        time.sleep(0.3)

if __name__ == "__main__":
    main()
