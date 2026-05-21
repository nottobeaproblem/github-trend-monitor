# GitHub Trend Monitor

## AI 趋势周报 

[![GitHub Actions](https://github.com/nottobeaproblem/github-trend-monitor/actions/workflows/daily_scraper.yml/badge.svg)](https://github.com/nottobeaproblem/github-trend-monitor/actions)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)

自动追踪 GitHub 热点项目 + 大厂模型发布 + arXiv 论文，每周生成 AI 行业洞察报告，让你用最少的时间掌握技术风向。

---

## 项目背景

作为 AI 产品经理 / 技术决策者 / 求职者，你是否也有这些困扰？

- 每天刷 GitHub Trending、Twitter、公众号 → 信息碎片化，真假难辨
- 自己分析数据 → 耗时费力，且不知道为什么热
- 现有分析工具 → 收费高、功能冗余，缺少轻量级免费方案
- 需要面试/汇报时 → 找不到系统性的数据支撑

**GitHub Trend Monitor** 为你自动完成数据采集、指标计算、趋势洞察，每周将高质量报告推送到你的邮箱。

---

## 核心功能

| 模块 | 说明 |
|------|------|
| **每日 GitHub 趋势爬取** | 按 AI Agent / RAG / 多模态 / 长文本 / 推理优化等 5 大领域，增量爬取新仓库 |
| **每日 Star 数更新** | 使用 GraphQL 批量查询，高效获取活跃项目最新 Star 数 |
| **智能淘汰机制** | 基于“连续无增长天数”（分级阈值）自动标记冷门项目，控制活跃项目数量 |
| **大厂发布日历** | 跟踪 OpenAI、Google、DeepSeek、智谱等 8+ 厂商的模型/技术发布，支持在线日历查看 |
| **arXiv 论文 RSS** | 自动抓取 cs.AI/cs.LG/cs.CL/cs.CV 方向最新论文 |
| **AI 周报生成** | 调用大模型（GLM/Gemini/Qwen）自动生成结构化周报，包含趋势、战略、技术难点、场景建议 |
| **邮件推送** | 每周一上午 9:00（北京时间）发送精美 HTML 报告 |
| **在线日历** | 部署于 GitHub Pages，支持按厂商/类型筛选，点击条目查看详情 |

---

## 技术架构

```text
GitHub API (REST + GraphQL)  →  Scraper (增量爬取)  →  CSV 存储
                                      ↓
arXiv RSS / 厂商 RSS         →  Company Crawler  →  CSV 存储
                                      ↓
                              Analyzer (Star 更新 + 淘汰)
                                      ↓
                              AI Analyzer (LLM 生成周报)
                                      ↓
                              Email + GitHub Pages
