import requests
import time
import csv
import os
from datetime import datetime, timedelta
from typing import List, Dict, Set

# ==================== 配置区 ====================
# 你的 GitHub Personal Access Token
# 建议通过环境变量传入，避免硬编码
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# 搜索关键词分组（按领域）
DOMAIN_QUERIES = {
    "AI Agent": [
        "topic:ai-agent",
        "LLM Agent",
        "Agentic",
        "Autonomous Agent",
        "OpenClaw",
        "Claude Code",
        "browser-use",
        "Computer Use"
    ],
    "RAG": [
        "topic:rag",
        "Retrieval-Augmented Generation",
        "Agentic RAG",
        "GraphRAG",
        "LightRAG",
        "RAGFlow"
    ],
    "Multi-modal": [
        "topic:multimodal",
        "Vision-Language",
        "VLM",
        "LLaVA",
        "ImageBind",
        "Video Understanding",
        "Any-to-Any"
    ],
    "Long Context": [
        "Long Context",
        "Long Sequence",
        "Infinite Context",
        "Mamba",
        "SSM",
        "State Space Model",
        ">100k context"
    ],
    "Speculative Model": [
        "Speculative Decoding",
        "Draft Model",
        "Medusa",
        "Lookahead Decoding",
        "EAGLE",
        "Fast Inference"
    ]
}

# 数据文件路径
DATA_DIR = "data"
REPO_CSV = os.path.join(DATA_DIR, "all_repos.csv")
LAST_RUN_FILE = os.path.join(DATA_DIR, "last_run.txt")

# ==================== GitHub API 爬虫类 ====================
class GitHubTrendScraper:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0

    def _check_rate_limit(self):
        """检查 API 剩余次数，必要时等待"""
        if self.rate_limit_remaining < 10:
            wait_time = max(0, self.rate_limit_reset - time.time())
            if wait_time > 0:
                print(f"接近速率限制，等待 {wait_time:.0f} 秒...")
                time.sleep(wait_time + 5)

    def _make_request(self, url: str, params: dict = None, retries=3) -> dict:
        """发送 API 请求并处理速率限制和重试"""
        self._check_rate_limit()

        for attempt in range(retries):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)

                # 更新速率限制信息
                if 'X-RateLimit-Remaining' in response.headers:
                    self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
                if 'X-RateLimit-Reset' in response.headers:
                    self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])

                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    print(f"触发次级速率限制，等待 {retry_after} 秒...")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                print(f"请求失败 (尝试 {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    raise

    def search_repositories(self, query: str, sort: str = "created", order: str = "desc",
                            per_page: int = 100, max_pages: int = 10) -> List[Dict]:
        """
        搜索仓库，按创建时间排序（用于增量爬取）
        返回仓库原始数据列表
        """
        all_items = []
        url = f"{self.base_url}/search/repositories"

        for page in range(1, max_pages + 1):
            params = {
                "q": query,
                "sort": sort,
                "order": order,
                "per_page": per_page,
                "page": page
            }
            print(f"    正在爬取第 {page} 页...")
            try:
                data = self._make_request(url, params)
            except Exception as e:
                print(f"    请求失败: {e}")
                break

            items = data.get('items', [])
            if not items:
                break
            all_items.extend(items)

            # 礼貌性延迟，避免触发次级限制
            time.sleep(0.5)

        return all_items

    def extract_repo_info(self, repo_data: Dict) -> Dict:
        """提取需要的字段"""
        return {
            "id": repo_data.get("id"),
            "name": repo_data.get("full_name"),
            "description": repo_data.get("description"),
            "url": repo_data.get("html_url"),
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "language": repo_data.get("language"),
            "topics": ",".join(repo_data.get("topics", [])),
            "created_at": repo_data.get("created_at"),
            "updated_at": repo_data.get("updated_at"),
            "pushed_at": repo_data.get("pushed_at"),
            "license": repo_data.get("license", {}).get("key") if repo_data.get("license") else None,
            "size": repo_data.get("size"),
            "open_issues": repo_data.get("open_issues_count", 0),
            "subscribers_count": repo_data.get("subscribers_count", 0),
        }


# ==================== 文件操作辅助函数 ====================
def ensure_data_dir():
    """确保 data 目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)

def load_last_run() -> str:
    """读取上次运行的时间戳，格式 YYYY-MM-DD，默认返回 7 天前"""
    ensure_data_dir()
    try:
        with open(LAST_RUN_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        # 如果第一次运行，返回 7 天前的日期（避免抓取太多）
        return (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

def save_last_run(date_str: str):
    """保存本次运行的时间戳"""
    ensure_data_dir()
    with open(LAST_RUN_FILE, 'w') as f:
        f.write(date_str)

def load_existing_ids() -> Set[int]:
    """从现有的 CSV 中加载已存在的仓库 ID，用于去重"""
    if not os.path.exists(REPO_CSV):
        return set()
    existing_ids = set()
    with open(REPO_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                existing_ids.add(int(row['id']))
            except (ValueError, KeyError):
                continue
    return existing_ids

def save_repos_to_csv(repos: List[Dict], domains: List[str] = None):
    """
    将仓库信息保存到 CSV，如果文件不存在则创建并写入表头。
    如果仓库 ID 已存在，则跳过（不更新旧数据）。
    domains: 该批次项目对应的领域标签列表（与 repos 一一对应）
    """
    if not repos:
        print("没有新仓库需要保存")
        return

    ensure_data_dir()
    existing_ids = load_existing_ids()
    new_repos = []
    for repo in repos:
        if repo['id'] not in existing_ids:
            new_repos.append(repo)

    if not new_repos:
        print("所有仓库均已存在，无需新增")
        return

    # 准备写入的数据（添加 first_seen 字段）
    today = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for repo in new_repos:
        row = {
            "id": repo["id"],
            "name": repo["name"],
            "description": repo["description"],
            "url": repo["url"],
            "stars": repo["stars"],
            "forks": repo["forks"],
            "language": repo["language"],
            "topics": repo["topics"],
            "created_at": repo["created_at"],
            "first_seen": today,
            "is_active": True,        # 默认活跃
            "domains": ""              # 稍后可通过其他方式填充
        }
        rows.append(row)

    # 写入 CSV
    file_exists = os.path.isfile(REPO_CSV)
    with open(REPO_CSV, 'a', newline='', encoding='utf-8-sig') as f:
        fieldnames = ["id", "name", "description", "url", "stars", "forks",
                      "language", "topics", "created_at", "first_seen", "is_active", "domains"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerows(rows)

    print(f"新增 {len(rows)} 个仓库到 {REPO_CSV}")


# ==================== 主程序 ====================
def main():
    if not GITHUB_TOKEN :
        print("错误：请设置 GITHUB_TOKEN 环境变量或在代码中填写有效的 Token")
        return

    scraper = GitHubTrendScraper(GITHUB_TOKEN)

    # 获取上次运行时间
    last_run = load_last_run()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"上次运行: {last_run}, 今日: {today}")

    # 如果上次运行就是今天，可能已经抓过，但为了避免遗漏，我们仍允许抓取今天的数据
    # 但为了节省 API，可以跳过，这里不做限制，由使用者自行判断

    # 遍历每个领域的关键词
    for domain, keywords in DOMAIN_QUERIES.items():
        print(f"\n处理领域: {domain}")
        domain_repos = []
        for kw in keywords:
            # 构建查询：创建时间 >= last_run，包含关键词 kw
            # 注意：如果 kw 本身是 topic:xxx 格式，直接使用；否则作为全文搜索
            if kw.startswith("topic:"):
                query = f"{kw} created:>={last_run}"
            else:
                # 全文搜索，需要加引号避免空格问题（但 GitHub 会自动处理）
                query = f'"{kw}" created:>={last_run}'

            print(f"  关键词: {kw}")
            try:
                repos = scraper.search_repositories(query, sort="created", order="desc", max_pages=5)
                print(f"    获取到 {len(repos)} 个仓库")
                for repo in repos:
                    info = scraper.extract_repo_info(repo)
                    # 暂时不记录领域，后续可以单独维护一个关系表，或者直接写入 domains 字段
                    # 这里为了简化，只收集仓库信息，去重保存
                    domain_repos.append(info)
            except Exception as e:
                print(f"    搜索失败: {e}")

        # 对该领域获取的所有仓库去重（同一个仓库可能被多个关键词搜到）
        unique = {repo['id']: repo for repo in domain_repos}.values()
        print(f"领域 {domain} 共获取到 {len(unique)} 个唯一仓库")

        # 保存到 CSV（自动去重）
        save_repos_to_csv(list(unique))

    # 更新 last_run 为今天
    save_last_run(today)
    print("\n所有任务完成！")


if __name__ == "__main__":
    main()