import feedparser
import pandas as pd
import os
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV"]

def fetch_arxiv_papers(days_back=7):
    cutoff = datetime.now() - timedelta(days=days_back)
    papers = []
    for cat in ARXIV_CATEGORIES:
        feed_url = f"https://rss.arxiv.org/rss/{cat}"
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            pub_date_str = entry.get('published')
            if not pub_date_str:
                continue
            try:
                # 使用 email.utils.parsedate_to_datetime 解析 RFC 2822 日期
                pub_date = parsedate_to_datetime(pub_date_str)
                # 转换为 naive datetime（假设为 UTC）
                if pub_date.tzinfo is not None:
                    pub_date = pub_date.replace(tzinfo=None)
            except Exception as e:
                print(f"日期解析失败: {pub_date_str}, 错误: {e}")
                continue
            if pub_date < cutoff:
                continue
            papers.append({
                "title": entry.title,
                "authors": ", ".join(author.name for author in entry.authors),
                "summary": entry.summary,
                "link": entry.link,
                "published": pub_date.strftime("%Y-%m-%d %H:%M:%S")  # 统一存储格式
            })
    return papers

def save_arxiv_papers(papers):
    if not papers:
        print("没有新论文")
        return
    df = pd.DataFrame(papers)
    # 去重（基于链接）
    if os.path.exists("data/arxiv_papers.csv"):
        old = pd.read_csv("data/arxiv_papers.csv")
        df = pd.concat([old, df]).drop_duplicates(subset=['link']).reset_index(drop=True)
    os.makedirs("data", exist_ok=True)
    df.to_csv("data/arxiv_papers.csv", index=False)
    print(f"保存 {len(papers)} 篇新论文")

if __name__ == "__main__":
    papers = fetch_arxiv_papers()
    save_arxiv_papers(papers)