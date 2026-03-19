import pandas as pd
import requests
import os
import time
from datetime import datetime, timedelta

def get_repo_metrics(owner, repo, token):
    """获取单个仓库的当前 Star 数"""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"token {token}"}
    try:
        response = requests.get(url, headers=headers)
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
        print("错误：未找到 GITHUB_TOKEN")
        return

    # 1. 读取所有活跃项目
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
        time.sleep(0.5)  # 礼貌延迟

    # 2. 保存今日指标到新的CSV文件
    metrics_df = pd.DataFrame(metrics)
    metrics_file = f'data/metrics/metrics_{today}.csv'
    os.makedirs('data/metrics', exist_ok=True)
    metrics_df.to_csv(metrics_file, index=False)
    print(f"今日指标已保存到 {metrics_file}")

    # 3. 分析增长和淘汰（一个简化的逻辑）
    # 这里我们计算每个项目过去30天的总增长
    # 由于指标是按天文件存储的，需要整合过去30天的数据
    all_metrics_files = sorted(os.listdir('data/metrics'))[-30:] # 取最近30天的文件
    if len(all_metrics_files) < 2:
        print("数据不足，无法进行淘汰分析")
        return

    # 读取并合并数据（这里只做最简单的示例，实际可能需要更复杂的pandas操作）
    first_day = pd.read_csv(f'data/metrics/{all_metrics_files[0]}')
    last_day = pd.read_csv(f'data/metrics/{all_metrics_files[-1]}')
    merged = pd.merge(first_day, last_day, on='name', suffixes=('_first', '_last'))
    merged['growth_30d'] = merged['stars_last'] - merged['stars_first']

    # 设定淘汰阈值：30天内Star增长少于 5 的项目，标记为不活跃
    to_deactivate = merged[merged['growth_30d'] < 5]['name'].tolist()

    # 更新主CSV文件中的 is_active 状态
    df.loc[df['name'].isin(to_deactivate), 'is_active'] = False
    df.to_csv('data/all_repos.csv', index=False)
    print(f"已标记 {len(to_deactivate)} 个项目为不活跃")

if __name__ == "__main__":
    main()