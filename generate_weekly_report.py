"""生成报告并发送邮件"""
import os
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ========== 配置 ==========
GLM_API_KEY = os.getenv("GLM_API_KEY")          # 你的 GLM API Key
GLM_MODEL = "glm-4"                              # 或 "glm-4-flash"
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# ========== 数据读取 ==========
def get_hot_projects(days=7, top_n=10):
    """获取最近 top_n 个热门项目"""
    metrics_dir = "data/metrics"
    files = sorted(os.listdir(metrics_dir), reverse=True)
    if not files:
        return []
    latest = files[0]
    df = pd.read_csv(os.path.join(metrics_dir, latest))
    hot = df.nlargest(top_n, 'stars')[['name', 'stars', 'domain']]
    return hot

def get_company_releases(days=7):
    """获取最近一周的公司发布"""
    csv_file = "data/company_releases.csv"
    if not os.path.exists(csv_file):
        return pd.DataFrame()
    df = pd.read_csv(csv_file)
    cutoff = datetime.now() - timedelta(days=days)
    df['publish_date'] = pd.to_datetime(df['publish_date'])
    recent = df[df['publish_date'] >= cutoff]
    return recent

def get_arxiv_papers(days=7):
    """获取最近一周的论文"""
    csv_file = "data/arxiv_papers.csv"
    if not os.path.exists(csv_file):
        return pd.DataFrame()
    df = pd.read_csv(csv_file)
    cutoff = datetime.now() - timedelta(days=days)
    df['published'] = pd.to_datetime(df['published'])
    recent = df[df['published'] >= cutoff]
    return recent

# ========== 调用 GLM ==========
def call_glm(prompt):
    """调用 GLM API 生成内容"""
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {GLM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
        "temperature": 0.7
    }
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        print(f"GLM 调用失败: {response.status_code} {response.text}")
        return None

# ========== 生成报告 ==========
def generate_html_report(github_data, company_data, arxiv_data):
    # 构建提示词
    github_str = "\n".join([f"- {row['name']}: {row['stars']} stars ({row['domain']})" for _, row in github_data.iterrows()])
    company_str = "\n".join([f"- {row['company']}: {row['title']} ({row['publish_date'].strftime('%Y-%m-%d')}) - {row['summary'][:100]}..." for _, row in company_data.iterrows()])
    arxiv_str = "\n".join([f"- {row['title']} - {row['authors']} - {row['summary'][:150]}..." for _, row in arxiv_data.iterrows()])

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
    result = call_glm(prompt)
    if not result:
        return "<h1>AI 分析生成失败</h1>"

    # 包装成 HTML
    html = f"""
    <html>
    <head><meta charset="UTF-8"><title>AI 周报 - {datetime.now().strftime('%Y-%m-%d')}</title></head>
    <body>
    <h1>AI 技术趋势周报</h1>
    <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <div style="white-space: pre-wrap; font-family: Arial, sans-serif;">{result}</div>
    </body>
    </html>
    """
    return html

# ========== 发送邮件 ==========
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

# ========== 主函数 ==========
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
        # 可选：保存到文件供查看
        with open("weekly_report.html", "w", encoding="utf-8") as f:
            f.write(html)
        send_email(html)

if __name__ == "__main__":
    main()