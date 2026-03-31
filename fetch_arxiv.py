"""获取最近一周的arxiv论文"""
import feedparser
import pandas as pd
import os
from datetime import datetime, timedelta

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
            pub_date = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%SZ")
            if pub_date < cutoff:
                continue
            papers.append({
                "title": entry.title,
                "authors": ", ".join(author.name for author in entry.authors),
                "summary": entry.summary,
                "link": entry.link,
                "published": pub_date_str
            })
    return papers

def save_arxiv_papers(papers):
    df = pd.DataFrame(papers)
    # 去重（基于链接）
    if os.path.exists("data/arxiv_papers.csv"):
        old = pd.read_csv("data/arxiv_papers.csv")
        df = pd.concat([old, df]).drop_duplicates(subset=['link']).reset_index(drop=True)
    df.to_csv("data/arxiv_papers.csv", index=False)
    print(f"保存 {len(papers)} 篇新论文")

if __name__ == "__main__":
    papers = fetch_arxiv_papers()
    if papers:
        save_arxiv_papers(papers)
    else:
        print("本周无新论文")