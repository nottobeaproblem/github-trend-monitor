import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os

DATA_DIR = "data"
RELEASES_CSV = os.path.join(DATA_DIR, "company_releases.csv")
DAYS_BACK = 7

def get_recent_releases():
    if not os.path.exists(RELEASES_CSV):
        return pd.DataFrame()
    df = pd.read_csv(RELEASES_CSV)
    cutoff = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    df['publish_date'] = pd.to_datetime(df['publish_date'])
    recent = df[df['publish_date'] >= cutoff]
    return recent

def generate_highlights(recent):
    # 简单规则：选取 type='模型' 且 open_source='是' 的作为亮点
    highlights = recent[recent['type'].str.contains('模型', na=False) & (recent['open_source'] == '是')]
    if len(highlights) > 3:
        highlights = highlights.head(3)
    return highlights

def generate_html(recent):
    if recent.empty:
        return "<h1>本周无新发布</h1>"

    highlights = generate_highlights(recent)
    highlights_html = ""
    for _, row in highlights.iterrows():
        highlights_html += f"""
        <div style="margin-bottom: 20px;">
            <h3>{row['company']} - {row['title']}</h3>
            <p><strong>日期：</strong>{row['publish_date'].strftime('%Y-%m-%d')}</p>
            <p><strong>简介：</strong>{row['summary']}</p>
            <p><a href="{row['url']}">阅读更多</a></p>
        </div>
        """

    # 按厂商分组生成表格
    grouped = recent.groupby('company')
    company_html = ""
    for company, group in grouped:
        table_rows = ""
        for _, row in group.iterrows():
            table_rows += f"""
            <tr>
                <td>{row['publish_date'].strftime('%Y-%m-%d')}</td>
                <td>{row['title']}</td>
                <td>{row['type']}</td>
                <td>{row['open_source']}</td>
                <td><a href="{row['url']}">链接</a></td>
            </tr>
            """
        company_html += f"""
        <h2>{company}</h2>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr><th>日期</th><th>标题</th><th>类型</th><th>开源</th><th>链接</th></tr>
            {table_rows}
        </table>
        """

    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>AI 大厂发布周报 - {datetime.now().strftime('%Y-%m-%d')}</title>
        <style>
            body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>AI 大厂发布周报</h1>
        <p>统计时间：{datetime.now().strftime('%Y-%m-%d')} 过去 {DAYS_BACK} 天</p>

        <h2>本周亮点</h2>
        {highlights_html or "<p>无特别亮点</p>"}

        <h2>全部发布</h2>
        {company_html}
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
    msg['Subject'] = f"AI 大厂发布周报 - {datetime.now().strftime('%Y-%m-%d')}"
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
        print("周报邮件发送成功")
    except Exception as e:
        print(f"邮件发送失败: {e}")

def main():
    recent = get_recent_releases()
    if recent.empty:
        print("本周无新发布，跳过发送")
        return
    html = generate_html(recent)
    send_email(html)

if __name__ == "__main__":
    main()