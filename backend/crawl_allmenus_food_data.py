"""
Import food records from the local CSV backup into the MySQL food table.

The project already ships with a curated CSV at data/chinese_food_caption.csv.
Keeping this script local-first makes the project runnable without network
access while preserving the original database schema.
"""

import argparse
import csv
import json
import os
import sys

import pymysql

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import DB_CONFIG, init_database


DEFAULT_CSV = os.path.join(BASE_DIR, "data", "chinese_food_caption.csv")
XIASHA_ENRICHMENT_JSON = os.path.join(BASE_DIR, "data", "xiasha_enrichment.json")


def to_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_food_key(text):
    return ''.join(str(text or '').strip().split()).replace('（', '(').replace('）', ')')


def load_source_url_map():
    mapping = {}
    if not os.path.exists(XIASHA_ENRICHMENT_JSON):
        return mapping

    with open(XIASHA_ENRICHMENT_JSON, 'r', encoding='utf-8') as file:
        records = json.load(file)

    for record in records:
        restaurant = str(record.get('restaurant') or '').strip()
        source_url = str(record.get('source_url') or '').strip()
        for item in record.get('items', []):
            item_name = str(item.get('name') or '').strip()
            if not item_name or not source_url:
                continue
            full_name = f'{item_name}（{restaurant}）' if restaurant else item_name
            mapping[normalize_food_key(full_name)] = source_url
    return mapping


def read_food_rows(csv_path, limit=0):
    source_url_map = load_source_url_map()
    rows = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            food_name = (row.get("food_name") or "").strip()
            if not food_name:
                continue
            rows.append(
                {
                    "food_name": food_name[:100],
                    "category": (row.get("category") or "").strip()[:50],
                    "price": to_float(row.get("price")),
                    "review": (row.get("review") or "").strip(),
                    "rating": to_float(row.get("rating")),
                    "original_taste": (row.get("original_taste") or "").strip()[:200],
                    "taste_reform_scheme": (row.get("taste_reform_scheme") or "").strip(),
                    "image_url": (row.get("image_url") or "").strip(),
                    "source_url": source_url_map.get(normalize_food_key(food_name), ""),
                }
            )
            if limit and len(rows) >= limit:
                break
    return rows


def clear_food_data(cursor):
    cursor.execute("DELETE FROM user_history")
    cursor.execute("DELETE FROM user_favorite")
    cursor.execute("DELETE FROM user_review")
    cursor.execute("DELETE FROM food")


def get_next_food_id(cursor):
    cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM food")
    return cursor.fetchone()[0]


def upsert_food(cursor, row):
    cursor.execute("SELECT id FROM food WHERE food_name = %s", (row["food_name"],))
    existing = cursor.fetchone()
    values = (
        row["category"],
        row["price"],
        row["review"],
        row["rating"],
        row["original_taste"],
        row["taste_reform_scheme"],
        row["image_url"],
        row["source_url"],
    )
    if existing:
        cursor.execute(
            """
            UPDATE food
            SET category = %s,
                price = %s,
                review = %s,
                rating = %s,
                original_taste = %s,
                taste_reform_scheme = %s,
                image_url = %s,
                source_url = %s
            WHERE id = %s
            """,
            values + (existing[0],),
        )
        return "updated"

    cursor.execute(
        """
        INSERT INTO food (
            id, food_name, category, price, review, rating,
            original_taste, taste_reform_scheme, image_url, source_url
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (get_next_food_id(cursor), row["food_name"]) + values,
    )
    return "inserted"


def import_csv(csv_path=DEFAULT_CSV, replace=False, limit=0):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

    init_database()
    rows = read_food_rows(csv_path, limit)
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    stats = {"inserted": 0, "updated": 0}

    try:
        if replace:
            clear_food_data(cursor)
        for row in rows:
            action = upsert_food(cursor, row)
            stats[action] += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    return stats, len(rows)


def main():
    parser = argparse.ArgumentParser(description="导入本地真实菜品 CSV 数据")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="CSV file path")
    parser.add_argument("--replace", action="store_true", help="clear old food/user relation records first")
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    args = parser.parse_args()

    stats, total = import_csv(args.csv, args.replace, args.limit)
    print(f"读取 {total} 条记录，新增 {stats['inserted']} 条，更新 {stats['updated']} 条。")


if __name__ == "__main__":
    main()
