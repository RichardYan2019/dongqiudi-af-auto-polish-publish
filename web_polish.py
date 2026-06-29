"""Polish Publish Web 界面"""
import os, sys, queue, threading
import requests as http_requests
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)
sys.path.insert(0, os.path.dirname(__file__))

from auto_publish import get_drafts, session as af_session
from auto_polish_publish import (
    get_article_detail, polish_text, polish_html_body,
    apply_english_rules, publish_article as do_publish,
    get_zh_article_detail, translate_title_to_en, translate_html_body_to_en,
    create_en_draft,
)

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
API_KEY = os.environ.get("OPENAI_API_KEY", "")

# article_id → {title, body, original_title, original_body, tabs, channels, channels_level, top_tag}
store = {}
# article_id → Queue
log_queues = {}


def run_polish(article_id: str, lq: queue.Queue):
    try:
        lq.put("获取草稿...")
        article = get_article_detail(article_id)
        original_title = article["title"]
        original_body  = article["body"]

        lq.put(f"原标题: {original_title}")
        lq.put("Polish 标题...")
        article["title"] = polish_text(article["title"], API_KEY)
        lq.put(f"→ {article['title']}")

        lq.put("Polish 正文（逐段处理）...")
        article["body"] = polish_html_body(article["body"], API_KEY)

        lq.put("应用英文规则...")
        article = apply_english_rules(article, API_KEY)
        lq.put(f"最终标题: {article['title']}")
        lq.put(f"置顶池: {article['top_tag']}")

        store[article_id] = {
            "title": article["title"],
            "body":  article["body"],
            "original_title": original_title,
            "original_body":  original_body,
            "original_tabs":  article["original_tabs"],
            "original_channels": article["original_channels"],
            "original_channels_level": article["original_channels_level"],
            "top_tag": article["top_tag"],
            "source":  article.get("source", ""),
            "source_url": article.get("source_url", ""),
            "writer":  article.get("writer", ""),
            "litpic":  article.get("litpic", ""),
            "display_time": article.get("display_time", ""),
            "sort_time":    article.get("sort_time", ""),
            "style":   article.get("style", "default"),
        }
        lq.put("[DONE]")
    except Exception as e:
        import traceback
        full_err = traceback.format_exc()
        print("=== POLISH ERROR ===")
        print(full_err)
        lq.put(f"[ERROR] {e}")
        for line in full_err.splitlines():
            lq.put(f"[TRACE] {line}")


def run_polish_from_zh(temp_key: str, zh_id: str, lq: queue.Queue):
    """中文 ID → 翻译 → 创建英文草稿 → 跑标准 polish 流程"""
    try:
        lq.put(f"获取中文文章 {zh_id}...")
        zh_article = get_zh_article_detail(zh_id)
        zh_title = zh_article.get("title", "")
        zh_body  = zh_article.get("body", "")
        lq.put(f"中文标题: {zh_title}")

        lq.put("翻译标题为英文...")
        en_title = translate_title_to_en(zh_title, API_KEY)
        lq.put(f"→ {en_title}")

        lq.put("翻译正文为英文（逐段处理）...")
        en_body = translate_html_body_to_en(zh_body, API_KEY)

        lq.put("在 AF 后台创建英文草稿...")
        new_en_id = create_en_draft(zh_article, en_title, en_body, logger=lambda m: lq.put(m))
        lq.put(f"[NEW_ID] {new_en_id}")
        lq.put(f"新英文文章 ID: {new_en_id}")

        # 构造 article 对象走 apply_english_rules（与 run_polish 保持一致）
        article = {
            "title": en_title,
            "body":  en_body,
            "original_tabs": [],
            "original_channels": [],
            "original_channels_level": [],
            "source":      zh_article.get("source", "DQD"),
            "source_url":  zh_article.get("source_url", ""),
            "writer":      zh_article.get("writer", ""),
            "litpic":      zh_article.get("litpic", ""),
            "display_time": zh_article.get("display_time", ""),
            "sort_time":    zh_article.get("sort_time", ""),
            "style":       zh_article.get("style", "default"),
        }

        lq.put("Polish 英文标题...")
        article["title"] = polish_text(article["title"], API_KEY)
        lq.put(f"→ {article['title']}")

        lq.put("Polish 英文正文（逐段处理）...")
        article["body"] = polish_html_body(article["body"], API_KEY)

        lq.put("应用英文规则...")
        article = apply_english_rules(article, API_KEY)
        lq.put(f"最终标题: {article['title']}")
        lq.put(f"置顶池: {article['top_tag']}")

        store[temp_key] = {
            "title": article["title"],
            "body":  article["body"],
            "original_title": zh_title,
            "original_body":  zh_body,
            "original_tabs":  article["original_tabs"],
            "original_channels": article["original_channels"],
            "original_channels_level": article["original_channels_level"],
            "top_tag": article["top_tag"],
            "source":  article.get("source", ""),
            "source_url": article.get("source_url", ""),
            "writer":  article.get("writer", ""),
            "litpic":  article.get("litpic", ""),
            "display_time": article.get("display_time", ""),
            "sort_time":    article.get("sort_time", ""),
            "style":   article.get("style", "default"),
            "target_id": str(new_en_id),
        }
        lq.put("[DONE]")
    except Exception as e:
        import traceback
        full_err = traceback.format_exc()
        print("=== POLISH-FROM-ZH ERROR ===")
        print(full_err)
        lq.put(f"[ERROR] {e}")
        for line in full_err.splitlines():
            lq.put(f"[TRACE] {line}")


@app.route("/api/polish-from-zh", methods=["POST"])
def api_polish_from_zh():
    zh_id = str(request.json.get("zh_id", "")).strip()
    if not zh_id:
        return jsonify({"error": "缺少 zh_id"}), 400
    temp_key = f"zh_{zh_id}"
    lq = queue.Queue(maxsize=500)
    log_queues[temp_key] = lq
    threading.Thread(target=run_polish_from_zh, args=(temp_key, zh_id, lq), daemon=True).start()
    return jsonify({"ok": True, "temp_key": temp_key})


@app.route("/")
def index():
    return render_template("polish.html")


@app.route("/api/drafts")
def api_drafts():
    try:
        all_drafts = get_drafts(limit=50)
        drafts = [d for d in all_drafts if d.get("source", "").lower() == "dongqiudi"][:20]
        return jsonify([{
            "id": d["id"], "title": d["title"],
            "source": d.get("source", ""), "time": d.get("display_time", ""),
        } for d in drafts])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/polish", methods=["POST"])
def api_polish():
    article_id = str(request.json.get("article_id", "")).strip()
    if not article_id:
        return jsonify({"error": "缺少 article_id"}), 400
    lq = queue.Queue(maxsize=200)
    log_queues[article_id] = lq
    threading.Thread(target=run_polish, args=(article_id, lq), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/polish-logs")
def api_polish_logs():
    article_id = request.args.get("article_id", "")
    lq = log_queues.get(article_id)
    if not lq:
        return jsonify({"error": "no log queue"}), 404

    def stream():
        while True:
            try:
                msg = lq.get(timeout=60)
                yield f"data: {msg}\n\n"
                if msg.startswith("[DONE]") or msg.startswith("[ERROR]"):
                    break
            except queue.Empty:
                yield "data: [heartbeat]\n\n"

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def make_diff_html(original: str, polished: str) -> str:
    """生成词级别的 diff，高亮显示修改部分"""
    import difflib, html
    orig_words = original.split()
    new_words = polished.split()
    matcher = difflib.SequenceMatcher(None, orig_words, new_words)
    result = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            result.append(html.escape(' '.join(orig_words[i1:i2])))
        elif op == 'replace':
            result.append(f'<span style="background:#5c3500;text-decoration:line-through;color:#ff9800">{html.escape(" ".join(orig_words[i1:i2]))}</span>'
                         f'<span style="background:#1b5e20;color:#a5d6a7"> {html.escape(" ".join(new_words[j1:j2]))}</span>')
        elif op == 'delete':
            result.append(f'<span style="background:#5c0000;text-decoration:line-through;color:#ef9a9a">{html.escape(" ".join(orig_words[i1:i2]))}</span>')
        elif op == 'insert':
            result.append(f'<span style="background:#1b5e20;color:#a5d6a7">{html.escape(" ".join(new_words[j1:j2]))}</span>')
    return ' '.join(result)


@app.route("/api/result")
def api_result():
    article_id = request.args.get("article_id", "")
    data = store.get(article_id)
    if not data:
        return jsonify({"error": "not found"}), 404
    plain_original = BeautifulSoup(data["original_body"], "html.parser").get_text("\n").strip()
    plain_polished = BeautifulSoup(data["body"], "html.parser").get_text("\n").strip()
    return jsonify({
        "original_title": data["original_title"],
        "original_body":  plain_original,
        "polished_title": data["title"],
        "polished_body":  data["body"],
        "diff_title": make_diff_html(data["original_title"], data["title"]),
        "diff_body":  make_diff_html(plain_original, plain_polished),
        "channels": [c["en_name"] for c in data["original_channels"]],
        "tabs": data["original_tabs"],
        "top_tag": data["top_tag"],
    })


@app.route("/api/publish", methods=["POST"])
def api_publish():
    body = request.json
    article_id = str(body.get("article_id", "")).strip()
    data = store.get(article_id)
    if not data:
        return jsonify({"error": "请先 polish"}), 400

    # 用前端传回的（可能已人工修改的）标题和正文
    data["title"] = body.get("title", data["title"])
    data["body"]  = body.get("body", data["body"])  # 前端传回 HTML

    # 中文流程会带 target_id（实际要发布到的英文文章 ID）；普通流程没有 target_id 时用 article_id 本身
    publish_id = data.get("target_id") or article_id

    try:
        result = do_publish(publish_id, data)
        if result.get("errno") == 0:
            store.pop(article_id, None)
            return jsonify({"ok": True, "published_id": publish_id})
        return jsonify({"error": result.get("errmsg", "未知错误")}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _call_gpt(api_key, prompt):
    base_url = os.environ.get("OPENAI_BASE_URL", "https://ai.flashapi.top/v1")
    r = http_requests.post(f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "gpt-5.5", "messages": [{"role": "user", "content": prompt}]}, timeout=180)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def _call_gemini(api_key, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    r = http_requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=180)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

TAB_NAMES = {
    "1": "Headline", "2": "Transfers", "4": "Football",
    "14": "Asia", "15": "Europe", "16": "Africa", "17": "America",
    "186": "World Cup", "225": "AF FIFA WC 2026",
}

@app.route("/api/arabic", methods=["POST"])
def api_arabic():
    try:
        body = request.json
        article_id = str(body.get("article_id", "")).strip()
        data = store.get(article_id)
        if not data:
            return jsonify({"error": "请先 polish"}), 400
        title = data["title"]
        plain = BeautifulSoup(data["body"], "html.parser").get_text("\n").strip()
        ar_title = _call_gpt(API_KEY, f"Translate this football headline to Arabic. Return only the Arabic translation:\n\n{title}")
        ar_body  = _call_gpt(API_KEY, f"Translate this football article to Arabic. Keep paragraph structure. Return only the Arabic translation:\n\n{plain}")
        tabs = [TAB_NAMES.get(str(t), f"tab:{t}") for t in data["original_tabs"]]
        channels = [c.get("en_name") or c.get("name", "") for c in data["original_channels"]]
        return jsonify({"ar_title": ar_title, "ar_body": ar_body, "tabs": tabs, "channels": channels, "top_tag": data["top_tag"]})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai", methods=["POST"])
def api_ai():
    data = request.json
    text = data.get("text", "").strip()
    mode = data.get("mode", "translate")
    provider = data.get("provider", "gemini")
    api_key = data.get("api_key", "").strip()
    target_lang = data.get("target_lang", "Vietnamese")
    if not text: return jsonify({"error": "请输入文本"}), 400
    if not api_key: return jsonify({"error": "请输入 API Key"}), 400
    prompts = {
        "translate": f"Translate the following text to {target_lang}. Only output the translation:\n\n{text}",
        "rewrite": f"Rewrite the following text in a different style. Only output the result:\n\n{text}",
        "polish": f"Polish and improve the following text. Only output the result:\n\n{text}",
    }
    try:
        fn = _call_gpt if provider == "gpt" else _call_gemini
        return jsonify({"result": fn(api_key, prompts.get(mode, prompts["translate"]))})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 置顶池管理 ──────────────────────────────────────────────────────────

def _get_article_full(article_id):
    r = af_session.get(
        "http://admin.allfootballapp.com/newarticle/admin/archives/view",
        params={"type": "article", "id": article_id, "language": "en", "include_body": "1"},
        timeout=10
    )
    return r.json()["data"]["archive"]

def _set_top_tag(article_id, top_tag_value):
    a = _get_article_full(article_id)
    body = a.get("ext", {}).get("archive_body", "")
    data = {
        "top_tag": top_tag_value, "title": a["title"],
        "body": body, "con": body, "language": "en",
        "type": "article", "status": "1",
        "source": a.get("source", ""), "source_url": a.get("source_url", ""),
        "writer": a.get("writer", ""),
        "display_time": a.get("display_time", ""),
        "sort_time": a.get("sort_time", ""),
    }
    for i, ch in enumerate(a.get("ext", {}).get("archive_channels", [])):
        data[f"channels[{i}]"] = str(ch["value"])
        data[f"channels_level[{ch['value']}]"] = "A"
    r = af_session.post(
        f"http://admin.allfootballapp.com/newarticle/admin/archives/edit?id={article_id}",
        data=data, timeout=15
    )
    return r.json().get("errno") == 0


@app.route("/api/toppool")
def api_toppool():
    """获取当前置顶池文章列表"""
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from datetime import datetime, timedelta

        r = af_session.get(
            "http://admin.allfootballapp.com/newarticle/admin/archives/list",
            params={"language": "en", "status": "1", "per_page": 100, "page": 1},
            timeout=15
        )
        ids = [a["id"] for a in r.json().get("data", {}).get("archives", [])]

        pool = []
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(_get_article_full, aid): aid for aid in ids}
            for fut in as_completed(futures):
                a = fut.result()
                if a.get("ext", {}).get("top_tag") == "pool":
                    pool.append({
                        "id": a["id"], "title": a["title"],
                        "sort_time": a.get("sort_time", ""),
                        "top_tag": "pool",
                    })

        pool.sort(key=lambda x: x["sort_time"], reverse=True)
        now = datetime.now()
        for a in pool:
            try:
                t = datetime.strptime(a["sort_time"], "%Y-%m-%d %H:%M:%S")
                a["expired"] = (now - t).total_seconds() > 12 * 3600
                a["age_hours"] = round((now - t).total_seconds() / 3600, 1)
            except Exception:
                a["expired"] = False
                a["age_hours"] = 0

        return jsonify({"pool": pool, "count": len(pool)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/toppool/run", methods=["POST"])
def api_toppool_run():
    """执行自动下架（超12小时 + 超20篇）"""
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from datetime import datetime, timedelta

        r = af_session.get(
            "http://admin.allfootballapp.com/newarticle/admin/archives/list",
            params={"language": "en", "status": "1", "per_page": 100, "page": 1},
            timeout=15
        )
        ids = [a["id"] for a in r.json().get("data", {}).get("archives", [])]

        pool_full = []
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(_get_article_full, aid): aid for aid in ids}
            for fut in as_completed(futures):
                a = fut.result()
                if a.get("ext", {}).get("top_tag") == "pool":
                    pool_full.append(a)

        pool_full.sort(key=lambda x: x.get("sort_time", ""), reverse=True)
        now = datetime.now()
        to_remove = []

        for a in pool_full:
            try:
                t = datetime.strptime(a["sort_time"], "%Y-%m-%d %H:%M:%S")
                if (now - t).total_seconds() > 12 * 3600:
                    to_remove.append((a, "超过12小时"))
            except Exception:
                pass

        remaining = [a for a in pool_full if a not in [x[0] for x in to_remove]]
        if len(remaining) > 20:
            for a in remaining[20:]:
                to_remove.append((a, "超过20篇上限"))

        results = []
        for a, reason in to_remove:
            ok = _set_top_tag(a["id"], "nil")
            results.append({"id": a["id"], "title": a["title"][:60], "reason": reason, "ok": ok})

        return jsonify({"removed": len(results), "details": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/toppool/set", methods=["POST"])
def api_toppool_set():
    """手动修改单篇文章的 top_tag"""
    body = request.json
    article_id = str(body.get("article_id", "")).strip()
    top_tag = body.get("top_tag", "nil")
    if top_tag not in ("pool", "nil", "on"):
        return jsonify({"error": "top_tag 只能是 pool/nil/on"}), 400
    ok = _set_top_tag(article_id, top_tag)
    return jsonify({"ok": ok})


if __name__ == "__main__":
    import urllib3; urllib3.disable_warnings()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
