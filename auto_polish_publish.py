"""
英文草稿 → GPT polish → 现有英文规则 → 发布
用法: python auto_polish_publish.py <article_id> [--api-key xxx] [--dry-run]
"""
import sys, os, re
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)
import requests as http_requests
from bs4 import BeautifulSoup

# 复用 auto_publish 的 session 和规则函数
sys.path.insert(0, os.path.dirname(__file__))
from auto_publish import (
    session, zh_session,
    normalize_team_names, normalize_standard_names,
    title_case, shorten_title, capitalize_names, capitalize_names_ai,
    convert_beijing_to_utc, involves_top_team,
)

BASE_URL    = "http://admin.allfootballapp.com"
BASE_URL_ZH = "https://zh-admin.allfootballapp.com"
GPT_BASE  = "https://ai.flashapi.top/v1"
GPT_MODEL = "gpt-5.5"

BLOCK_TAGS = ["p", "li", "h1", "h2", "h3", "h4", "blockquote", "td", "th"]
SKIP_TAGS  = ["script", "style", "code", "pre"]


def call_gpt(api_key: str, prompt: str) -> str:
    import time
    for attempt in range(3):
        try:
            r = http_requests.post(
                f"{GPT_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": GPT_MODEL, "messages": [{"role": "user", "content": prompt}]},
                timeout=180,
            )
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError(f"API 返回空 choices: {data}")
            return choices[0]["message"]["content"].strip()
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            raise


def _looks_like_bad_title(original: str, result: str) -> str:
    """Return reason string if title result is suspicious, else empty string."""
    if not result or not result.strip():
        return "empty title"
    r_lower = result.lower().strip().strip('"').strip("'")
    for marker in REFUSAL_MARKERS:
        if r_lower.startswith(marker) or marker in r_lower[:120]:
            return f"refusal marker: {marker!r}"
    if len(original) >= 20 and len(result.strip()) < len(original) * 0.5:
        return f"length shrunk {len(original)}->{len(result.strip())} (<50%)"
    return ""


def fix_title_caps(title: str, api_key: str) -> str:
    try:
        result = call_gpt(api_key, (
            "Fix this football headline. Rules:\n"
            "1. Capitalize proper nouns only: player names, manager names, club names, referee names, chairman/owner names, place names, competition names.\n"
            "2. Do NOT capitalize every word — follow standard English sentence-style capitalization for all other words.\n"
            "3. Do not change any words, only fix capitalization.\n"
            "4. Never shorten, summarize, or remove any words. Preserve the full headline.\n"
            "Return only the corrected headline.\n\n" + title
        ))
        issue = _looks_like_bad_title(title, result)
        if issue:
            print(f"  [fix_title_caps 结果异常，保留原标题] {issue}; preview={result[:120]!r}")
            return title
        return result
    except Exception:
        return title


REFUSAL_MARKERS = (
    "i'm sorry", "i am sorry", "i cannot", "i can't", "i can not",
    "as an ai", "i'm not able", "i am unable", "i apologize",
    "sorry, but", "unable to comply", "against my", "cannot assist",
    "违反", "无法帮助", "抱歉", "作为ai", "作为一个ai",
)


def _looks_like_refusal_or_truncated(original: str, polished: str) -> str:
    """Return reason string if polished result is suspicious, else empty string."""
    if not polished or not polished.strip():
        return "empty response"
    p_lower = polished.lower().strip()
    for marker in REFUSAL_MARKERS:
        if p_lower.startswith(marker) or (marker in p_lower[:200]):
            return f"refusal marker: {marker!r}"
    # Strip HTML tags for a fair length comparison
    orig_text = re.sub(r"<[^>]+>", "", original).strip()
    pol_text = re.sub(r"<[^>]+>", "", polished).strip()
    if len(orig_text) >= 40 and len(pol_text) < len(orig_text) * 0.6:
        return f"length shrunk {len(orig_text)}->{len(pol_text)} (<60%)"
    return ""


def polish_text(text: str, api_key: str) -> str:
    if not text.strip():
        return text
    prompt = (
        "Polish the following English football news text. "
        "Fix grammar, improve fluency and professionalism. "
        "Keep all facts, names, numbers, and HTML tags/attributes exactly as-is. "
        "Do not shorten, summarize, or remove any content. "
        "Only output the polished text, nothing else.\n\n" + text
    )
    for attempt in range(2):
        try:
            result = call_gpt(api_key, prompt)
            issue = _looks_like_refusal_or_truncated(text, result)
            if issue:
                print(f"  [polish 结果异常，保留原文] {issue}; preview={result[:120]!r}")
                return text
            return result
        except Exception as e:
            if attempt == 1:
                print(f"  [polish失败，保留原文] {e}")
                return text


def polish_html_body(html: str, api_key: str) -> str:
    import traceback as _tb
    soup = BeautifulSoup(html, "html.parser")
    for block in soup.find_all(BLOCK_TAGS):
        if block.find(SKIP_TAGS):
            continue
        inner = block.decode_contents().strip()
        if not re.search(r'[a-zA-Z]', inner):
            continue
        try:
            polished = polish_text(inner, api_key)
            # polish_text already keeps original on refusal/truncation, but double-check
            if _looks_like_refusal_or_truncated(inner, polished):
                continue
            block.clear()
            for child in list(BeautifulSoup(polished, "html.parser").contents):
                block.append(child)
        except Exception as e:
            raise RuntimeError(f"polish_html_body 在处理块时失败: {e}\n块内容: {inner[:100]}\n{_tb.format_exc()}")
    return str(soup)


def detect_world_cup(title: str, body: str, api_key: str) -> dict:
    """用 GPT 检测文章是否与世界杯相关，返回 {is_wc, continents}"""
    from bs4 import BeautifulSoup as _BS
    plain = _BS(body, "html.parser").get_text(" ")[:1500]
    prompt = (
        "Analyze this football article. Answer in JSON only, no explanation.\n"
        "Fields:\n"
        '  "is_world_cup": true/false — is this about FIFA World Cup 2026, national teams, or international football?\n'
        '  "continents": list of continents involved, using only: ["Europe","Africa","America","Asia","Oceania"]\n'
        "Return ONLY valid JSON.\n\n"
        f"Title: {title}\n\nText: {plain}"
    )
    try:
        result = call_gpt(api_key, prompt)
        import json as _json
        # Extract JSON from response
        m = re.search(r'\{.*\}', result, re.DOTALL)
        if m:
            data = _json.loads(m.group())
            return {
                "is_wc": bool(data.get("is_world_cup", False)),
                "continents": data.get("continents", []),
            }
    except Exception as e:
        print(f"  [WC检测失败] {e}")
    return {"is_wc": False, "continents": []}


# Tab IDs for World Cup tabs (value field used in POST)
WC_TAB_IDS = {
    "WorldCup": "186",       # World Cup
    "AfFifaWC": "225",       # AF FIFA World Cup 2026
    "Europe": "15",
    "Africa": "16",
    "America": "17",
    "Asia": "14",
    "Oceania": None,         # Oceania tab不存在，暂留
}
WC_CLASSIFICATION_ID = "164"  # 专题专栏: AF FIFA World Cup 2026


def get_article_detail(article_id):
    resp = session.get(
        f"{BASE_URL}/newarticle/admin/archives/view",
        params={"type": "article", "id": article_id, "language": "en", "include_body": "1"},
    )
    payload = resp.json()
    if not isinstance(payload, dict) or payload.get("errno", 0) not in (0, None):
        raise ValueError(f"文章 {article_id} 获取失败：{payload.get('msg', '后台返回异常')}")
    raw = payload.get("data")
    if not isinstance(raw, dict) or not isinstance(raw.get("archive"), dict):
        raise ValueError(f"文章 {article_id} 不存在或没有英文版本")
    data = raw["archive"]
    ext  = data.get("ext", {})
    data["body"]     = ext.get("archive_body", "")
    tabs = ext.get("archive_tabs", {})
    if isinstance(tabs, dict):
        data["original_tabs"] = tabs.get("common", [])
    else:
        data["original_tabs"] = tabs if isinstance(tabs, list) else []
    data["original_channels"]       = ext.get("archive_channels", [])
    data["original_channels_level"] = ext.get("archive_channels_level", [])
    return data


# ============================================================
# 中文文章 → 翻译 → 创建英文草稿 流程
# ============================================================

def get_zh_article_detail(zh_id):
    """从中文后台拉取中文文章详情"""
    resp = zh_session.get(
        f"{BASE_URL_ZH}/newarticle/admin/archives/view",
        params={"type": "article", "id": zh_id, "language": "zh", "include_body": "1"},
        timeout=30,
    )
    payload = resp.json()
    if not isinstance(payload, dict) or payload.get("errno", 0) not in (0, None):
        raise ValueError(f"中文文章 {zh_id} 获取失败：{payload.get('errmsg', '后台返回异常')}")
    raw = payload.get("data")
    if not isinstance(raw, dict) or not isinstance(raw.get("archive"), dict):
        raise ValueError(f"中文文章 {zh_id} 不存在或没有中文版本")
    data = raw["archive"]
    ext  = data.get("ext", {})
    data["body"] = ext.get("archive_body", "")
    return data


def translate_title_to_en(zh_title: str, api_key: str) -> str:
    """中文标题 → 英文（不含 polish，只翻译；后续 apply_english_rules 会再修标题）"""
    prompt = (
        "Translate this Chinese football news headline into natural, professional English. "
        "Keep player names, team names, and competition names accurate. "
        "Return only the translated headline, nothing else, no quotes, no extra punctuation.\n\n"
        + zh_title
    )
    return call_gpt(api_key, prompt)


def translate_html_body_to_en(html: str, api_key: str) -> str:
    """逐块翻译中文 HTML 正文为英文，保留所有标签、属性、图片"""
    import traceback as _tb
    soup = BeautifulSoup(html, "html.parser")
    for block in soup.find_all(BLOCK_TAGS):
        if block.find(SKIP_TAGS):
            continue
        inner = block.decode_contents().strip()
        # 无内容 或 无中文字符就跳过
        if not inner or not re.search(r'[一-鿿]', inner):
            continue
        try:
            prompt = (
                "Translate the following Chinese football news HTML fragment into natural, "
                "professional English. Keep ALL HTML tags, attributes, and image URLs EXACTLY as-is. "
                "Translate only the visible Chinese text. Keep player names, team names, and "
                "competition names accurate. Return only the translated HTML fragment, nothing else, "
                "no markdown code fences.\n\n" + inner
            )
            translated = call_gpt(api_key, prompt)
            # 去掉模型可能加的 ```html ... ``` 包装
            translated = re.sub(r'^\s*```(?:html)?\s*', '', translated)
            translated = re.sub(r'\s*```\s*$', '', translated)
            block.clear()
            for child in list(BeautifulSoup(translated, "html.parser").contents):
                block.append(child)
        except Exception as e:
            raise RuntimeError(f"translate_html_body_to_en 处理块失败: {e}\n块内容: {inner[:120]}\n{_tb.format_exc()}")
    return str(soup)


def _extract_new_article_id(payload):
    """从 AF 后台 create/edit 返回的 JSON 里提取新文章 ID（兼容多种字段位置）"""
    if not isinstance(payload, dict):
        return None
    for k in ("id", "article_id", "archive_id"):
        v = payload.get(k)
        if v: return v
    data = payload.get("data") or {}
    if isinstance(data, dict):
        for k in ("id", "article_id", "archive_id"):
            v = data.get(k)
            if v: return v
        archive = data.get("archive") or {}
        if isinstance(archive, dict):
            v = archive.get("id")
            if v: return v
    return None


_CACHED_VALID_EN_CHANNELS = None

def _load_channels_from_tag_overrides(logger=None):
    """
    从 tag_overrides.json 读已知有效的 EN channel ID。
    这些 value 是历史上真实 publish 时用过、被 EN 后台接受过的 channel，
    所以一定能通过 /create 的合法性校验。
    """
    log = logger or (lambda _msg: None)
    try:
        import json as _json
        path = os.path.join(os.path.dirname(__file__), "tag_overrides.json")
        if not os.path.exists(path):
            log(f"[channels] tag_overrides.json 不存在: {path}")
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        seen = []
        for entry in data.values():
            if not isinstance(entry, dict):
                continue
            cid = entry.get("value")
            if cid and str(cid) not in seen:
                seen.append(str(cid))
            if len(seen) >= 5:
                break
        log(f"[channels] 从 tag_overrides.json 加载到 {len(seen)} 个已知合法 channel: {seen}")
        return seen
    except Exception as e:
        log(f"[channels] tag_overrides.json 读取异常: {type(e).__name__}: {e}")
        return []


def _fetch_valid_en_channel_ids(logger=None):
    """
    /create 端点要求 channels 是 EN 后台真实存在的 channel ID。
    ZH/EN channel 系统独立、ID 不通用，无法直接搬。
    优先级：
      1) 缓存（之前成功过的）
      2) tag_overrides.json（确定合法）
      3) 动态从 EN 已发布文章里借
      4) 环境变量 AF_EN_FALLBACK_CHANNEL_ID
      5) 264（最后兜底，可能失败）
    """
    log = logger or (lambda _msg: None)

    global _CACHED_VALID_EN_CHANNELS
    if _CACHED_VALID_EN_CHANNELS:
        log(f"[channels] 使用缓存: {_CACHED_VALID_EN_CHANNELS}")
        return _CACHED_VALID_EN_CHANNELS

    # 1) tag_overrides.json（最可靠）
    known = _load_channels_from_tag_overrides(logger=log)
    if known:
        _CACHED_VALID_EN_CHANNELS = known[:3]  # 多带几个 channel 增加被接受概率
        return _CACHED_VALID_EN_CHANNELS

    # 2) 动态从 EN 已发布文章列表里借
    try:
        r = session.get(
            f"{BASE_URL}/newarticle/admin/archives/list",
            params={"language": "en", "status": "1", "per_page": 10, "page": 1},
            timeout=15,
        )
        archives = (r.json().get("data") or {}).get("archives") or []
        log(f"[channels] 探测 EN 已发布列表，拉到 {len(archives)} 篇文章")
        for archive in archives:
            aid = archive.get("id")
            if not aid:
                continue
            try:
                detail = get_article_detail(aid)
                channels = detail.get("original_channels") or []
                ids = [str(c.get("value")) for c in channels if c.get("value")]
                if ids:
                    _CACHED_VALID_EN_CHANNELS = ids[:3]
                    log(f"[channels] 从文章 {aid} 借到 channel: {_CACHED_VALID_EN_CHANNELS}")
                    return _CACHED_VALID_EN_CHANNELS
            except Exception as e:
                log(f"[channels] 文章 {aid} 读取异常: {type(e).__name__}: {e}")
                continue
    except Exception as e:
        log(f"[channels] 列表拉取异常: {type(e).__name__}: {e}")

    # 3) 环境变量
    env_ch = os.environ.get("AF_EN_FALLBACK_CHANNEL_ID", "").strip()
    if env_ch:
        log(f"[channels] 使用环境变量 AF_EN_FALLBACK_CHANNEL_ID={env_ch}")
        return [env_ch]

    # 4) 兜底
    log("[channels] 所有来源失败，fallback 到 264")
    return ["264"]


def create_en_draft(zh_article: dict, en_title: str, en_body: str, logger=None) -> str:
    """在 AF 英文后台创建一篇新的英文草稿，返回新生成的 article_id（字符串）"""
    log = logger or (lambda _msg: None)
    post_data = {
        "status": "0",  # 0=草稿；发布时由 publish_article 改成 1
        "type": "article",
        "title": en_title,
        "body":  en_body,
        "con":   en_body,
        "language": "en",
        "source":      zh_article.get("source", "DQD"),
        "source_url":  zh_article.get("source_url", ""),
        "writer":      zh_article.get("writer", ""),
        "litpic":      zh_article.get("litpic", ""),
        "style":       zh_article.get("style", "default"),
        "add_to_tab":       "1",
        "antispam_status":  "1",
        "redirect_in_app":  "0",
        "tab_recommend":    "1",
        "from_third_part":  "0",
        "insert_comment":   "0",
        "top_tag":          "nil",
        "object_attr_channel": "",
        "object_attr_other":   "",
        "event_attr":          "",
    }
    # 后端要求至少有 channels 字段。ZH 和 EN 后台是两套独立的 channel ID 系统
    # （ZH 用 6-7 位 ID，EN 用 3 位 ID，靠 relate_sd_id 做桥接），不能直接搬。
    # 创建阶段从一篇真实 EN 草稿里动态借一个合法 channel ID 当占位，发布前由前端覆盖。
    channel_ids = _fetch_valid_en_channel_ids(logger=log)
    for i, ch in enumerate(channel_ids):
        post_data[f"channels[{i}]"] = ch
        post_data[f"channels_level[{ch}]"] = "A"
    # 默认放进 Headline + Football 两个 tab，发布前可在前端修改
    for i, t in enumerate(["1", "4"]):
        post_data[f"tabs[{i}]"] = t

    # 几个可能的创建端点，按概率从高到低尝试（/create 已确认是正解，放最前）
    candidates = [
        f"{BASE_URL}/newarticle/admin/archives/create",
        f"{BASE_URL}/newarticle/admin/archives/add",
        f"{BASE_URL}/newarticle/admin/archives/edit",
        f"{BASE_URL}/newarticle/admin/archives/edit?id=0",
    ]
    last_err = None
    for url in candidates:
        log(f"[create_draft] POST → {url}（携带 channels={channel_ids}）")
        try:
            resp = session.post(url, data=post_data, timeout=60)
            try:
                j = resp.json()
            except Exception:
                last_err = f"{url} 返回非 JSON（HTTP {resp.status_code}）"
                log(f"[create_draft] 失败：{last_err}")
                continue
            if j.get("errno") not in (0, None):
                errno_val = j.get("errno")
                last_err = f"{url}: {j.get('errmsg', f'errno={errno_val}')}"
                log(f"[create_draft] 失败：{last_err}")
                continue
            new_id = _extract_new_article_id(j)
            if new_id:
                log(f"[create_draft] 成功，新 ID = {new_id}（端点：{url}）")
                return str(new_id)
            last_err = f"{url}: 返回 errno=0 但找不到新 ID（{str(j)[:300]}）"
            log(f"[create_draft] 失败：{last_err}")
        except Exception as e:
            last_err = f"{url}: {type(e).__name__}: {e}"
            log(f"[create_draft] 异常：{last_err}")
            continue
    raise RuntimeError(f"创建英文草稿失败：{last_err}")


def apply_english_rules(article: dict, api_key: str) -> dict:
    title = article["title"]
    body  = article["body"]

    body  = convert_beijing_to_utc(body)
    title = convert_beijing_to_utc(title)
    # 去掉 CEST/CET 等时区标记（convert_beijing_to_utc 只处理 CET+N 格式）
    body  = re.sub(r',?\s*Beijing\s+[Tt]ime\s*\([^)]*\)\s*[–—-]?\s*', ' ', body).strip()
    title = re.sub(r',?\s*Beijing\s+[Tt]ime\s*\([^)]*\)\s*[–—-]?\s*', ' ', title).strip()
    title = normalize_team_names(title)
    body  = normalize_team_names(body)
    title = re.sub(r'\bChampions League\b', 'UCL', title, flags=re.IGNORECASE)
    title = normalize_standard_names(title)
    body  = normalize_standard_names(body)
    if len(title) > 100:
        try:
            title = call_gpt(api_key, (
                f"This football headline is too long ({len(title)} chars). "
                "Rewrite or condense it to under 100 characters. "
                "Keep the core meaning. Return only the new headline, nothing else.\n\n" + title
            ))
            if len(title) > 100:
                raise ValueError(f"API 改写后仍超过100字符（{len(title)}字）：{title}")
        except Exception as e:
            raise RuntimeError(f"标题超过100字符且无法自动改写，请人工处理：{e}")
        title = normalize_team_names(title)
        title = normalize_standard_names(title)
    title = capitalize_names(title)
    title = fix_title_caps(title, api_key)

    article["title"]   = title
    article["body"]    = body
    article["top_tag"] = "pool" if involves_top_team(title, body) else "nil"

    # 世界杯检测：识别后追加对应专栏
    wc = detect_world_cup(title, body, api_key)
    if wc["is_wc"]:
        extra_tabs = [WC_TAB_IDS["WorldCup"]]
        if WC_TAB_IDS["AfFifaWC"]:
            extra_tabs.append(WC_TAB_IDS["AfFifaWC"])
        for cont in wc.get("continents", []):
            tid = WC_TAB_IDS.get(cont)
            if tid:
                extra_tabs.append(tid)
        # 追加到原有 tabs，去重
        current = [str(t) for t in article.get("original_tabs", [])]
        for t in extra_tabs:
            if t and t not in current:
                current.append(t)
        article["original_tabs"] = current
        print(f"  [WC] 检测到世界杯相关，追加专栏: {extra_tabs}，大洲: {wc['continents']}")

    # 有 World Cup 专栏的文章强制加 AF FIFA WC 2026 专题专栏并进置顶池
    final_tabs = [str(t) for t in article.get("original_tabs", [])]
    if WC_TAB_IDS["WorldCup"] in final_tabs:
        if WC_TAB_IDS["AfFifaWC"] not in final_tabs:
            final_tabs.append(WC_TAB_IDS["AfFifaWC"])
            article["original_tabs"] = final_tabs
        article["top_tag"] = "pool"
        article["classifications"] = [WC_CLASSIFICATION_ID]

    return article


def publish_article(article_id, article: dict, dry_run=False):
    channels     = article["original_channels"]
    ch_level_map = {str(c["channel_id"]): c["level"]
                    for c in article["original_channels_level"]}

    post_data = {
        "status": "1", "type": "article",
        "title": article["title"],
        "source": article.get("source", ""),
        "source_url": article.get("source_url", ""),
        "writer": article.get("writer", ""),
        "litpic": article.get("litpic", ""),
        "display_time": article.get("display_time", ""),
        "sort_time": article.get("sort_time", ""),
        "language": "en",
        "add_to_tab": "1", "antispam_status": "1",
        "style": article.get("style", "default"),
        "redirect_in_app": "0", "tab_recommend": "1",
        "body": article["body"], "con": article["body"],
        "top_tag": article.get("top_tag", "nil"),
        "from_third_part": "0", "insert_comment": "0",
        "object_attr_channel": "", "object_attr_other": "", "event_attr": "",
    }

    for i, ch in enumerate(channels):
        val = str(ch["value"])
        post_data[f"channels[{i}]"] = val
        post_data[f"channels_level[{val}]"] = ch_level_map.get(val, "A")

    tabs = [str(t) for t in article["original_tabs"]] or ["1", "4"]
    for i, t in enumerate(tabs):
        post_data[f"tabs[{i}]"] = t

    for i, c in enumerate(article.get("classifications", [])):
        post_data[f"classifications[{i}]"] = c

    if dry_run:
        print("[dry-run] 不提交，post_data 预览：")
        for k, v in post_data.items():
            if k != "body":
                print(f"  {k}: {v}")
        print(f"  body length: {len(post_data['body'])}")
        return {"errno": 0, "dry_run": True}

    resp = session.post(
        f"{BASE_URL}/newarticle/admin/archives/edit?id={article_id}",
        data=post_data, timeout=30,
    )
    return resp.json()


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if "--api-key" in args:
        idx = args.index("--api-key")
        api_key = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    if not args:
        print("用法: python auto_polish_publish.py <article_id> [--api-key xxx] [--dry-run]")
        sys.exit(1)

    if not api_key:
        api_key = input("请输入 API Key: ").strip()

    article_id = args[0]
    print(f"=== 获取草稿 {article_id} ===")
    article = get_article_detail(article_id)
    print(f"标题: {article['title']}")
    print(f"原 channels: {[c['en_name'] for c in article['original_channels']]}")
    print(f"原 tabs: {article['original_tabs']}")

    print("\n=== Polish 标题 ===")
    _orig_title = article["title"]
    _polished_title = polish_text(_orig_title, api_key)
    _issue = _looks_like_bad_title(_orig_title, _polished_title)
    if _issue:
        print(f"  [polish 标题异常，保留原标题] {_issue}; preview={_polished_title[:120]!r}")
        article["title"] = _orig_title
    else:
        article["title"] = _polished_title
    print(f"→ {article['title']}")

    print("\n=== Polish 正文 ===")
    article["body"] = polish_html_body(article["body"], api_key)
    print("正文 polish 完成")

    print("\n=== 应用英文规则 ===")
    article = apply_english_rules(article, api_key)
    print(f"最终标题: {article['title']}")
    print(f"置顶池: {article['top_tag']}")

    if not dry_run:
        confirm = input("\n确认发布？(yes/no): ").strip().lower()
        if confirm != "yes":
            print("已取消")
            sys.exit(0)

    print("\n=== 发布 ===")
    result = publish_article(article_id, article, dry_run=dry_run)
    if result.get("errno") == 0:
        print(f"成功{'（dry-run）' if dry_run else ''}")
    else:
        print(f"失败: {result}")
