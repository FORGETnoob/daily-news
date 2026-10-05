# 每日财经科技要闻（云端定时推送）

每天中午 12:00 自动抓取全球财经/科技新闻，交给 DeepSeek 整合成中文简报，发到你邮箱。
整套跑在 GitHub 云端，**不需要你电脑开机**。

## 文件说明

| 文件 | 作用 |
|------|------|
| `news_daily.py` | 抓 RSS → 调 DeepSeek 整合 → 发邮件 |
| `.github/workflows/daily-news.yml` | 定时任务配置（每天北京 12:00 触发） |
| `README.md` | 本文档 |

---

## 一、准备三个凭证（只需一次）

### 1. DeepSeek API Key
- 打开 https://platform.deepseek.com 登录
- 左侧菜单 **API Keys** → 点 **创建 API Key** → 复制以 `sk-` 开头的字符串

### 2. QQ 邮箱 SMTP 授权码（不是登录密码）
- 打开 https://mail.qq.com 登录你的 QQ 邮箱
- 点 **设置 → 账户**
- 往下找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务**
- 在 **IMAP/SMTP服务** 处点 **开启**，按提示发短信验证
- 验证后会给你一串 **16 位授权码**（例如 `abcdefghijklmnop`），复制保存

### 3. 收件邮箱地址
- 就是你想收到新闻的邮箱，可以和发件 QQ 邮箱是同一个

---

## 二、部署到 GitHub（一次性，约 5 分钟）

### 第 1 步：新建私有仓库
1. 登录 https://github.com
2. 点右上角 **+** → **New repository**
3. 仓库名随便填（如 `daily-news`）
4. 选 **Private（私有）** ← 必须私有，否则密钥会泄露
5. **不要**勾选初始化 README，点 **Create repository**

### 第 2 步：上传这三个文件
在新建的仓库页面点 **Add file → Upload files**，把本地 `daily-news-digest` 文件夹里的内容整体拖进去（`news_daily.py`、`README.md`、以及 `.github` 文件夹），点 **Commit changes**。

> 如果网页上传无法保留 `.github` 目录结构，就改为逐个手动创建：
> - 仓库根目录 → **Add file → Create new file**，文件名填 `news_daily.py`，粘贴脚本内容
> - 再创建 `.github/workflows/daily-news.yml`（文件名直接带 `/` 会自动建目录），粘贴配置内容

### 第 3 步：配置 4 个密钥（Secrets）
进入仓库 **Settings → Secrets and variables → Actions**，点 **New repository secret**，依次添加：

| Name | 值 |
|------|-----|
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API Key（`sk-...`） |
| `SMTP_USER` | 发件 QQ 邮箱地址（如 `12345678@qq.com`） |
| `SMTP_PASS` | 第一步拿到的 16 位 SMTP 授权码 |
| `TO_EMAIL` | 收件邮箱地址 |

### 第 4 步：立即测试一次
1. 仓库页面点 **Actions** 标签
2. 左侧找到 **Daily News Digest**
3. 点 **Run workflow** → 绿色 **Run workflow** 按钮
4. 等 1-3 分钟，点进去看运行日志；成功后你的邮箱会收到测试邮件

收到邮件 = 部署成功，之后每天中午 12 点自动发。

---

## 三、注意事项

1. **时区**：任务设定为 UTC 04:00 = **北京时间 12:00**。GitHub 免费额度实际执行可能有几分钟延迟，属正常。
2. **GitHub 休眠机制**：GitHub 会在仓库 **60 天没有提交** 时暂停定时任务。建议每隔一两个月给仓库随便改点东西（或在 Actions 页手动 Run workflow 一次）保持活跃。
3. **改时间/改内容**：想改推送时间或新闻范围，编辑 `.github/workflows/daily-news.yml` 里的 cron 表达式，或改 `news_daily.py` 里的 `RSS_SOURCES` / `SYSTEM_PROMPT`。
4. **失败排查**：在 Actions 页点开某次运行，看日志里 `[时间] ...` 那几行，哪一步报错一目了然（抓取失败 / DeepSeek 调用失败 / 邮件发送失败都会分别打印）。

---

## cron 时间速查（北京时间）

| 想改成 | cron 表达式 |
|--------|-------------|
| 中午 12:00（当前） | `0 4 * * *` |
| 早上 8:00 | `0 0 * * *` |
| 早上 9:00 | `0 1 * * *` |
| 晚上 20:00 | `0 12 * * *` |

> 规则：cron 用的是 UTC 时间，比北京时间慢 8 小时。要推 12:00 → 填 `0 4`（4 点 UTC）；推 8:00 → 填 `0 0`。

������ʱ�䣺2026-10-05��
