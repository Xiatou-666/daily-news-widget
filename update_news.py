import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
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

    entries = []
    for item in root.findall(".//item")[:8]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
        published = (item.findtext("pubDate") or "").strip()
        if title and link:
            entries.append({
                "source": source["name"],
                "title": title,
                "link": link,
                "description": " ".join(description.split())[:500],
                "published": published,
            })
    return entries


def call_model(articles):
    prompt = """请把下面的新闻整理成适合手机小组件显示的中文 JSON。
只返回 JSON 数组，不要 Markdown，不要解释。每项必须包含：title（不超过30字）、summary（不超过80字）、url、source、published。
保留事实，不要编造；最多返回 8 条；按重要性排序。

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
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))

    content = result["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content).strip()
    return json.loads(content)


def main():
    with open("news_sources.json", encoding="utf-8") as file:
        sources = json.load(file)

    articles = []
    for source in sources:
        try:
            articles.extend(fetch_feed(source))
        except Exception as error:
            print(f"跳过 RSS {source['name']}: {error}")

    if not articles:
        raise RuntimeError("没有抓到任何 RSS 新闻")

    items = call_model(articles)
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": items[:8],
    }
    with open("news.json", "w", encoding="utf-8", newline="\n") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"已写入 {len(output['items'])} 条新闻")


if __name__ == "__main__":
    main()
