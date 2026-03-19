import pandas as pd
import requests
import os
import time
from datetime import datetime

def get_repo_metrics(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"token {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            'name': f"{owner}/{repo}",
            'stars': data['stargazers_count'],
            'collected_at': datetime.now().strftime("%Y-%m-%d")
        }
    except Exception as e:
        print(f"  获取 {owner}/{repo} 失败: {e}")
        return None

def main():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("错误：未找到 GITHUB_TOKEN 环境变量")
        return

    if not os.path.exists('data/all_repos.csv'):
        print("错误：data/all_repos.csv 不存在，请先运行爬虫")
        return

    df = pd.read_csv('data/all_repos.csv')
    active_repos = df[df['is_active'] == True]

    metrics = []
    today = datetime.now().strftime("%Y-%m-%d")

    for index, row in active_repos.iterrows():
        full_name = row['name']
        owner, repo = full_name.split('/')
        print(f"正在获取 {full_name} ...")
        metric = get_repo_metrics(owner, repo, token)
        if metric:
            metrics.append(metric)
        time.sleep(0.5)

    metrics_df = pd.DataFrame(metrics)
    metrics_file = f'data/metrics/metrics_{today}.csv'
    os.makedirs('data/metrics', exist_ok=True)
    metrics_df.to_csv(metrics_file, index=False)
    print(f"今日指标已保存到 {metrics_file}")

    all_metrics_files = sorted(os.listdir('data/metrics'))
    if len(all_metrics_files) < 2:
        print("数据不足，无法进行淘汰分析（至少需要两天数据）")
        return

    recent_files = all_metrics_files[-30:]
    if len(recent_files) < 2:
        print("最近数据不足，无法进行淘汰分析")
        return

    first_day = pd.read_csv(f'data/metrics/{recent_files[0]}')
    last_day = pd.read_csv(f'data/metrics/{recent_files[-1]}')
    merged = pd.merge(first_day, last_day, on='name', suffixes=('_first', '_last'))
    merged['growth_30d'] = merged['stars_last'] - merged['stars_first']

    to_deactivate = merged[merged['growth_30d'] < 5]['name'].tolist()

    df.loc[df['name'].isin(to_deactivate), 'is_active'] = False
    df.to_csv('data/all_repos.csv', index=False)
    print(f"已标记 {len(to_deactivate)} 个项目为不活跃")

if __name__ == "__main__":
    main()