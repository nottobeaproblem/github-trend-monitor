import pandas as pd
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

def generate_html_report():
    """生成HTML格式的趋势报告"""
    # 检查必要数据是否存在
    if not os.path.exists('data/all_repos.csv'):
        return "<h1>错误：数据文件不存在，请先运行爬虫和分析器</h1>"

    # 读取最新指标数据
    metrics_dir = 'data/metrics'
    if not os.path.exists(metrics_dir):
        return "<h1>错误：指标目录不存在</h1>"

    metrics_files = sorted(os.listdir(metrics_dir), reverse=True)
    if not metrics_files:
        return "<h1>暂无指标数据</h1>"

    # 最新一天的数据
    latest_file = metrics_files[0]
    today_df = pd.read_csv(os.path.join(metrics_dir, latest_file))
    # 按 Star 数排序，取前 20
    top_stars = today_df.nlargest(20, 'stars')[['name', 'stars']]

    # 如果有至少两天的数据，计算增长最快
    growth_html = "<p>暂无增长数据（需要至少两天数据）</p>"
    if len(metrics_files) >= 2:
        yesterday_file = metrics_files[1]
        yesterday_df = pd.read_csv(os.path.join(metrics_dir, yesterday_file))
        merged = pd.merge(today_df, yesterday_df, on='name', suffixes=('_today', '_yesterday'))
        merged['daily_growth'] = merged['stars_today'] - merged['stars_yesterday']
        top_growth = merged.nlargest(10, 'daily_growth')[['name', 'stars_today', 'daily_growth']]
        growth_html = top_growth.to_html(index=False, escape=False)

    # 统计各领域项目数（如果 domains 字段有数据）
    domains_count = ""
    all_repos = pd.read_csv('data/all_repos.csv')
    if 'domains' in all_repos.columns and all_repos['domains'].notna().any():
        domain_stats = all_repos['domains'].value_counts().reset_index()
        domain_stats.columns = ['领域', '项目数']
        domains_count = domain_stats.to_html(index=False, escape=False)

    # 组装HTML
    html = f"""
    <html>
    <head>
        <title>GitHub 趋势日报 - {datetime.now().strftime('%Y-%m-%d')}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h1>GitHub 技术趋势日报</h1>
        <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>今日 Star 总数 Top 20</h2>
        {top_stars.to_html(index=False, escape=False)}

        <h2>今日 Star 增长最快 Top 10</h2>
        {growth_html}

        <h2>各领域项目统计</h2>
        {domains_count if domains_count else "<p>暂无领域统计数据</p>"}
    </body>
    </html>
    """
    return html

def send_email(html_content):
    """发送邮件"""
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = sender  # 默认发送给自己

    if not sender or not password:
        print("错误：未设置 EMAIL_USER 或 EMAIL_PASSWORD 环境变量")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"GitHub Trend Report - {datetime.now().strftime('%Y-%m-%d')}"
    msg['From'] = sender
    msg['To'] = receiver

    part = MIMEText(html_content, 'html')
    msg.attach(part)

    try:
        # 使用 QQ 邮箱 SMTP 服务器（可根据需要修改）
        server = smtplib.SMTP('smtp.qq.com', 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        print("邮件发送成功")
    except Exception as e:
        print(f"邮件发送失败: {e}")

def main():
    report_html = generate_html_report()
    send_email(report_html)

if __name__ == "__main__":
    main()