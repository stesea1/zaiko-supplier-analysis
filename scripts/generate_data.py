# -*- coding: utf-8 -*-
"""
サンプルデータ生成スクリプト
実務で使用していたERP(調達・在庫・物流モジュール)のテーブル構造を参考に、
在庫マスタと納品実績の2つのCSVを生成する。

使い方:
    python scripts/generate_data.py
出力:
    data/zaiko_master.csv   (在庫マスタ: 約100品目)
    data/nouhin_jisseki.csv (納品実績: 約600件)
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

# 再現性のため乱数を固定
random.seed(42)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------
# マスタ定義(実務のERPマスタをイメージ)
# ---------------------------------------------------------------

CATEGORIES = {
    "EL": "電気部品",
    "ME": "機械部品",
    "RM": "原材料",
    "PK": "包装資材",
    "CS": "消耗品",
}

SUPPLIERS = [
    ("S001", "東和電機株式会社"),
    ("S002", "大阪金属工業"),
    ("S003", "北村樹脂産業"),
    ("S004", "グローバルパーツ商事"),
    ("S005", "中央包装材料"),
    ("S006", "協立精密(海外仕入先A)"),
    ("S007", "華信電子(海外仕入先B)"),
    ("S008", "山田物産"),
]

# 仕入先ごとの「納期遅延しやすさ」(遅延日数の期待値)。
# 分析結果に差が出るように、わざと性格の違う仕入先を作っておく。
SUPPLIER_DELAY_PROFILE = {
    "S001": 0.3,   # ほぼ遅れない優良仕入先
    "S002": 1.0,
    "S003": 0.5,
    "S004": 3.5,   # よく遅れる仕入先
    "S005": 0.8,
    "S006": 2.5,   # 海外のため変動大
    "S007": 4.0,   # 海外のため変動大
    "S008": 1.5,
}


def generate_zaiko_master(n_items: int = 100) -> list[dict]:
    """在庫マスタ(品目マスタ+在庫数量)を生成する"""
    rows = []
    for i in range(1, n_items + 1):
        cat_code = random.choice(list(CATEGORIES.keys()))
        supplier_code, supplier_name = random.choice(SUPPLIERS)

        # 単価はカテゴリによって桁を変える(ABC分析で差が出るように)
        base_price = {
            "EL": random.uniform(50, 3000),
            "ME": random.uniform(100, 8000),
            "RM": random.uniform(20, 500),
            "PK": random.uniform(5, 100),
            "CS": random.uniform(10, 300),
        }[cat_code]

        safety_stock = random.choice([50, 100, 200, 300, 500])
        # 一部の品目はわざと安全在庫割れにしておく(欠品リスク検出の練習用)
        if random.random() < 0.15:
            stock_qty = int(safety_stock * random.uniform(0.2, 0.9))
        else:
            stock_qty = int(safety_stock * random.uniform(1.0, 4.0))

        rows.append({
            "品目コード": f"{cat_code}-{i:04d}",
            "品目名": f"{CATEGORIES[cat_code]}{i:03d}",
            "カテゴリ": CATEGORIES[cat_code],
            "主要仕入先コード": supplier_code,
            "主要仕入先名": supplier_name,
            "単価": round(base_price, 1),
            "在庫数量": stock_qty,
            "安全在庫": safety_stock,
        })
    return rows


def generate_nouhin_jisseki(zaiko_rows: list[dict], n_orders: int = 600) -> list[dict]:
    """納品実績(発注〜納品の履歴)を生成する"""
    rows = []
    start = date(2025, 7, 1)
    for i in range(1, n_orders + 1):
        item = random.choice(zaiko_rows)
        supplier_code = item["主要仕入先コード"]
        supplier_name = item["主要仕入先名"]

        order_date = start + timedelta(days=random.randint(0, 330))
        lead_time = random.randint(7, 30)
        due_date = order_date + timedelta(days=lead_time)

        # 仕入先プロファイルに応じて遅延を発生させる
        expected_delay = SUPPLIER_DELAY_PROFILE[supplier_code]
        delay = max(0, int(random.gauss(expected_delay, 2.0)))
        actual_date = due_date + timedelta(days=delay)

        qty = random.choice([100, 200, 300, 500, 1000])

        row = {
            "発注番号": f"PO-{i:05d}",
            "品目コード": item["品目コード"],
            "仕入先コード": supplier_code,
            "仕入先名": supplier_name,
            "発注日": order_date.isoformat(),
            "納期予定日": due_date.isoformat(),
            "実際納品日": actual_date.isoformat(),
            "発注数量": qty,
            "単価": item["単価"],
        }

        # --- わざと「汚いデータ」を混ぜる(データクレンジングの練習用) ---
        r = random.random()
        if r < 0.03:
            row["実際納品日"] = ""                       # 欠損値
        elif r < 0.05:
            d = date.fromisoformat(row["発注日"])
            row["発注日"] = d.strftime("%Y/%m/%d")        # 日付フォーマット不統一
        elif r < 0.07:
            row["仕入先名"] = row["仕入先名"] + " "        # 末尾に余計な空白

        rows.append(row)

        # 重複行も少し混ぜる
        if random.random() < 0.02:
            rows.append(dict(row))

    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"生成完了: {path} ({len(rows)}行)")


if __name__ == "__main__":
    zaiko = generate_zaiko_master()
    nouhin = generate_nouhin_jisseki(zaiko)
    write_csv(DATA_DIR / "zaiko_master.csv", zaiko)
    write_csv(DATA_DIR / "nouhin_jisseki.csv", nouhin)
