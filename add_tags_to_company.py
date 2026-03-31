import pandas as pd
import os

TAG_MAPPING = {
    "long-context": ["long context", "1m context", "infinite context", "mamba", "long sequence"],
    "multimodal": ["multimodal", "vision", "image", "video", "audio", "speech"],
    "inference": ["inference", "vllm", "tensorrt", "quantization", "speculative", "fast"],
    "agent": ["agent", "autonomous", "tool use", "openclaw", "computer use"],
    "rag": ["rag", "retrieval", "knowledge base", "graphrag"]
}

def assign_tags(title, summary):
    # 处理缺失值，转为空字符串
    title = str(title) if pd.notna(title) else ""
    summary = str(summary) if pd.notna(summary) else ""
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
    # 确保 tags 列存在且为字符串类型
    if 'tags' not in df.columns:
        df['tags'] = ''
    else:
        df['tags'] = df['tags'].astype(str)

    # 对每条记录，如果 tags 为空或 NaN，则重新打标
    for idx, row in df.iterrows():
        if pd.isna(row['tags']) or row['tags'] == '':
            tags = assign_tags(row['title'], row.get('summary', ''))
            df.at[idx, 'tags'] = tags

    # 保存前确保 tags 列是字符串
    df['tags'] = df['tags'].astype(str)
    df.to_csv(csv_file, index=False)
    print("公司发布标签更新完成")

if __name__ == "__main__":
    main()