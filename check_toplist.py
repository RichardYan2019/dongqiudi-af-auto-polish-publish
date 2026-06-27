import requests, json, sys
sys.stdout.reconfigure(encoding='utf-8')

cookies = {
    "auth_token": "NVhkWEJBPT07NDYwNjc0NzskMnkkMTAkYmpNN1ZrcDJrSTdFQ0JVc2dDdEhILk9rRWI5SmNDNVI1UVR0NXZBaVcxemNzbnhWMlRnVC4%3D",
    "laravel_session": "eyJpdiI6IjFDZHYydE5MeEsySndqcHBmWmFEVU5zWGJJSFBBWktqNzNQaG54UTdBdmc5IiwidmFsdWUiOiI2VkxlaUZ5Nm9kZ0MySk44cUZ1eUFGZlE4N1NCdkljVlBJYmRnTGcrS29uYVB4WWFocTVjcmhvZkE0WTlqOFo4UlpOVHg4VVpub2lJNGNMQ0NORU9PQT09IiwibWFjIjoiZjJiYzBhMDg3ZGQ0MDI1MDgxODlhN2M5NDIzZGJhOGNjZmVlMjUzZTcxNmMwYTNkOTZiYTI2NmI2ODVhNjhkMCJ9",
    "afuid": "rBAAQ2mZLmKfY3AHBUbWAg==",
}

s = requests.Session()
s.cookies.update(cookies)
s.headers.update({"User-Agent": "Mozilla/5.0"})

import json
# 查列表接口返回的 ext 字段里有什么
r = s.get("http://admin.allfootballapp.com/newarticle/admin/archives/list",
    params={"language": "en", "status": "1", "per_page": 5}, timeout=15)
a = r.json()["data"]["archives"][0]
print("列表接口 ext 字段：")
print(json.dumps(a.get("ext", {}), ensure_ascii=False, indent=2))
print("\n顶层字段中与 top 相关：")
for k, v in a.items():
    if "top" in k.lower():
        print(f"  {k}: {v}")
