name: Update Daily News Widget

on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:

jobs:
  update-news:
    runs-on: ubuntu-latest

    steps:
      - name: Update Gist
        env:
          GIST_TOKEN: ${{ secrets.GIST_TOKEN }}
        run: |
          python - <<'PY'
          import json
          import urllib.request

          gist_id = "597be9eb8f225a31a4452dac61b178d2"

          data = {
              "date": "2026-10-06",
              "physics": [
                  "测试：前沿物理新闻 1",
                  "测试：前沿物理新闻 2"
              ],
              "ai": [
                  "测试：AI 新闻 1",
                  "测试：AI 新闻 2"
              ],
              "tech": [
                  "测试：科技新闻 1",
                  "测试：科技新闻 2"
              ],
              "github": [
                  "测试：GitHub 热门项目 1",
                  "测试：GitHub 热门项目 2"
              ]
          }

          content = json.dumps(data, ensure_ascii=False, indent=2)

          payload = json.dumps({
              "files": {
                  "news.json": {
                      "content": content
                  }
              }
          }).encode("utf-8")

          req = urllib.request.Request(
              f"https://api.github.com/gists/{gist_id}",
              data=payload,
              method="PATCH",
              headers={
                  "Authorization": f"Bearer {__import__('os').environ['GIST_TOKEN']}",
                  "Accept": "application/vnd.github+json",
                  "X-GitHub-Api-Version": "2022-11-28",
                  "Content-Type": "application/json"
              }
          )

          with urllib.request.urlopen(req) as response:
              print("Gist update successful!")
              print(response.status)
          PY
