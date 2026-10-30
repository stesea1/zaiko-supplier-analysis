# -*- coding: utf-8 -*-
"""
在庫・仕入先データ分析ツール(メインスクリプト)

調達・在庫データ(CSV)を読み込み、以下の分析を行って
Excelレポートとグラフを自動生成する。

  1. データクレンジング(重複削除・空白除去・日付型変換・欠損除外)
  2. 在庫分析(在庫金額算出・カテゴリ別集計・安全在庫割れ抽出・ABC分析)
  3. 仕入先パフォーマンス分析(納期遵守率・平均遅延日数の集計)
  4. レポート出力(Excel 2シート + グラフ2枚)

実行方法:
    python src/analysis.py
"""

from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")          # 画面に表示せずファイル出力する設定
import matplotlib.pyplot as plt
import japanize_matplotlib     # グラフの日本語文字化け対策

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------
# STEP 1: データ読み込みとクレンジング
# ---------------------------------------------------------------
def load_and_clean() -> tuple[pd.DataFrame, pd.DataFrame]:
    zaiko = pd.read_csv(DATA_DIR / "zaiko_master.csv")
    nouhin = pd.read_csv(DATA_DIR / "nouhin_jisseki.csv")

    print(f"クレンジング前: {len(nouhin)}行")

    # 1. 重複行を削除
    nouhin = nouhin.drop_duplicates()
    print(f"重複削除後: {len(nouhin)}行")

    # 2. 仕入先名の余計な空白を除去
    nouhin["仕入先名"] = nouhin["仕入先名"].str.strip()

    # 3. 日付3列を文字列 → datetime型に変換
    date_cols = ["発注日", "納期予定日", "実際納品日"]
    for col in date_cols:
        nouhin[col] = pd.to_datetime(nouhin[col], format="mixed")

    # 4. 実際納品日が欠損している行(未納品)を分析対象から除外
    missing = nouhin["実際納品日"].isna().sum()
    print(f"納品日欠損: {missing}行 → 除外")
    nouhin = nouhin.dropna(subset=["実際納品日"])

    print(f"クレンジング後: {len(nouhin)}行")
    return zaiko, nouhin


# ---------------------------------------------------------------
# STEP 2: 在庫分析
# ---------------------------------------------------------------
def analyze_zaiko(zaiko: pd.DataFrame) -> pd.DataFrame:
    # 1. 在庫金額列を追加(単価 × 在庫数量)
    zaiko["在庫金額"] = zaiko["単価"] * zaiko["在庫数量"]

    # 2. カテゴリ別の在庫金額合計
    cat_summary = zaiko.groupby("カテゴリ")["在庫金額"].sum().sort_values(ascending=False)
    print("\n=== カテゴリ別在庫金額 ===")
    print(cat_summary.round(0))

    # 3. 安全在庫割れの品目を抽出
    shortage = zaiko[zaiko["在庫数量"] < zaiko["安全在庫"]]
    print(f"\n=== 安全在庫割れ: {len(shortage)}品目 ===")
    print(shortage[["品目コード", "品目名", "在庫数量", "安全在庫"]].to_string(index=False))

    # 4. ABC分析
    zaiko = zaiko.sort_values("在庫金額", ascending=False)
    zaiko["累計構成比"] = zaiko["在庫金額"].cumsum() / zaiko["在庫金額"].sum()
    zaiko["ABC区分"] = pd.cut(
        zaiko["累計構成比"],
        bins=[0, 0.7, 0.9, 1.0],
        labels=["A", "B", "C"],
    )
    print("\n=== ABC区分別の品目数 ===")
    print(zaiko["ABC区分"].value_counts().sort_index())

    return zaiko


# ---------------------------------------------------------------
# STEP 3: 仕入先パフォーマンス分析
# ---------------------------------------------------------------
def analyze_suppliers(nouhin: pd.DataFrame) -> pd.DataFrame:
    # 1. 遅延日数列を追加(実際納品日 − 納期予定日)
    nouhin["遅延日数"] = (nouhin["実際納品日"] - nouhin["納期予定日"]).dt.days

    # 2. 納期遵守フラグ(遅延0日以下 = 遵守)
    nouhin["納期遵守"] = nouhin["遅延日数"] <= 0

    # 3. 仕入先ごとに集計
    result = nouhin.groupby("仕入先名").agg(
        発注件数=("発注番号", "count"),
        納期遵守率=("納期遵守", "mean"),
        平均遅延日数=("遅延日数", "mean"),
    )
    result["納期遵守率"] = (result["納期遵守率"] * 100).round(1)
    result["平均遅延日数"] = result["平均遅延日数"].round(1)

    # 4. 遵守率の低い順に並べる(問題仕入先が上に来る)
    result = result.sort_values("納期遵守率")

    print("\n=== 仕入先別パフォーマンス ===")
    print(result.to_string())

    return result


# ---------------------------------------------------------------
# STEP 4: レポート出力
# ---------------------------------------------------------------
def export_report(zaiko_result: pd.DataFrame, supplier_result: pd.DataFrame) -> None:
    # 1. Excelレポート出力(シート2枚)
    report_path = OUTPUT_DIR / "report.xlsx"
    with pd.ExcelWriter(report_path) as writer:
        zaiko_result.to_excel(writer, sheet_name="在庫分析", index=False)
        supplier_result.to_excel(writer, sheet_name="仕入先評価")
    print(f"\nExcelレポート出力: {report_path}")

    # 2. グラフ1: 在庫金額 上位10品目
    top10 = zaiko_result.head(10)
    plt.figure(figsize=(10, 5))
    plt.bar(top10["品目コード"], top10["在庫金額"])
    plt.title("在庫金額 上位10品目")
    plt.ylabel("在庫金額(円)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "zaiko_top10.png", dpi=120)
    plt.close()

    # 3. グラフ2: 仕入先別 納期遵守率
    plt.figure(figsize=(10, 5))
    plt.bar(supplier_result.index, supplier_result["納期遵守率"])
    plt.title("仕入先別 納期遵守率(%)")
    plt.ylabel("納期遵守率(%)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "supplier_rate.png", dpi=120)
    plt.close()

    print(f"グラフ出力: {OUTPUT_DIR}/zaiko_top10.png, supplier_rate.png")
if __name__ == "__main__":
    zaiko, nouhin = load_and_clean()
    print(f"在庫マスタ: {len(zaiko)}行 / 納品実績: {len(nouhin)}行 を読み込みました")

    zaiko_result = analyze_zaiko(zaiko)
    supplier_result = analyze_suppliers(nouhin)
    export_report(zaiko_result, supplier_result)
