#!/usr/bin/env python3
"""
データセット品質チェック＆フィルタリングスクリプト
生成されたデータの品質を検証し、問題のあるデータを除外する
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

# =====================================================
# 品質チェック基準
# =====================================================

# 回答に含まれるべきキーワード（育成論として最低限の情報）
REQUIRED_KEYWORDS_BUILD = ["努力値", "性格", "技構成", "持ち物"]
# いずれかが含まれていれば育成論として認識
REQUIRED_ANY = ["努力値", "性格", "テラスタイプ", "立ち回り", "種族値"]

# SVに存在しないポケモン（誤生成チェック用）
INVALID_POKEMON = [
    "メガリザードン",
    "メガガルーラ",
    "アッシュグレニンジャ",
    "ゲンシカイオーガ",
    "ゲンシグラードン",
    "Zワザ",
    "メガシンカ",
    "ダイマックス",
]

# 回答の最低文字数
MIN_ANSWER_LENGTH = 100
# 回答の最大文字数（異常に長い場合）
MAX_ANSWER_LENGTH = 5000


def check_record(record: dict, index: int) -> list[str]:
    """1レコードの品質チェック。問題があればエラーメッセージのリストを返す"""
    errors = []

    # 構造チェック
    if "messages" not in record:
        errors.append("'messages' キーがない")
        return errors

    messages = record["messages"]
    if len(messages) < 2:
        errors.append("user/assistant の2メッセージが必要")
        return errors

    user_msg = messages[0].get("content", "")
    assistant_msg = messages[1].get("content", "")

    # 空チェック
    if not user_msg.strip():
        errors.append("ユーザーメッセージが空")
    if not assistant_msg.strip():
        errors.append("アシスタント回答が空")
        return errors

    # 長さチェック
    if len(assistant_msg) < MIN_ANSWER_LENGTH:
        errors.append(
            f"回答が短すぎる ({len(assistant_msg)}文字 < {MIN_ANSWER_LENGTH})"
        )
    if len(assistant_msg) > MAX_ANSWER_LENGTH:
        errors.append(
            f"回答が長すぎる ({len(assistant_msg)}文字 > {MAX_ANSWER_LENGTH})"
        )

    # 育成論としての情報チェック（初心者向け質問は除外）
    is_beginner_q = any(
        kw in user_msg
        for kw in ["って何", "仕組み", "わからない", "初心者", "始めたい"]
    )
    if not is_beginner_q:
        has_any = any(kw in assistant_msg for kw in REQUIRED_ANY)
        if not has_any:
            errors.append("育成論の基本情報（努力値・性格等）が含まれていない")

    # 無効なポケモン/システムの言及チェック
    for invalid in INVALID_POKEMON:
        if invalid in assistant_msg:
            errors.append(f"SV非対応の要素が含まれている: '{invalid}'")

    # 努力値合計チェック（努力値が記載されている場合）
    ev_total = extract_ev_total(assistant_msg)
    if ev_total is not None and ev_total > 510:
        errors.append(f"努力値の合計が510を超えている ({ev_total})")

    # 言語チェック（英語が大半を占めていないか）
    ascii_ratio = sum(1 for c in assistant_msg if c.isascii()) / max(
        len(assistant_msg), 1
    )
    if ascii_ratio > 0.8:
        errors.append("回答の大部分が英語/ASCII（日本語回答が期待される）")

    return errors


def extract_ev_total(text: str) -> int | None:
    """テキストから努力値の合計を抽出（ブロック単位で検証）"""
    # "努力値:" の後に続く 1行内の H/A/B/C/D/S + 数値 を拾う
    ev_line_pattern = r"努力値[：:]?\s*([^\n]+)"
    lines = re.findall(ev_line_pattern, text)
    for line in lines:
        matches = re.findall(r"[HABCDS]\s*(\d+)", line)
        if matches:
            total = sum(int(m) for m in matches)
            if total > 510:
                return total
    return None


def analyze_dataset(filepath: str):
    """データセット全体の分析"""
    path = Path(filepath)
    if not path.exists():
        print(f"エラー: ファイルが見つかりません: {filepath}")
        sys.exit(1)

    records = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if line.strip():
                try:
                    records.append((i + 1, json.loads(line)))
                except json.JSONDecodeError:
                    print(f"  行 {i + 1}: JSONパースエラー")

    print(f"=== データセット品質チェック: {filepath} ===")
    print(f"総レコード数: {len(records)}")
    print()

    # 各レコードをチェック
    clean_records = []
    error_records = []
    error_types = Counter()

    for line_num, record in records:
        errors = check_record(record, line_num)
        if errors:
            error_records.append((line_num, record, errors))
            for e in errors:
                error_types[e.split("(")[0].strip()] += 1
        else:
            clean_records.append(record)

    # サマリー出力
    print(f"✅ 正常: {len(clean_records)} 件")
    print(f"❌ エラー: {len(error_records)} 件")
    print()

    if error_types:
        print("--- エラー内訳 ---")
        for error_type, count in error_types.most_common():
            print(f"  {error_type}: {count} 件")
        print()

    # エラー詳細（最大10件）
    if error_records:
        print("--- エラー詳細（最大10件）---")
        for line_num, record, errors in error_records[:10]:
            user_msg = record.get("messages", [{}])[0].get("content", "")[:50]
            print(f"  行 {line_num}: {user_msg}...")
            for e in errors:
                print(f"    → {e}")
        print()

    # カテゴリ分布
    categories = Counter()
    for _, record in records:
        cat = record.get("category", "unknown")
        categories[cat] += 1

    if any(cat != "unknown" for cat in categories):
        print("--- カテゴリ分布 ---")
        for cat, count in categories.most_common():
            bar = "█" * (count // 2)
            print(f"  {cat:20s}: {count:3d} {bar}")
        print()

    # 回答長の統計
    lengths = []
    for _, record in records:
        msgs = record.get("messages", [])
        if len(msgs) >= 2:
            lengths.append(len(msgs[1].get("content", "")))

    if lengths:
        print("--- 回答文字数 ---")
        print(f"  最小: {min(lengths)}")
        print(f"  最大: {max(lengths)}")
        print(f"  平均: {sum(lengths) // len(lengths)}")
        print(f"  中央値: {sorted(lengths)[len(lengths) // 2]}")
        print()

    return clean_records, error_records


def export_clean(clean_records: list[dict], output_path: str):
    """正常データのみを出力"""
    with open(output_path, "w", encoding="utf-8") as f:
        for record in clean_records:
            mlx_record = {"messages": record["messages"]}
            f.write(json.dumps(mlx_record, ensure_ascii=False) + "\n")
    print(f"クリーンデータを出力: {output_path} ({len(clean_records)} 件)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="データセット品質チェック")
    parser.add_argument("file", help="チェック対象の.jsonlファイル")
    parser.add_argument("--export-clean", help="正常データのみ出力するファイルパス")
    args = parser.parse_args()

    clean, errors = analyze_dataset(args.file)

    if args.export_clean and clean:
        export_clean(clean, args.export_clean)
