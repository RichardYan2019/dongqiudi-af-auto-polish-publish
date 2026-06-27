import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from auto_publish import session

ARTICLE_ID = "4557279"

# 1. 查当前 top_tag
r = session.get(
    "http://admin.allfootballapp.com/newarticle/admin/archives/view",
    params={"type": "article", "id": ARTICLE_ID, "language": "en", "include_body": "1"},
    timeout=10
)
a = r.json()["data"]["archive"]
body = a.get("ext", {}).get("archive_body", "")
print(f"修改前 top_tag: {a.get('ext', {}).get('top_tag', 'nil')}")
print(f"标题: {a['title']}")

# 2. 带完整字段修改 top_tag
print("\n尝试设置 top_tag=nil（带 channels）...")
existing_channels = a.get("ext", {}).get("archive_channels", [])
data = {
    "top_tag": "nil",
    "title": a["title"],
    "body": body,
    "con": body,
    "language": "en",
    "type": "article",
    "status": "1",
    "source": a.get("source", ""),
    "source_url": a.get("source_url", ""),
    "writer": a.get("writer", ""),
    "display_time": a.get("display_time", ""),
    "sort_time": a.get("sort_time", ""),
}
for i, ch in enumerate(existing_channels):
    data[f"channels[{i}]"] = str(ch["value"])
    data[f"channels_level[{ch['value']}]"] = "A"
r2 = session.post(
    f"http://admin.allfootballapp.com/newarticle/admin/archives/edit?id={ARTICLE_ID}",
    data=data, timeout=15
)
print(f"响应: {r2.status_code} {r2.text[:200]}")

# 3. 确认修改结果
r3 = session.get(
    "http://admin.allfootballapp.com/newarticle/admin/archives/view",
    params={"type": "article", "id": ARTICLE_ID, "language": "en"},
    timeout=10
)
a3 = r3.json()["data"]["archive"]
print(f"\n修改后 top_tag: {a3.get('ext', {}).get('top_tag', 'nil')}")
