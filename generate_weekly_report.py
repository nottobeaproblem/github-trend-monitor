import os
import pandas as pd
import requests
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown

# ========== 配置 ==========
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")   # 新环境变量
OPENROUTER_MODEL = "qwen/qwen3.6-plus-preview:free"    # 免费模型
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# ========== 数据读取（不变）==========
def get_hot_projects(days=7, top_n=10):
    metrics_dir = "data/metrics"
    if not os.path.exists(metrics_dir):
        return pd.DataFrame()
    files = sorted(os.listdir(metrics_dir), reverse=True)
    if not files:
        return pd.DataFrame()
    latest = files[0]
    df = pd.read_csv(os.path.join(metrics_dir, latest))
    hot = df.nlargest(top_n, 'stars')[['name', 'stars', 'domain']]
    return hot

def get_company_releases(days=7):
    csv_file = "data/company_releases.csv"
    if not os.path.exists(csv_file):
        return pd.DataFrame()
    df = pd.read_csv(csv_file)
    cutoff = datetime.now() - timedelta(days=days)
    df['publish_date'] = pd.to_datetime(df['publish_date'])
    recent = df[df['publish_date'] >= cutoff]
    return recent

def get_arxiv_papers(days=7):
    csv_file = "data/arxiv_papers.csv"
    if not os.path.exists(csv_file):
        return pd.DataFrame()
    df = pd.read_csv(csv_file)
    cutoff = datetime.now() - timedelta(days=days)
    df['published'] = pd.to_datetime(df['published'])
    recent = df[df['published'] >= cutoff]
    return recent

# ========== 调用 OpenRouter (Qwen 3.6 Plus) ==========
def call_llm(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
        "temperature": 0.7
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        print(f"OpenRouter 响应状态码: {response.status_code}")
        if response.status_code != 200:
            print(f"错误详情: {response.text}")
            return None
        result = response.json()
        # 标准 OpenAI 格式返回
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"调用 OpenRouter 失败: {e}")
        return None

# ========== 生成报告（提示词不变）==========
def generate_html_report(github_data, company_data, arxiv_data):
    github_str = "\n".join([f"- **{row['name']}**: {row['stars']} stars ({row['domain']})" for _, row in github_data.iterrows()])
    company_str = "\n".join([f"- **{row['company']}**: {row['title']} ({row['publish_date'].strftime('%Y-%m-%d')}) - {str(row['summary'])[:100]}..." for _, row in company_data.iterrows()])
    arxiv_str = "\n".join([f"- **{row['title']}** - {row['authors']} - {row['summary'][:150]}..." for _, row in arxiv_data.iterrows()])

    prompt = f"""
你是一位顶尖的 AI 行业分析师。请基于以下数据，生成一份本周 AI 技术趋势周报。

**GitHub 热点项目（本周 Star 增长最快）**：
{github_str if github_str else "无"}

**大厂模型/技术发布（本周）**：
{company_str if company_str else "无"}

**最新 arXiv 论文（本周）**：
{arxiv_str if arxiv_str else "无"}

请按以下结构输出（使用中文，800-1200 字）：
1. 总体趋势：本周最值得关注的 2-3 个技术方向，及其热度变化。
2. 大厂战略对比：至少两家头部厂商的发布重点，推测其战略意图。
3. 技术难点与解决方案：指出一个热门技术面临的挑战，并列举 GitHub 项目或论文中的解决思路。
4. 适用场景建议：哪个方向适合产品化落地？哪个仍处早期？
5. 学界 vs 业界：本周是否有论文被快速采纳？举例说明。

要求：每条分析必须引用具体数据（项目名、厂商名、论文标题）。
"""
    result = call_llm(prompt)
    if not result:
        return "<h1>AI 分析生成失败</h1><p>请检查 OpenRouter API Key 和网络连接。</p>"

    # 将 Markdown 转换为 HTML
    md_content = markdown.markdown(result, extensions=['extra'])

    # 构建最终 HTML（使用漂亮的样式）
    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 技术趋势周报 - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            background: linear-gradient(135deg, #f5f7fa 0%, #e9edf2 100%);
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
            padding: 40px 20px;
            color: #1e2a3a;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 32px;
            box-shadow: 0 20px 35px -10px rgba(0,0,0,0.15);
            overflow: hidden;
        }}
        .header {{
            ackground: linear-gradient(135deg, #C4A4A4 0%, #C4A4A4 100%);
            color: white;
            padding: 40px 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.4rem;
            font-weight: 600;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }}
        .header .date {{
            font-size: 1rem;
            opacity: 0.85;
            border-top: 1px solid rgba(255,255,255,0.2);
            display: inline-block;
            padding-top: 12px;
            margin-top: 12px;
        }}
        .content {{
            padding: 40px 45px;
            line-height: 1.65;
        }}
        .content h1, .content h2, .content h3, .content h4 {{
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
            font-weight: 600;
            color: #0b2b40;
        }}
        .content h2 {{
            border-bottom: 3px solid #1a4a6f;
            padding-bottom: 0.5rem;
        }}
        .content p {{
            margin-bottom: 1rem;
        }}
        .content ul, .content ol {{
            margin: 0.75rem 0 1rem 1.8rem;
        }}
        .content li {{
            margin-bottom: 0.4rem;
        }}
        .content code {{
            background: #f0f2f5;
            padding: 0.2rem 0.4rem;
            border-radius: 6px;
            font-family: 'SF Mono', monospace;
            font-size: 0.9em;
        }}
        .content blockquote {{
            border-left: 4px solid #1a4a6f;
            background: #f8fafc;
            padding: 0.8rem 1.2rem;
            margin: 1rem 0;
            border-radius: 12px;
            color: #2c3e50;
        }}
        .footer {{
            background: #f8fafc;
            padding: 20px 40px;
            text-align: center;
            font-size: 0.8rem;
            color: #5a6e7c;
            border-top: 1px solid #e2e8f0;
        }}
        @media (max-width: 700px) {{
            .content {{
                padding: 25px 20px;
            }}
            .header h1 {{
                font-size: 1.8rem;
            }}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>📈 AI 技术趋势周报</h1>
        <div class="date">生成时间：{datetime.now().strftime('%Y年%m月%d日')}</div>
    </div>
    <div class="content">
        {md_content}
    </div>
    <div class="footer">
        🤖 本报告由 AI 自动生成 | 数据来源：GitHub Trending & 大厂发布 & arXiv
    </div>
</div>
</body>
</html>
    """
    return html

# ========== 发送邮件（不变）==========
def send_email(html_content):
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("邮箱未配置，跳过发送")
        return
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"AI 技术趋势周报 - {datetime.now().strftime('%Y-%m-%d')}"
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_USER
    part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(part)
    try:
        server = smtplib.SMTP('smtp.qq.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, EMAIL_USER, msg.as_string())
        server.quit()
        print("邮件发送成功")
    except Exception as e:
        print(f"邮件发送失败: {e}")

def main():
    print("开始生成 AI 周报...")
    github_data = get_hot_projects(top_n=10)
    company_data = get_company_releases()
    arxiv_data = get_arxiv_papers()

    if github_data.empty and company_data.empty and arxiv_data.empty:
        print("无数据，跳过报告生成")
        return

    html = generate_html_report(github_data, company_data, arxiv_data)
    if html:
        with open("weekly_report.html", "w", encoding="utf-8") as f:
            f.write(html)
        # 如果不想发送邮件，注释掉下面一行
        send_email(html)

if __name__ == "__main__":
    main()