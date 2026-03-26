import os
import pandas as pd
import feedparser
from datetime import datetime, timedelta, timezone
from huggingface_hub import list_models

# 配置
DATA_DIR = "data"
RELEASES_CSV = os.path.join(DATA_DIR, "company_releases.csv")
DAYS_BACK = 90  # 最近 90 天（约 3 个月）

# 厂商映射（Hugging Face 组织名 → 标准厂商名）
HF_MAPPING = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "deepseek-ai": "DeepSeek",
    "MoonshotAI": "Kimi",
    "stepfun-ai": "StepFun",
    "Qwen": "阿里巴巴（通义千问）",
    "google": "Google",
    "THUDM": "智谱AI"
}

# RSS 订阅列表（官方博客）
RSS_FEEDS = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Google AI": "https://blog.google/technology/ai/rss/",
    "Stability AI": "https://stability.ai/news?format=rss",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "Meta AI": "https://ai.meta.com/blog/feed/",
    "Microsoft Research": "https://www.microsoft.com/en-us/research/feed/",
    "Simon Willison": "https://simonwillison.net/atom/everything/",
}

# RSS 关键词过滤（不区分大小写）
RSS_KEYWORDS = [
    "gpt", "claude", "gemini", "qwen", "deepseek", "llama", "mistral",
    "model", "api", "research", "release", "launch", "announcing",
    "open source", "dataset", "tool", "agent", "multimodal"
]

def load_existing_releases():
    """加载已有发布记录，返回 (company, title, publish_date) 集合"""
    if not os.path.exists(RELEASES_CSV):
        return set()
    df = pd.read_csv(RELEASES_CSV)
    existing = set()
    for _, row in df.iterrows():
        key = (row['company'], row['title'], row['publish_date'])
        existing.add(key)
    return existing

def save_new_releases(new_records):
    """追加新记录到 CSV"""
    if not new_records:
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    df_new = pd.DataFrame(new_records)
    if os.path.exists(RELEASES_CSV):
        df_old = pd.read_csv(RELEASES_CSV)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_csv(RELEASES_CSV, index=False)
    print(f"新增 {len(new_records)} 条发布记录")

def fetch_from_huggingface(existing, cutoff_date):
    """从 Hugging Face 获取指定厂商的新模型"""
    new_records = []
    for hf_name, company in HF_MAPPING.items():
        print(f"  HF: 正在处理 {company} (组织: {hf_name})")
        try:
            models = list_models(author=hf_name, sort="lastModified", direction=-1, limit=200)  # 增加 limit 以覆盖更多历史
            for model in models:
                mod_date = model.lastModified
                if mod_date and mod_date < cutoff_date:
                    continue
                title = model.id.split('/')[-1]
                record = {
                    "id": f"hf_{model.id.replace('/', '_')}",
                    "company": company,
                    "title": title,
                    "publish_date": mod_date.strftime("%Y-%m-%d") if mod_date else "",
                    "type": "模型",
                    "open_source": "是" if model.tags and "pytorch" in model.tags else "否",
                    "summary": model.cardData.get("description", "") if model.cardData else "",
                    "details": "",
                    "url": f"https://huggingface.co/{model.id}",
                    "tags": ",".join(model.tags or []),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                key = (record["company"], record["title"], record["publish_date"])
                if key not in existing:
                    new_records.append(record)
                    existing.add(key)
        except Exception as e:
            print(f"    错误: {e}")
    return new_records

def fetch_from_rss(existing, cutoff_date):
    """从 RSS 获取厂商博客更新"""
    new_records = []
    for company, feed_url in RSS_FEEDS.items():
        print(f"  RSS: 正在处理 {company} ({feed_url})")
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                print(f"    警告：未获取到条目")
                continue
            for entry in feed.entries:
                pub_date = entry.get('published_parsed')
                if not pub_date:
                    continue
                pub_datetime = datetime(*pub_date[:6], tzinfo=timezone.utc)
                if pub_datetime < cutoff_date:
                    continue
                title = entry.title
                if not any(kw.lower() in title.lower() for kw in RSS_KEYWORDS):
                    continue
                record = {
                    "id": f"rss_{entry.id}",
                    "company": company,
                    "title": title,
                    "publish_date": pub_datetime.strftime("%Y-%m-%d"),
                    "type": "其他",
                    "open_source": "否",
                    "summary": entry.get("summary", "")[:200],
                    "details": "",
                    "url": entry.link,
                    "tags": "",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                key = (record["company"], record["title"], record["publish_date"])
                if key not in existing:
                    new_records.append(record)
                    existing.add(key)
        except Exception as e:
            print(f"    错误: {e}")
    return new_records

def main():
    print("开始初始化大厂发布日历（最近 90 天）...")
    os.makedirs(DATA_DIR, exist_ok=True)

    # 计算截止时间（UTC）
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    print(f"抓取范围：{cutoff_date.strftime('%Y-%m-%d')} 至今")

    existing = load_existing_releases()
    all_new = []

    print("从 Hugging Face 抓取...")
    all_new.extend(fetch_from_huggingface(existing, cutoff_date))

    print("从 RSS 抓取...")
    all_new.extend(fetch_from_rss(existing, cutoff_date))

    save_new_releases(all_new)
    print("初始化完成。")

if __name__ == "__main__":
    main()