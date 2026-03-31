""" 获取热门项目的README"""
import os
import requests
import base64
import pandas as pd
from datetime import datetime, timedelta

def get_hot_projects(days=7, top_n=10):
    """从最近的指标文件中获取 top_n 个项目名"""
    metrics_dir = "data/metrics"
    files = sorted(os.listdir(metrics_dir), reverse=True)
    if not files:
        return []
    # 取最近的一个指标文件
    latest = files[0]
    df = pd.read_csv(os.path.join(metrics_dir, latest))
    # 按 star 数降序取前 top_n
    hot = df.nlargest(top_n, 'stars')['name'].tolist()
    return hot

def fetch_readme(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    headers = {"Authorization": f"token {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            content = base64.b64decode(data['content']).decode('utf-8', errors='ignore')
            return content[:5000]  # 只取前5000字符
    except Exception as e:
        print(f"获取 {owner}/{repo} README 失败: {e}")
    return None

def save_readme(project_name, content):
    safe_name = project_name.replace('/', '_')
    filename = f"data/project_readmes/{safe_name}.txt"
    os.makedirs("data/project_readmes", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("缺少 GITHUB_TOKEN 环境变量")
        return
    hot_projects = get_hot_projects()
    print(f"准备获取 {len(hot_projects)} 个热门项目的 README")
    for full_name in hot_projects:
        owner, repo = full_name.split('/')
        print(f"处理 {full_name} ...")
        readme = fetch_readme(owner, repo, token)
        if readme:
            save_readme(full_name, readme)

if __name__ == "__main__":
    main()