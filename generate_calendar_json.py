import pandas as pd
import json
import os

DATA_DIR = "data"
CSV_FILE = os.path.join(DATA_DIR, "company_releases.csv")
JSON_FILE = os.path.join(DATA_DIR, "calendar_data.json")

def csv_to_json():
    if not os.path.exists(CSV_FILE):
        print(f"错误：找不到 {CSV_FILE}，请先运行爬虫。")
        return

    df = pd.read_csv(CSV_FILE)
    # 将日期列转换为字符串（便于JSON序列化）
    df['publish_date'] = pd.to_datetime(df['publish_date']).dt.strftime('%Y-%m-%d')
    # 处理NaN值
    df = df.fillna('')
    # 转换为字典列表
    records = df.to_dict(orient='records')

    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"成功导出 {len(records)} 条记录到 {JSON_FILE}")

if __name__ == "__main__":
    csv_to_json()