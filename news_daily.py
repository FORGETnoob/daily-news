#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日财经科技要闻（国内为主，覆盖最近 24 小时）
- 金融：财联社 / 东方财富 / 华尔街见闻 / 新浪 7x24 实时快讯（公开 JSON API，无需 key）
- 科技：IT之家新闻列表（公开 JSON API，无需 key）
交给 DeepSeek 整合成中文简报（分国内/国际两大板块，每条标注时间），
通过 QQ 邮箱 SMTP 发送 HTML 邮件。供 GitHub Actions 每天定时调用。
所有敏感信息从环境变量读取。
"""
import os
import re
import json
import ssl
import uuid
import smtplib
import urllib.request
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.header import Header

# ---------- 从环境变量读配置 ----------
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
TO_EMAIL = os.environ.get("TO_EMAIL", "")

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

BJ = timezone(timedelta(hours=8))
HOURS_WINDOW = 24  # 只保留最近 24 小时的新闻（覆盖"今天上午 + 昨天下午"）

SYSTEM_PROMPT = """你是一名专业的财经科技新闻编辑。用户会给你两批中文新闻，每条都带 [时间] 和来源，覆盖最近 24 小时。

请整合成一份中文《每日财经科技要闻》简报，要求如下：

一、分成两大板块：
- 【国内要闻】：国内发生的金融、经济、政策、上市公司、科技动态，精选最重要的 8-12 条，可稍详细。
- 【国际要闻】：国外发生的重要大事（美联储、地缘政治、国际科技巨头如 SpaceX/马斯克、英伟达、苹果、特斯拉、微软、谷歌、OpenAI 等），精选对国内有影响或特别重要的 4-6 条，可简要。

二、每条新闻都标注时间：用新闻自带的时间信息，统一格式为「HH:MM」（如 14:32），放在每条最前面；若跨日则写「MM-DD HH:MM」。

三、板块内不要零散罗列，要把相关的新闻串起来：同一主题或同一逻辑链的放在一起，点出彼此的关联（是印证、因果、传导还是对比）。

四、结尾用 2-3 句话串起今天的整体图景与市场情绪。

五、归类原则：SpaceX、苹果、谷歌、微软、英伟达、特斯拉等国际巨头 → 国际要闻；华为、腾讯、阿里、字节、比亚迪、小米等国内公司及国内政策/市场 → 国内要闻。纯促销带货略过。

六、全文 900-1200 字，适合 10-15 分钟读完；宁精勿滥。

七、直接输出 HTML 片段（不要 Markdown、不要代码块包裹、不要任何开场白或结尾寒暄），严格按如下模板：
<h2>🇨🇳 国内要闻</h2>
<ul>
<li><strong>14:32</strong> <strong>标题</strong>：要点说明</li>
...
</ul>
<h2>🌍 国际要闻</h2>
<ul>
<li><strong>09:15</strong> <strong>英伟达</strong>：要点说明</li>
...
</ul>
<p>📌 今日图景：……</p>
"""


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def http_get_json(url, headers=None):
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def clean_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"&[a-zA-Z#0-9]+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def now_ts():
    return int(datetime.now(timezone.utc).timestamp())


def within_window(ts):
    """时间戳是否在最近 HOURS_WINDOW 小时内；无法解析的保留。"""
    if ts is None:
        return True
    return (now_ts() - ts) <= HOURS_WINDOW * 3600


def fmt_ts(ts):
    """unix 秒 -> 'MM-DD HH:MM'（北京时间）"""
    try:
        return datetime.fromtimestamp(int(ts), BJ).strftime("%m-%d %H:%M")
    except Exception:
        return ""


def bj_str_to_ts(s):
    """'2026-10-04 10:55:14' 或 ISO（北京时间）-> unix 秒"""
    try:
        s2 = (s or "").replace("T", " ").split(".")[0].strip()
        if len(s2) >= 16:
            dt = datetime.strptime(s2[:16], "%Y-%m-%d %H:%M").replace(tzinfo=BJ)
            return int(dt.timestamp())
    except Exception:
        pass
    return None


# ---------- 国内金融快讯 ----------

def fetch_cls():
    """财联社电报（最新约 20 条，覆盖最近 1-2 小时）"""
    url = "https://www.cls.cn/api/cache?app=CailianpressWeb&name=telegraph&os=web&sv=8.7.9"
    data = http_get_json(url, {"Referer": "https://www.cls.cn/telegraph"})
    d = data.get("data", {}) or {}
    roll = d.get("roll_data") or d.get("telegraph") or []
    out = []
    for it in roll:
        title = (it.get("title") or "").strip()
        brief = clean_html(it.get("brief") or it.get("content") or "")
        if not title and not brief:
            continue
        ts = it.get("ctime")
        try:
            ts = int(ts)
        except Exception:
            ts = None
        if not within_window(ts):
            continue
        out.append((title or brief[:40], brief[:200], fmt_ts(ts)))
    return out


def fetch_eastmoney():
    """东方财富快讯（page_size=200，可覆盖 2 天以上）"""
    trace = str(uuid.uuid4())
    url = ("https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
           f"?client=web&biz=web_home_channel&column=350,35,466,467&order=1"
           f"&needInteractData=0&page_index=1&page_size=200&req_trace={trace}")
    data = http_get_json(url)
    out = []
    for it in (data.get("data", {}) or {}).get("list", []):
        title = (it.get("title") or "").strip()
        summary = clean_html(it.get("summary") or "")
        if not title:
            continue
        ts = bj_str_to_ts(it.get("showTime"))
        if not within_window(ts):
            continue
        out.append((title, summary[:200], fmt_ts(ts)))
    return out


def fetch_wallstreet():
    """华尔街见闻实时快讯（limit=100，可覆盖约 1.5 天）"""
    url = "https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=200"
    data = http_get_json(url, {
        "Referer": "https://wallstreetcn.com/",
        "Origin": "https://wallstreetcn.com",
    })
    out = []
    for it in (data.get("data", {}) or {}).get("items", []):
        text = clean_html(it.get("content_text") or "")
        if not text:
            continue
        ts = it.get("display_time")
        try:
            ts = int(ts)
        except Exception:
            ts = None
        if not within_window(ts):
            continue
        out.append((text[:40], text[:200], fmt_ts(ts)))
    return out


def fetch_sina():
    """新浪 7x24 全球快讯（page_size=100）"""
    url = ("https://zhibo.sina.com.cn/api/zhibo/feed"
           "?page=1&page_size=100&zhibo_id=152&tag_id=0&type=0")
    data = http_get_json(url, {"Referer": "https://finance.sina.com.cn/7x24/"})
    feed = (((data.get("result", {}) or {}).get("data", {}) or {}).get("feed", {}) or {})
    out = []
    for it in feed.get("list", []):
        text = clean_html(it.get("rich_text") or "")
        if not text:
            continue
        ts = bj_str_to_ts(it.get("create_time"))
        if not within_window(ts):
            continue
        out.append((text[:40], text[:200], fmt_ts(ts)))
    return out


# ---------- 国内科技新闻 ----------

def fetch_ithome():
    """IT之家新闻（最近约 25 条，覆盖最近 2 小时）"""
    url = "https://api.ithome.com/json/newslist/news?page=1"
    data = http_get_json(url)
    out = []
    for it in data.get("newslist", []):
        if it.get("cid") == 166:  # 好物推荐/带货分类，跳过
            continue
        title = (it.get("title") or "").strip()
        desc = clean_html(it.get("description") or "")
        if not title:
            continue
        ts = bj_str_to_ts(it.get("postdate"))
        if not within_window(ts):
            continue
        out.append((title, desc[:200], fmt_ts(ts)))
    return out


CN_FINANCE = [
    ("财联社",     fetch_cls),
    ("东方财富",   fetch_eastmoney),
    ("华尔街见闻", fetch_wallstreet),
    ("新浪7x24",   fetch_sina),
]

CN_TECH = [
    ("IT之家", fetch_ithome),
]


def collect(source_list, limit):
    collected = []
    for source, fn in source_list:
        try:
            items = fn()[:limit]
            for title, desc, t in items:
                collected.append((source, title, desc, t))
            log(f"{source}: {len(items)} 条（24h内）")
        except Exception as e:
            log(f"{source}: 抓取失败 - {e}")
    return collected


# ---------- DeepSeek 与邮件 ----------

def call_deepseek(news_text):
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": news_text},
        ],
        "temperature": 0.3,
        "max_tokens": 2400,
        "stream": False,
    }
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def send_email(html_body):
    subject = f"每日财经科技要闻 {datetime.now().strftime('%Y-%m-%d')}"
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = SMTP_USER
    msg["To"] = TO_EMAIL
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context()) as s:
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [TO_EMAIL], msg.as_string())


def main():
    if not all([DEEPSEEK_API_KEY, SMTP_USER, SMTP_PASS, TO_EMAIL]):
        log("缺少必要环境变量：DEEPSEEK_API_KEY / SMTP_USER / SMTP_PASS / TO_EMAIL")
        raise SystemExit(1)

    log("抓取国内金融快讯（最近 24h）...")
    finance = collect(CN_FINANCE, 60)
    log("抓取国内科技新闻（最近 24h）...")
    tech = collect(CN_TECH, 25)

    if not finance and not tech:
        log("没有抓到任何新闻，任务失败")
        raise SystemExit(1)

    log(f"金融 {len(finance)} 条，科技 {len(tech)} 条")

    lines = []
    for s, t, d, ts in finance:
        tm = f"时间{ts}" if ts else "时间未知"
        lines.append(f"[{tm}][金融·{s}] {t} | {d}")
    for s, t, d, ts in tech:
        tm = f"时间{ts}" if ts else "时间未知"
        lines.append(f"[{tm}][科技·{s}] {t} | {d}")
    news_text = "\n".join(lines)

    log("调用 DeepSeek 整合...")
    digest = call_deepseek(news_text)
    digest = re.sub(r"^```(?:html)?\s*", "", digest.strip())
    digest = re.sub(r"\s*```$", "", digest)

    html = (
        '<html><head><meta charset="utf-8"></head>'
        '<body style="font-family:-apple-system,Segoe UI,Microsoft YaHei,Arial,sans-serif;'
        'color:#1a1a1a;line-height:1.65;max-width:680px;">'
        f"{digest}"
        '<hr style="border:none;border-top:1px solid #eee;">'
        '<p style="color:#999;font-size:12px;">由 DeepSeek 自动整合 · '
        "金融：财联社 / 东方财富 / 华尔街见闻 / 新浪7x24 · 科技：IT之家</p>"
        "</body></html>"
    )

    log("发送邮件...")
    send_email(html)
    log(f"已发送到 {TO_EMAIL}")


if __name__ == "__main__":
    main()
