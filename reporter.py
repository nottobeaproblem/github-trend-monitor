import pandas as pd
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import jieba
import io
import base64

# 设置中文字体路径（Windows 常见字体）
FONT_PATHS = [
    'C:/Windows/Fonts/msyh.ttc',      # 微软雅黑
    'C:/Windows/Fonts/simhei.ttf',    # 黑体
    'C:/Windows/Fonts/simsun.ttc',    # 宋体
    'C:/Windows/Fonts/SimHei.ttf',
    None
]

def find_valid_font():
    for path in FONT_PATHS:
        if path and os.path.exists(path):
            return path
    return None

def generate_wordcloud(texts, domain_name):
    if not texts:
        return ""
    text = ' '.join(str(t) for t in texts if pd.notna(t))
    if not text.strip():
        return ""
    words = ' '.join(jieba.cut(text))
    font_path = find_valid_font()
    try:
        wordcloud = WordCloud(width=600, height=300,
                              background_color='white',
                              font_path=font_path,
                              collocations=False).generate(words)
        plt.figure(figsize=(6,3))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode()
        plt.close()
        return f'<img src="data:image/png;base64,{img_base64}" style="max-width:100%;" />'
    except Exception as e:
        print(f"生成词云失败: {e}")
        return ""

def generate_html_report():
    metrics_dir = 'data/metrics'
    if not os.path.exists(metrics_dir):
        return "<h1>错误：指标目录不存在</h1>"

    metrics_files = sorted(os.listdir(metrics_dir), reverse=True)
    if not metrics_files:
        return "<h1>暂无指标数据</h1>"

    today_file = metrics_files[0]
    today_df = pd.read_csv(os.path.join(metrics_dir, today_file), encoding='utf-8-sig')

    yesterday_df = None
    if len(metrics_files) >= 2:
        yesterday_df = pd.read_csv(os.path.join(metrics_dir, metrics_files[1]), encoding='utf-8-sig')

    top_stars_global = today_df.nlargest(20, 'stars')[['name', 'stars']]
    global_table = top_stars_global.to_html(index=False, escape=False)

    domains = today_df['domain'].unique()
    domain_sections = ""
    for domain in domains:
        domain_today = today_df[today_df['domain'] == domain]

        top_stars = domain_today.nlargest(10, 'stars')[['name', 'stars']]
        top_stars_table = top_stars.to_html(index=False, escape=False)

        # 领域内日增长 Top 5（增加兼容性判断）
        growth_table = ""
        if yesterday_df is not None:
            if 'domain' in yesterday_df.columns:
                domain_yest = yesterday_df[yesterday_df['domain'] == domain]
                if not domain_yest.empty:
                    merged = pd.merge(domain_today, domain_yest, on='name', suffixes=('_today', '_yest'))
                    merged['growth'] = merged['stars_today'] - merged['stars_yest']
                    top_growth = merged.nlargest(5, 'growth')[['name', 'stars_today', 'growth']]
                    growth_table = top_growth.to_html(index=False, escape=False)
                else:
                    growth_table = "<p>昨日无此领域数据</p>"
            else:
                growth_table = "<p>昨日指标文件缺少领域信息，无法计算领域增长</p>"
        else:
            growth_table = "<p>暂无增长数据（需要至少两天数据）</p>"

        domain_file = os.path.join('data', f"{domain.replace(' ', '_')}.csv")
        wordcloud_img = ""
        if os.path.exists(domain_file):
            domain_df = pd.read_csv(domain_file, encoding='utf-8-sig')
            active_names = domain_today['name'].tolist()
            domain_active = domain_df[domain_df['name'].isin(active_names)]
            texts = domain_active['name'].tolist() + domain_active['description'].dropna().tolist()
            wordcloud_img = generate_wordcloud(texts, domain)
        else:
            wordcloud_img = "<p>领域文件缺失</p>"

        domain_sections += f"""
        <h2>{domain}</h2>
        {wordcloud_img}
        <h3>Star 总数 Top 10</h3>
        {top_stars_table}
        <h3>日增长 Top 5</h3>
        {growth_table}
        """

    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>GitHub 趋势日报 - {datetime.now().strftime('%Y-%m-%d')}</title>
        <style>
            body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>GitHub 技术趋势日报</h1>
        <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>全局 Star 总数 Top 20</h2>
        {global_table}

        {domain_sections}
    </body>
    </html>
    """
    return html

def send_email(html_content):
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = sender

    if not sender or not password:
        print("错误：未设置 EMAIL_USER 或 EMAIL_PASSWORD 环境变量")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"GitHub Trend Report - {datetime.now().strftime('%Y-%m-%d')}"
    msg['From'] = sender
    msg['To'] = receiver

    part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(part)

    try:
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
    # 调试：保存到文件
    # with open("test_report.html", "w", encoding="utf-8") as f:
    #     f.write(report_html)
    # print("报告已保存到 test_report.html，请检查。")

    send_email(report_html)

if __name__ == "__main__":
    main()