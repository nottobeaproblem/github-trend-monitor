import requests
import time
import csv
import json
from datetime import datetime
from typing import List, Dict, Optional

class GitHubTrendScraper:
    """
    GitHub 趋势数据爬虫
    基于 GitHub REST API v3
    """
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        # API 速率限制：认证用户 5000 次/小时
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0

    def _check_rate_limit(self):
        """检查 API 剩余次数，必要时等待"""
        if self.rate_limit_remaining < 10:
            wait_time = max(0, self.rate_limit_reset - time.time())
            if wait_time > 0:
                print(f"接近速率限制，等待 {wait_time:.0f} 秒...")
                time.sleep(wait_time + 5)

    def _make_request(self, url: str, params: dict = None) -> dict:
        """发送 API 请求并处理速率限制"""
        self._check_rate_limit()
        
        response = requests.get(url, headers=self.headers, params=params)
        
        # 更新速率限制信息
        if 'X-RateLimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
        if 'X-RateLimit-Reset' in response.headers:
            self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])
        
        # 处理 429 Too Many Requests（次级速率限制）
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"触发速率限制，等待 {retry_after} 秒...")
            time.sleep(retry_after)
            return self._make_request(url, params)  # 重试
        
        response.raise_for_status()
        return response.json()

    def search_repositories(self, query: str, sort: str = "stars", order: str = "desc",
                           per_page: int = 100, max_pages: int = 10) -> List[Dict]:
        """
        搜索仓库，获取基础信息
        支持按 star 排序，获取最热项目
        """
        all_repos = []
        url = f"{self.base_url}/search/repositories"
        
        for page in range(1, max_pages + 1):
            params = {
                "q": query,
                "sort": sort,
                "order": order,
                "per_page": per_page,
                "page": page
            }
            
            print(f"  正在爬取第 {page} 页...")
            try:
                data = self._make_request(url, params)
            except Exception as e:
                print(f"  请求失败: {e}")
                break
            
            items = data.get('items', [])
            if not items:
                break
                
            all_repos.extend(items)
            
            # 礼貌性延迟，避免触发次级限制
            time.sleep(0.5)
            
        return all_repos

    def extract_repo_info(self, repo_data: Dict) -> Dict:
        """
        提取需要的字段
        """
        return {
            "id": repo_data.get("id"),
            "name": repo_data.get("full_name"),
            "description": repo_data.get("description"),
            "url": repo_data.get("html_url"),
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "language": repo_data.get("language"),
            "topics": repo_data.get("topics", []),      # 仓库主题标签
            "created_at": repo_data.get("created_at"),
            "updated_at": repo_data.get("updated_at"),
            "pushed_at": repo_data.get("pushed_at"),
            "license": repo_data.get("license", {}).get("key") if repo_data.get("license") else None,
            "size": repo_data.get("size"),
            "open_issues": repo_data.get("open_issues_count", 0),
            "subscribers_count": repo_data.get("subscribers_count", 0),
        }


def save_to_csv(repos_data: List[Dict], filename_prefix: str = 'github_trends') -> None:
    """
    将仓库数据保存为 CSV 文件，文件名包含当前日期
    """
    if not repos_data:
        print("没有数据可保存")
        return
    
    # 生成文件名：github_trends_20260319.csv
    today = datetime.now().strftime("%Y%m%d")
    filename = f"{filename_prefix}_{today}.csv"
    
    # 提取所有字段名（假设所有字典键一致）
    fieldnames = repos_data[0].keys()
    
    # 写入 CSV，使用 utf-8-sig 编码以便 Excel/SPSS 正常打开中文
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(repos_data)
    
    print(f"已保存 {len(repos_data)} 条记录到 {filename}")


def main():
    # 请替换为你的 GitHub Personal Access Token
    token = "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"
    
    scraper = GitHubTrendScraper(token)
    
    # 定义要搜索的关键词（可按需增删）
    queries = [
        "topic:artificial-intelligence",
        "topic:machine-learning",
        "topic:large-language-model",
        "topic:ai-agent",
        "topic:rag",
        "topic:multimodal",
        "topic:deep-learning",
        "llm",
        "gpt",
        "transformer",
    ]
    
    all_repos = []
    
    for query in queries:
        print(f"\n搜索: {query}")
        try:
            # 搜索仓库，按 star 数排序，每页 100 条，最多取 2 页（可根据需要调整 max_pages）
            repos = scraper.search_repositories(
                query=query,
                sort="stars",
                order="desc",
                per_page=100,
                max_pages=2   # 每个查询最多获取 200 条
            )
            
            # 提取需要的信息，并标记来源查询词
            for repo in repos:
                info = scraper.extract_repo_info(repo)
                info['search_query'] = query   # 记录是通过哪个查询找到的
                all_repos.append(info)
            
            print(f"  获取到 {len(repos)} 个仓库")
            
        except Exception as e:
            print(f"  搜索失败 {query}: {e}")
    
    # 按仓库 ID 去重（同一个仓库可能被不同关键词搜到）
    unique_repos = {repo['id']: repo for repo in all_repos}.values()
    
    # 保存为 CSV
    save_to_csv(list(unique_repos))
    
    print(f"\n完成！共收集 {len(unique_repos)} 个唯一仓库")


if __name__ == "__main__":
    main()