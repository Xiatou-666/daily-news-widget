import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timezone


BASE_URL = os.environ.get("APINEBULA_BASE_URL", "https://apinebula.ai/v1").rstrip("/")
API_KEY = os.environ["APINEBULA_API_KEY"]
MODEL = os.environ.get("APINEBULA_MODEL", "gpt-6.1-sol")


def fetch_feed(source):
    request = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "news-widget/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    def local_name(tag):
        return tag.rsplit("}", 1)[-1]

    def child_text(node, names):
        for child in list(node):
            if local_name(child.tag) in names and child.text:
                return child.text.strip()
        return ""

    entries = []
    nodes = [node for node in root.iter() if local_name(node.tag) in {"item", "entry"}]
    for item in nodes[:12]:
        title = child_text(item, {"title"})
        link = child_text(item, {"link"})
        if not link:
            for child in list(item):
                if local_name(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        description = child_text(item, {"description", "summary", "content"})
        published = child_text(item, {"pubDate", "published", "updated"})
        description = re.sub(r"<[^>]+>", " ", description)
        if title and link:
            entries.append({
                "source": source["name"],
                "category": source["category"],
                "title": title,
                "link": link,
                "description": " ".join(description.split())[:500],
                "published": published,
            })
    return entries


def call_model(articles):
    now = datetime.now(timezone.utc).isoformat()
    prompt = f"""请把下面的新闻整理成适合手机小组件显示的中文 JSON。
只返回一个 JSON 对象，不要 Markdown，不要解释。对象必须严格包含四个数组：physics、ai、tech、github。
每个数组恰好 2 项。每项必须包含：title（不超过30字）、summary（不超过80字）、url、source、published、category。
physics=前沿物理，ai=人工智能，tech=科技发展，github=GitHub/开源。
当前时间是 {now}。优先选择最近 48 小时发布的新闻；如果最近 48 小时有 OpenAI、数学、数学推理、定理证明或 AI 科研成果，优先放入 ai 类。其次选择最近 7 天的重要新闻。
优先使用同类别新闻；不足时从标题和内容最相关的新闻补足。保留事实，不要编造，不要把旧闻包装成新发布。

新闻：
""" + json.dumps(articles, ensure_ascii=False)

    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是新闻编辑，只输出合法 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        BASE_URL + "/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + API_KEY,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "news-widget/1.0",
        },
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    else:
        raise RuntimeError(f"AI API 请求失败: {last_error}")

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        # Also accept providers that return a Responses-style output_text field.
        content = result.get("output_text", "") if isinstance(result, dict) else ""
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("AI API 返回中没有可解析的文本")
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content).strip()
    parsed = json.loads(content)
    if "categories" in parsed:
        parsed = parsed["categories"]
    categories = {}
    for category in ("physics", "ai", "tech", "github"):
        categories[category] = parsed.get(category, [])[:2]
        if len(categories[category]) < 2:
            raise RuntimeError(f"分类 {category} 少于 2 条新闻")
    return categories


def fallback_categories(articles):
    """Keep the widget fresh if the model response is malformed."""
    categories = {key: [] for key in ("physics", "ai", "tech", "github")}
    for article in articles:
        category = article.get("category")
        if category not in categories or len(categories[category]) >= 2:
            continue
        categories[category].append({
            "title": article.get("title", "")[:30],
            "summary": article.get("description", "")[:80] or article.get("title", "")[:80],
            "url": article.get("link", ""),
            "source": article.get("source", ""),
            "published": article.get("published", ""),
            "category": category,
        })
    for category, items in categories.items():
        if len(items) < 2:
            raise RuntimeError(f"分类 {category} 抓取到的新闻少于 2 条")
    return categories


def validate_categories(categories):
    required = ("physics", "ai", "tech", "github")
    if not isinstance(categories, dict):
        raise RuntimeError("分类结果不是 JSON 对象")
    for category in required:
        items = categories.get(category)
        if not isinstance(items, list) or len(items) < 2:
            raise RuntimeError(f"分类 {category} 少于 2 条新闻")
    return {category: categories[category][:2] for category in required}


def main():
    with open("news_sources.json", encoding="utf-8") as file:
        sources = json.load(file)

    articles = []
    seen_links = set()
    for source in sources:
        try:
            for article in fetch_feed(source):
                if article["link"] not in seen_links:
                    seen_links.add(article["link"])
                    articles.append(article)
        except Exception as error:
            print(f"跳过 RSS {source['name']}: {error}")

    if not articles:
        raise RuntimeError("没有抓到任何 RSS 新闻")

    try:
        categories = validate_categories(call_model(articles))
    except Exception as error:
        print(f"AI 整理失败，改用 RSS 原文生成今日数据: {error}")
        categories = validate_categories(fallback_categories(articles))
    items = [item for category in ("physics", "ai", "tech", "github") for item in categories[category]]
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "categories": categories,
        "items": items,
    }
    with open("news.json", "w", encoding="utf-8", newline="\n") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"已写入 {len(output['items'])} 条新闻")


if __name__ == "__main__":
    main()
