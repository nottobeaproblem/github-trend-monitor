import pandas as pd
import requests
import os
import time
from datetime import datetime
import glob

def get_repo_metrics(owner, repo, token):
    """获取单个仓库的当前 Star 数"""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"token {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data['stargazers_count']
    except Exception as e:
        print(f"  获取 {owner}/{repo} 失败: {e}")
        return None

def main():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("错误：未找到 GITHUB_TOKEN 环境变量")
        return

    # 获取所有领域文件（排除 all_repos.csv 和 metrics 目录）
    domain_files = glob.glob(os.path.join("data", "*.csv"))
    domain_files = [f for f in domain_files
                    if not f.endswith("all_repos.csv")
                    and not os.path.basename(f).startswith("metrics")]

    metrics = []  # 用于保存今日指标
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 遍历每个领域，获取活跃项目的当前 Star 数
    for domain_file in domain_files:
        domain = os.path.basename(domain_file).replace(".csv", "").replace("_", " ")
        print(f"\n处理领域: {domain}")
        df = pd.read_csv(domain_file)
        active_repos = df[df['is_active'] == True]

        for index, row in active_repos.iterrows():
            full_name = row['name']
            owner, repo = full_name.split('/')
            print(f"  获取 {full_name} ...")
            stars = get_repo_metrics(owner, repo, token)
            if stars is not None:
                metrics.append({
                    'name': full_name,
                    'stars': stars,
                    'collected_at': today,
                    'domain': domain
                })
            time.sleep(0.5)  # 礼貌延迟

    # 2. 保存今日指标（包含 domain 列）
    if metrics:
        metrics_df = pd.DataFrame(metrics)
        metrics_file = f'data/metrics/metrics_{today}.csv'
        os.makedirs('data/metrics', exist_ok=True)
        metrics_df.to_csv(metrics_file, index=False)
        print(f"今日指标已保存到 {metrics_file}")
    else:
        print("今日无指标数据")
        return

    # 3. 淘汰逻辑：计算每个项目近30天的增长，标记增长 <5 的为不活跃
    # 读取全局项目文件
    if not os.path.exists('data/all_repos.csv'):
        print("全局文件不存在，跳过淘汰")
        return

    global_df = pd.read_csv('data/all_repos.csv')

    # 获取最近30天的指标文件（按文件名排序）
    all_metrics_files = sorted(os.listdir('data/metrics'))
    if len(all_metrics_files) < 2:
        print("指标数据不足（少于2天），无法进行淘汰分析")
        # 仍然需要将今日指标更新到全局文件吗？暂时不更新，保持原样
        return

    # 取最早和最晚的30天范围（如果总天数>30，则取最近30天；否则取全部）
    if len(all_metrics_files) > 30:
        recent_files = all_metrics_files[-30:]
    else:
        recent_files = all_metrics_files

    # 读取最早一天和最晚一天的数据（按文件名排序后，第一个是最早，最后一个是今天）
    first_day = pd.read_csv(os.path.join('data/metrics', recent_files[0]))
    last_day = pd.read_csv(os.path.join('data/metrics', recent_files[-1]))

    # 合并，计算增长
    merged = pd.merge(first_day, last_day, on='name', suffixes=('_first', '_last'))
    merged['growth_30d'] = merged['stars_last'] - merged['stars_first']

    # 设定淘汰阈值：30天内 Star 增长少于 5 的项目
    to_deactivate = merged[merged['growth_30d'] < 5]['name'].tolist()
    print(f"发现 {len(to_deactivate)} 个项目可能淘汰")

    # 更新全局文件中的 is_active 状态
    global_df.loc[global_df['name'].isin(to_deactivate), 'is_active'] = False
    global_df.to_csv('data/all_repos.csv', index=False)
    print(f"已标记 {len(to_deactivate)} 个项目为不活跃")

    # 可选：同步更新各领域文件中的 is_active（保持一致性）
    for domain_file in domain_files:
        domain_df = pd.read_csv(domain_file)
        domain_df.loc[domain_df['name'].isin(to_deactivate), 'is_active'] = False
        domain_df.to_csv(domain_file, index=False)
    print("已同步更新各领域文件的活跃状态")

if __name__ == "__main__":
    main()