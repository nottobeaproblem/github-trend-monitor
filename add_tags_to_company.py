"""为公司发布打标签"""
import pandas as pd
import os

# 标签映射规则
TAG_MAPPING = {
    "long-context": ["long context", "1m context", "infinite context", "mamba", "long sequence"],
    "multimodal": ["multimodal", "vision", "image", "video", "audio", "speech"],
    "inference": ["inference", "vllm", "tensorrt", "quantization", "speculative", "fast"],
    "agent": ["agent", "autonomous", "tool use", "openclaw", "computer use"],
    "rag": ["rag", "retrieval", "knowledge base", "graphrag"]
}

def assign_tags(title, summary):
    text = (title + " " + summary).lower()
    tags = []
    for tag, keywords in TAG_MAPPING.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return ",".join(tags)

def main():
    csv_file = "data/company_releases.csv"
    if not os.path.exists(csv_file):
        print("company_releases.csv 不存在，跳过")
        return

    df = pd.read_csv(csv_file)
    if 'tags' not in df.columns:
        df['tags'] = ''
    # 对每条记录，如果 tags 为空，则重新打标
    for idx, row in df.iterrows():
        if pd.isna(row['tags']) or row['tags'] == '':
            tags = assign_tags(row['title'], row.get('summary', ''))
            df.at[idx, 'tags'] = tags
    df.to_csv(csv_file, index=False)
    print("公司发布标签更新完成")

if __name__ == "__main__":
    main()