import sys, json
sys.path.insert(0, ".")
from auto_publish import session

article_id = sys.argv[1] if len(sys.argv) > 1 else input("article_id: ").strip()
resp = session.get(
    "http://admin.allfootballapp.com/newarticle/admin/archives/view",
    params={"type": "article", "id": article_id, "language": "en", "include_body": "1"}
)
data = resp.json()["data"]["archive"]
ext = data.get("ext", {})
ext.pop("archive_body", None)  # 正文太长，不打印
print(json.dumps(ext, indent=2, ensure_ascii=False))
