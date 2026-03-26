import pandas as pd
import requests
import os
import time
import glob
from datetime import datetime, timedelta

# ==================== 配置 ====================
BATCH_SIZE = 50          # GraphQL 每批仓库数
GRAPHQL_URL = "https://api.github.com/graphql"
HEADERS = {"Authorization": f"token {os.getenv('GITHUB_TOKEN')}"}
MAX_RETRIES = 3
SLEEP_BETWEEN_BATCH = 1  # 批次间休息秒数

def graphql_get_stars_batch(repos):
    """
    repos: list of (owner, repo) tuples
    returns: dict {full_name: stars} for successful requests, None for failed repos
    """
    if not repos:
        return {}
    query_parts = []
    for idx, (owner, repo) in enumerate(repos):
        query_parts.append(f"  repo{idx}: repository(owner: \"{owner}\", name: \"{repo}\") {{ stargazerCount }}")
    query = "query {\n" + "\n".join(query_parts) + "\n}"
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(GRAPHQL_URL, json={"query": query}, headers=HEADERS, timeout=15)
            if response.status_code == 429:
                wait = 2 ** attempt
                print(f"  速率限制，等待 {wait} 秒后重试...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            if "data" in data:
                stars_map = {}
                for idx, (owner, repo) in enumerate(repos):
                    full_name = f"{owner}/{repo}"
                    stargazer = data["data"].get(f"repo{idx}", {}).get("stargazerCount")
                    if stargazer is not None:
                        stars_map[full_name] = stargazer
                    else:
                        stars_map[full_name] = None  # 标记为不存在
                return stars_map
            else:
                print(f"  GraphQL 返回错误: {data.get('errors', '未知错误')}")
                return None
        except Exception as e:
            print(f"  GraphQL 请求失败 (尝试 {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(2 ** attempt)
    return None

def get_consecutive_no_growth_days(star_series):
    """
    从最新一天向前计算连续无增长天数
    star_series: list of stars in chronological order (oldest first)
    """
    if len(star_series) < 2:
        return 0
    count = 0
    for i in range(len(star_series)-1, 0, -1):
        if star_series[i] <= star_series[i-1]:
            count += 1
        else:
            break
    return count

def main():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("错误：未找到 GITHUB_TOKEN 环境变量")
        return

    # 1. 获取所有领域文件
    domain_files = glob.glob(os.path.join("data", "*.csv"))
    domain_files = [f for f in domain_files
                    if not f.endswith("all_repos.csv")
                    and not f.endswith("company_releases.csv")
                    and not os.path.basename(f).startswith("metrics")]

    if not domain_files:
        print("警告：未找到任何领域文件，请检查 data 目录")
        return

    # 2. 收集所有活跃项目
    active_repos = []  # 列表元素: (full_name, domain)
    repo_domain_map = {}
    for domain_file in domain_files:
        domain = os.path.basename(domain_file).replace(".csv", "").replace("_", " ")
        df = pd.read_csv(domain_file)
        if 'is_active' in df.columns:
            df['is_active'] = df['is_active'].astype(str).str.lower() == 'true'
        else:
            df['is_active'] = True
        for _, row in df[df['is_active']].iterrows():
            full_name = row['name']
            active_repos.append((full_name, domain))
            repo_domain_map[full_name] = domain

    print(f"共发现 {len(active_repos)} 个活跃项目")

    if not active_repos:
        print("没有活跃项目，结束")
        return

    # 3. 分批获取 Star 数
    today = datetime.now().strftime("%Y-%m-%d")
    metrics = []
    deactivate_list = []   # 记录需要淘汰的仓库

    # 将 active_repos 按批次处理
    for i in range(0, len(active_repos), BATCH_SIZE):
        batch = active_repos[i:i+BATCH_SIZE]
        batch_names = [full_name for full_name, _ in batch]
        batch_owner_repo = [full_name.split('/') for full_name, _ in batch]
        print(f"批次 {i//BATCH_SIZE + 1}/{(len(active_repos)-1)//BATCH_SIZE+1}，共 {len(batch)} 个项目")
        stars_map = graphql_get_stars_batch(batch_owner_repo)
        if stars_map is None:
            print("  批次失败，跳过（后续会作为不存在标记）")
            # 如果批次失败，标记该批次所有仓库为不可用（需要淘汰）
            for full_name, domain in batch:
                deactivate_list.append(full_name)
        else:
            for full_name, domain in batch:
                stars = stars_map.get(full_name)
                if stars is None:
                    # 仓库不存在，标记淘汰
                    deactivate_list.append(full_name)
                else:
                    metrics.append({
                        'name': full_name,
                        'stars': stars,
                        'collected_at': today,
                        'domain': domain
                    })
        time.sleep(SLEEP_BETWEEN_BATCH)

    # 4. 保存今日指标
    if metrics:
        metrics_file = f'data/metrics/metrics_{today}.csv'
        os.makedirs('data/metrics', exist_ok=True)
        pd.DataFrame(metrics).to_csv(metrics_file, index=False)
        print(f"今日指标已保存到 {metrics_file} (成功 {len(metrics)} 条)")
    else:
        print("今日无任何指标数据")

    # 5. 淘汰处理
    # 5.1 处理不存在的仓库（404）
    if deactivate_list:
        print(f"发现 {len(deactivate_list)} 个不存在的仓库，标记为不活跃")
        # 更新全局文件
        if os.path.exists('data/all_repos.csv'):
            global_df = pd.read_csv('data/all_repos.csv')
            if 'is_active' in global_df.columns:
                global_df['is_active'] = global_df['is_active'].astype(str).str.lower() == 'true'
            else:
                global_df['is_active'] = True
            global_df.loc[global_df['name'].isin(deactivate_list), 'is_active'] = False
            global_df.to_csv('data/all_repos.csv', index=False)
        # 更新各领域文件
        for domain_file in domain_files:
            domain_df = pd.read_csv(domain_file)
            if 'is_active' in domain_df.columns:
                domain_df['is_active'] = domain_df['is_active'].astype(str).str.lower() == 'true'
            else:
                domain_df['is_active'] = True
            domain_df.loc[domain_df['name'].isin(deactivate_list), 'is_active'] = False
            domain_df.to_csv(domain_file, index=False)
        print(f"已标记 {len(deactivate_list)} 个仓库为不活跃")

    # 5.2 基于连续无增长天数淘汰
    # 获取最近30天的指标文件（如果存在）
    if not os.path.exists('data/metrics'):
        print("指标目录不存在，跳过淘汰")
        return
    all_metrics_files = sorted(os.listdir('data/metrics'))
    if len(all_metrics_files) < 2:
        print("指标数据不足（少于2天），无法进行淘汰分析")
        return

    # 读取最近30天的所有指标文件
    recent_files = all_metrics_files[-30:] if len(all_metrics_files) > 30 else all_metrics_files
    # 构建每个仓库的每日 star 序列（按日期顺序）
    star_series = {}
    for fname in recent_files:
        date = fname.replace('metrics_', '').replace('.csv', '')
        df = pd.read_csv(os.path.join('data/metrics', fname))
        for _, row in df.iterrows():
            name = row['name']
            stars = row['stars']
            star_series.setdefault(name, []).append((date, stars))

    # 计算每个仓库的连续无增长天数及当前 star
    to_deactivate_by_growth = []
    for name, series in star_series.items():
        if len(series) < 2:
            continue
        # 按日期排序
        series_sorted = sorted(series, key=lambda x: x[0])
        star_values = [s[1] for s in series_sorted]
        current_stars = star_values[-1]
        consecutive_no_growth = get_consecutive_no_growth_days(star_values)
        # 根据 star 区间确定阈值
        if current_stars < 10:
            threshold = 3
        elif current_stars < 100:
            threshold = 5
        elif current_stars < 200:
            threshold = 10
        else:
            continue  # 高热度项目不淘汰
        if consecutive_no_growth >= threshold:
            to_deactivate_by_growth.append(name)

    if to_deactivate_by_growth:
        print(f"发现 {len(to_deactivate_by_growth)} 个项目因连续无增长而淘汰")
        # 更新全局文件和各领域文件
        # 更新全局文件
        if os.path.exists('data/all_repos.csv'):
            global_df = pd.read_csv('data/all_repos.csv')
            if 'is_active' in global_df.columns:
                global_df['is_active'] = global_df['is_active'].astype(str).str.lower() == 'true'
            else:
                global_df['is_active'] = True
            global_df.loc[global_df['name'].isin(to_deactivate_by_growth), 'is_active'] = False
            global_df.to_csv('data/all_repos.csv', index=False)
        for domain_file in domain_files:
            domain_df = pd.read_csv(domain_file)
            if 'is_active' in domain_df.columns:
                domain_df['is_active'] = domain_df['is_active'].astype(str).str.lower() == 'true'
            else:
                domain_df['is_active'] = True
            domain_df.loc[domain_df['name'].isin(to_deactivate_by_growth), 'is_active'] = False
            domain_df.to_csv(domain_file, index=False)
        print(f"已标记 {len(to_deactivate_by_growth)} 个项目为不活跃")

    # 可选：保留原有的 30天总增长 <5 的淘汰（作为辅助）
    if len(all_metrics_files) >= 2:
        first_day = pd.read_csv(os.path.join('data/metrics', recent_files[0]))
        last_day = pd.read_csv(os.path.join('data/metrics', recent_files[-1]))
        merged = pd.merge(first_day, last_day, on='name', suffixes=('_first', '_last'))
        merged['growth_30d'] = merged['stars_last'] - merged['stars_first']
        to_deactivate_30d = merged[(merged['growth_30d'] < 5) & (merged['stars_last'] < 10)]['name'].tolist()
        if to_deactivate_30d:
            print(f"发现 {len(to_deactivate_30d)} 个项目因30天增长<5且star<10而淘汰")
            # 合并淘汰列表并更新（此处省略重复代码，可复用上面逻辑）

    print("analyzer 执行完成")

if __name__ == "__main__":
    main()