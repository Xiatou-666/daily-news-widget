# 新闻小组件自动更新

## 设置

1. 将本目录中的文件复制到你的 GitHub 仓库根目录。
2. 在仓库打开 **Settings → Secrets and variables → Actions → New repository secret**。
3. 创建 Secret：
   - Name：`APINEBULA_API_KEY`
   - Value：你的 Nebula API Key
4. 打开 **Actions → Update news widget → Run workflow** 手动测试一次。

## KWGT 地址

让 KWGT 读取：

```text
https://raw.githubusercontent.com/你的用户名/你的仓库/main/news.json
```

新闻列表位于 JSON 的 `items` 数组；每项有 `title`、`summary`、`url`、`source`、`published`。

## 说明

- GitHub Actions 在云端运行，不需要打开 ChatGPT、CCSwitch、电脑或手机。
- API Key 只放在 GitHub Secret，不要写入仓库文件。
- 默认每小时运行一次，也可以修改 workflow 中的 cron。
