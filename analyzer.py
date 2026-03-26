import pandas as pd
import requests
import os
import time
from datetime import datetime
import glob

def get_repo_metrics(owner, repo, token, retries=3):
    """获取单个仓库的当前 Star 数，支持重试"""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"token {token}"}
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 404:
                print(f"  仓库 {owner}/{repo} 不存在（404），标记为不活跃")
                return None, True  # 返回 (None, need_deactivate)
            response.raise_for_status()
            data = response.json()
            return data['stargazers_count'], False
        except requests.exceptions.RequestException as e:
            print(f"  获取 {owner}/{repo} 失败 (尝试 {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
            else:
                return None, False
    return None, False

def main():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("错误：未找到 GITHUB_TOKEN 环境变量")
        return

    # 获取所有领域文件（排除 all_repos.csv、company_releases.csv 和 metrics 目录）
    domain_files = glob.glob(os.path.join("data", "*.csv"))
    domain_files = [f for f in domain_files
                    if not f.endswith("all_repos.csv")
                    and not f.endswith("company_releases.csv")
                    and not os.path.basename(f).startswith("metrics")]

    if not domain_files:
        print("警告：未找到任何领域文件，请检查 data 目录")
        return

    metrics = []          # 今日指标列表
    deactivate_list = []  # 需要标记为不活跃的仓库（404）
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 遍历每个领域，获取活跃项目的当前 Star 数
    for domain_file in domain_files:
        domain = os.path.basename(domain_file).replace(".csv", "").replace("_", " ")
        print(f"\n处理领域: {domain}")
        df = pd.read_csv(domain_file)
        # 转换 is_active 为布尔类型
        if 'is_active' in df.columns:
            df['is_active'] = df['is_active'].astype(str).str.lower() == 'true'
        else:
            df['is_active'] = True

        active_repos = df[df['is_active'] == True]
        print(f"  活跃项目数: {len(active_repos)}")

        for index, row in active_repos.iterrows():
            full_name = row['name']
            owner, repo = full_name.split('/')
            print(f"  获取 {full_name} ...")
            stars, need_deactivate = get_repo_metrics(owner, repo, token)
            if stars is not None:
                metrics.append({
                    'name': full_name,
                    'stars': stars,
                    'collected_at': today,
                    'domain': domain
                })
            if need_deactivate:
                deactivate_list.append(full_name)
            time.sleep(0.5)  # 礼貌延迟

    # 2. 保存今日指标（即使只有部分数据也保存）
    if metrics:
        metrics_df = pd.DataFrame(metrics)
        metrics_file = f'data/metrics/metrics_{today}.csv'
        os.makedirs('data/metrics', exist_ok=True)
        metrics_df.to_csv(metrics_file, index=False)
        print(f"今日指标已保存到 {metrics_file} (成功 {len(metrics)} 条)")
    else:
        print("今日无任何指标数据，无法继续淘汰分析")
        # 仍然尝试标记 404 仓库（如果存在）
        if deactivate_list:
            print("发现需要标记为不活跃的仓库，将进行更新")
        else:
            return

    # 3. 处理 404 仓库：标记为不活跃
    if deactivate_list:
        print(f"发现 {len(deactivate_list)} 个不存在的仓库，准备标记为不活跃")
        # 更新全局文件
        if os.path.exists('data/all_repos.csv'):
            global_df = pd.read_csv('data/all_repos.csv')
            if 'is_active' in global_df.columns:
                global_df['is_active'] = global_df['is_active'].astype(str).str.lower() == 'true'
            else:
                global_df['is_active'] = True
            global_df.loc[global_df['name'].isin(deactivate_list), 'is_active'] = False
            global_df.to_csv('data/all_repos.csv', index=False)
            print(f"已更新全局文件，标记 {len(deactivate_list)} 个仓库为不活跃")
        # 更新各领域文件
        for domain_file in domain_files:
            domain_df = pd.read_csv(domain_file)
            if 'is_active' in domain_df.columns:
                domain_df['is_active'] = domain_df['is_active'].astype(str).str.lower() == 'true'
            else:
                domain_df['is_active'] = True
            domain_df.loc[domain_df['name'].isin(deactivate_list), 'is_active'] = False
            domain_df.to_csv(domain_file, index=False)
        print("已同步更新各领域文件的活跃状态")

    # 4. 淘汰逻辑（仅当有足够的历史数据时执行）
    if not metrics:
        return

    # 读取全局项目文件（用于淘汰）
    if not os.path.exists('data/all_repos.csv'):
        print("全局文件不存在，跳过淘汰")
        return

    global_df = pd.read_csv('data/all_repos.csv')
    if 'is_active' in global_df.columns:
        global_df['is_active'] = global_df['is_active'].astype(str).str.lower() == 'true'
    else:
        global_df['is_active'] = True

    # 获取最近30天的指标文件
    all_metrics_files = sorted(os.listdir('data/metrics'))
    if len(all_metrics_files) < 2:
        print("指标数据不足（少于2天），无法进行淘汰分析")
        return

    if len(all_metrics_files) > 30:
        recent_files = all_metrics_files[-30:]
    else:
        recent_files = all_metrics_files

    first_day = pd.read_csv(os.path.join('data/metrics', recent_files[0]))
    last_day = pd.read_csv(os.path.join('data/metrics', recent_files[-1]))

    # 合并，计算增长
    merged = pd.merge(first_day, last_day, on='name', suffixes=('_first', '_last'))
    merged['growth_30d'] = merged['stars_last'] - merged['stars_first']
    to_deactivate = merged[merged['growth_30d'] < 5]['name'].tolist()
    print(f"发现 {len(to_deactivate)} 个项目可能淘汰（30天增长<5）")

    if to_deactivate:
        global_df.loc[global_df['name'].isin(to_deactivate), 'is_active'] = False
        global_df.to_csv('data/all_repos.csv', index=False)
        print(f"已标记 {len(to_deactivate)} 个项目为不活跃")

        # 同步更新各领域文件
        for domain_file in domain_files:
            domain_df = pd.read_csv(domain_file)
            if 'is_active' in domain_df.columns:
                domain_df['is_active'] = domain_df['is_active'].astype(str).str.lower() == 'true'
            else:
                domain_df['is_active'] = True
            domain_df.loc[domain_df['name'].isin(to_deactivate), 'is_active'] = False
            domain_df.to_csv(domain_file, index=False)
        print("已同步更新各领域文件的活跃状态")

    print("analyzer 执行完成")

if __name__ == "__main__":
    main()