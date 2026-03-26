import pandas as pd
import requests
import os
import time
from datetime import datetime, timedelta
import glob

# ==================== GraphQL 批量获取 Star 数 ====================
def get_stars_batch(repos, token):
    """
    repos: list of (owner, repo) tuples
    returns: dict {full_name: stars}
    """
    results = {}
    batch_size = 50
    for i in range(0, len(repos), batch_size):
        batch = repos[i:i+batch_size]
        query = "query {\n"
        for idx, (owner, repo) in enumerate(batch):
            # 使用别名，确保变量名唯一
            query += f"  r{idx}: repository(owner: \"{owner}\", name: \"{repo}\") {{ stargazerCount }}\n"
        query += "}"
        headers = {"Authorization": f"token {token}"}
        try:
            response = requests.post("https://api.github.com/graphql", json={"query": query}, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            if "data" in data:
                for idx, (owner, repo) in enumerate(batch):
                    full_name = f"{owner}/{repo}"
                    star_data = data["data"].get(f"r{idx}")
                    if star_data is not None:
                        results[full_name] = star_data["stargazerCount"]
                    else:
                        # 仓库可能不存在或已删除
                        results[full_name] = None
            else:
                # 错误处理：打印错误信息，继续下一批
                print(f"GraphQL batch error: {data}")
                # 可选：回退到逐个请求？这里简单标记所有为 None
                for owner, repo in batch:
                    full_name = f"{owner}/{repo}"
                    results[full_name] = None
        except Exception as e:
            print(f"GraphQL batch request failed: {e}")
            for owner, repo in batch:
                results[f"{owner}/{repo}"] = None
        time.sleep(0.5)  # 避免触发次级速率限制
    return results

# ==================== 连续无增长天数计算 ====================
def consecutive_no_growth_days(star_series):
    """
    star_series: list of stars in chronological order (oldest first)
    returns: number of consecutive days without growth from the latest day backwards
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

# ==================== 主函数 ====================
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
    all_active_repos = []          # 存储 (full_name, domain)
    domain_repo_map = {}           # full_name -> domain
    today = datetime.now().strftime("%Y-%m-%d")

    for domain_file in domain_files:
        domain = os.path.basename(domain_file).replace(".csv", "").replace("_", " ")
        df = pd.read_csv(domain_file)
        # 列名兼容：优先使用 'name'，否则尝试其他
        name_col = None
        for col in ['name', 'full_name', 'repo_name']:
            if col in df.columns:
                name_col = col
                break
        if name_col is None:
            print(f"警告：领域文件 {domain_file} 中没有找到名称列，跳过")
            continue
        # 处理 is_active 列
        if 'is_active' in df.columns:
            df['is_active'] = df['is_active'].astype(str).str.lower() == 'true'
        else:
            df['is_active'] = True

        active = df[df['is_active'] == True]
        for _, row in active.iterrows():
            full_name = row[name_col]
            owner, repo = full_name.split('/')
            all_active_repos.append((owner, repo))
            domain_repo_map[full_name] = domain

    print(f"共有 {len(all_active_repos)} 个活跃项目")

    # 3. 批量获取当前 Star 数
    print("正在批量获取当前 Star 数...")
    stars_map = get_stars_batch(all_active_repos, token)

    # 4. 生成今日指标文件
    metrics = []
    deactivate_list = []   # 404 仓库（stars_map 中为 None）
    for (owner, repo) in all_active_repos:
        full_name = f"{owner}/{repo}"
        stars = stars_map.get(full_name)
        if stars is None:
            deactivate_list.append(full_name)
            continue
        metrics.append({
            'name': full_name,
            'stars': stars,
            'collected_at': today,
            'domain': domain_repo_map[full_name]
        })

    if metrics:
        metrics_file = f'data/metrics/metrics_{today}.csv'
        os.makedirs('data/metrics', exist_ok=True)
        pd.DataFrame(metrics).to_csv(metrics_file, index=False)
        print(f"今日指标已保存到 {metrics_file} (成功 {len(metrics)} 条)")
    else:
        print("今日无任何指标数据")
        if deactivate_list:
            print("发现需要标记为不活跃的仓库，将进行更新")
        else:
            return

    # 5. 标记 404 仓库为不活跃
    if deactivate_list:
        print(f"发现 {len(deactivate_list)} 个不存在的仓库，准备标记为不活跃")
        # 更新全局文件
        if os.path.exists('data/all_repos.csv'):
            global_df = pd.read_csv('data/all_repos.csv')
            name_col = None
            for col in ['name', 'full_name', 'repo_name']:
                if col in global_df.columns:
                    name_col = col
                    break
            if name_col is None:
                print("错误：global_df 中找不到名称列，跳过更新")
            else:
                if 'is_active' in global_df.columns:
                    global_df['is_active'] = global_df['is_active'].astype(str).str.lower() == 'true'
                else:
                    global_df['is_active'] = True
                global_df.loc[global_df[name_col].isin(deactivate_list), 'is_active'] = False
                global_df.to_csv('data/all_repos.csv', index=False)
                print(f"已更新全局文件，标记 {len(deactivate_list)} 个仓库为不活跃")
        # 更新各领域文件
        for domain_file in domain_files:
            domain_df = pd.read_csv(domain_file)
            name_col = None
            for col in ['name', 'full_name', 'repo_name']:
                if col in domain_df.columns:
                    name_col = col
                    break
            if name_col is None:
                continue
            if 'is_active' in domain_df.columns:
                domain_df['is_active'] = domain_df['is_active'].astype(str).str.lower() == 'true'
            else:
                domain_df['is_active'] = True
            domain_df.loc[domain_df[name_col].isin(deactivate_list), 'is_active'] = False
            domain_df.to_csv(domain_file, index=False)
        print("已同步更新各领域文件的活跃状态")

    # 6. 淘汰逻辑（基于连续无增长天数 + 原有规则）
    # 需要读取最近 30 天的指标文件
    metrics_dir = 'data/metrics'
    if not os.path.exists(metrics_dir):
        print("指标目录不存在，跳过淘汰")
        return

    all_metrics_files = sorted(os.listdir(metrics_dir))
    if len(all_metrics_files) < 2:
        print("指标数据不足（少于2天），无法进行淘汰分析")
        return

    # 取最近 30 天文件（如果超过 30 天）
    if len(all_metrics_files) > 30:
        recent_files = all_metrics_files[-30:]
    else:
        recent_files = all_metrics_files

    # 读取所有指标文件，按项目聚合
    all_data = []
    for fname in recent_files:
        df = pd.read_csv(os.path.join(metrics_dir, fname))
        # 确保有 name 列
        if 'name' not in df.columns:
            # 尝试其他列名
            name_col = None
            for col in ['name', 'full_name', 'repo_name']:
                if col in df.columns:
                    name_col = col
                    break
            if name_col is None:
                continue
            df = df.rename(columns={name_col: 'name'})
        df['date'] = fname.split('_')[1].replace('.csv', '')  # 提取日期
        all_data.append(df)

    if not all_data:
        print("无法加载指标文件，跳过淘汰")
        return

    combined = pd.concat(all_data, ignore_index=True)
    # 按项目分组，收集每日 star 列表
    growth_analysis = []
    for name, group in combined.groupby('name'):
        # 按日期排序
        group = group.sort_values('date')
        stars_series = group['stars'].tolist()
        # 计算连续无增长天数
        no_growth_days = consecutive_no_growth_days(stars_series)
        # 获取最新 star 数
        latest_stars = stars_series[-1]
        # 计算 30 天总增长（如果至少有两天数据）
        if len(stars_series) >= 2:
            total_growth = stars_series[-1] - stars_series[0]
        else:
            total_growth = 0

        # 淘汰判断
        should_deactivate = False
        # 条件1：404 已经处理过，这里不再重复
        # 条件2：连续无增长天数超过阈值
        if latest_stars < 10 and no_growth_days >= 3:
            should_deactivate = True
        elif latest_stars < 100 and no_growth_days >= 5:
            should_deactivate = True
        elif latest_stars < 200 and no_growth_days >= 10:
            should_deactivate = True
        # 条件3：30 天总增长小于 5（辅助淘汰）
        if total_growth < 5:
            should_deactivate = True

        if should_deactivate:
            growth_analysis.append(name)

    print(f"发现 {len(growth_analysis)} 个项目满足淘汰条件（连续无增长或增长过慢）")

    if growth_analysis:
        # 更新全局文件
        if os.path.exists('data/all_repos.csv'):
            global_df = pd.read_csv('data/all_repos.csv')
            name_col = None
            for col in ['name', 'full_name', 'repo_name']:
                if col in global_df.columns:
                    name_col = col
                    break
            if name_col is not None:
                if 'is_active' in global_df.columns:
                    global_df['is_active'] = global_df['is_active'].astype(str).str.lower() == 'true'
                else:
                    global_df['is_active'] = True
                global_df.loc[global_df[name_col].isin(growth_analysis), 'is_active'] = False
                global_df.to_csv('data/all_repos.csv', index=False)
                print(f"已更新全局文件，标记 {len(growth_analysis)} 个项目为不活跃")
        # 更新各领域文件
        for domain_file in domain_files:
            domain_df = pd.read_csv(domain_file)
            name_col = None
            for col in ['name', 'full_name', 'repo_name']:
                if col in domain_df.columns:
                    name_col = col
                    break
            if name_col is None:
                continue
            if 'is_active' in domain_df.columns:
                domain_df['is_active'] = domain_df['is_active'].astype(str).str.lower() == 'true'
            else:
                domain_df['is_active'] = True
            domain_df.loc[domain_df[name_col].isin(growth_analysis), 'is_active'] = False
            domain_df.to_csv(domain_file, index=False)
        print("已同步更新各领域文件的活跃状态")

    print("analyzer 执行完成")

if __name__ == "__main__":
    main()