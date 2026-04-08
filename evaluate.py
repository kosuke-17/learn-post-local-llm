#!/usr/bin/env python3
"""
fine-tune後のモデル評価スクリプト
ベースモデル vs fine-tuneモデルの比較評価を行う
"""

import json
import subprocess

# =====================================================
# 評価用の質問セット
# =====================================================
EVAL_QUESTIONS = [
    # 基本的な育成論
    "ミミッキュの対戦用育成論を教えて。",
    "サーフゴーのおすすめの型は？",
    # 役割ベース
    "物理受けでおすすめのポケモンと育成論を教えて。",
    # 対策
    "ハバタクカミの対策を教えて。",
    # パーティ構築
    "カイリュー軸のパーティ構築を教えて。",
    # テラスタル
    "ガブリアスのおすすめテラスタイプは？",
    # 初心者
    "努力値の振り方の基本を教えて。",
    # 比較
    "パオジアンとセグレイブ、どっちが強い？",
]


def eval_with_mlx(
    model: str,
    adapter_path: str | None,
    questions: list[str],
    max_tokens: int = 500,
) -> list[dict]:
    """mlx-lm で推論して結果を取得"""
    results = []

    for i, q in enumerate(questions):
        print(f"  [{i + 1}/{len(questions)}] {q[:40]}...")

        cmd = [
            "python",
            "-m",
            "mlx_lm.generate",
            "--model",
            model,
            "--prompt",
            q,
            "--max-tokens",
            str(max_tokens),
        ]
        if adapter_path:
            cmd.extend(["--adapter-path", adapter_path])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            output = result.stdout.strip()
            results.append(
                {
                    "question": q,
                    "answer": output,
                    "error": None,
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "question": q,
                    "answer": "",
                    "error": "タイムアウト",
                }
            )
        except Exception as e:
            results.append(
                {
                    "question": q,
                    "answer": "",
                    "error": str(e),
                }
            )

    return results


def eval_with_ollama(
    model: str,
    questions: list[str],
) -> list[dict]:
    """Ollama で推論して結果を取得"""
    results = []

    for i, q in enumerate(questions):
        print(f"  [{i + 1}/{len(questions)}] {q[:40]}...")

        cmd = ["ollama", "run", model, q]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            output = result.stdout.strip()
            results.append(
                {
                    "question": q,
                    "answer": output,
                    "error": None,
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "question": q,
                    "answer": "",
                    "error": "タイムアウト",
                }
            )
        except Exception as e:
            results.append(
                {
                    "question": q,
                    "answer": "",
                    "error": str(e),
                }
            )

    return results


def score_answer(answer: str) -> dict:
    """回答の自動スコアリング（簡易版）"""
    scores = {}

    # 情報の網羅性（育成論に必要な情報が含まれているか）
    info_keywords = {
        "性格": [
            "性格",
            "ようき",
            "いじっぱり",
            "おくびょう",
            "ひかえめ",
            "ずぶとい",
            "わんぱく",
            "しんちょう",
            "おだやか",
            "なまいき",
        ],
        "努力値": [
            "努力値",
            "H252",
            "A252",
            "B252",
            "C252",
            "D252",
            "S252",
            "H4",
            "A4",
            "B4",
            "C4",
            "D4",
            "S4",
        ],
        "技構成": ["技構成", "技:", "わざ"],
        "持ち物": [
            "持ち物",
            "いのちのたま",
            "こだわりスカーフ",
            "こだわりハチマキ",
            "こだわりメガネ",
            "きあいのタスキ",
            "たべのこし",
            "とつげきチョッキ",
            "ラムのみ",
            "オボンのみ",
        ],
        "テラスタイプ": ["テラスタイプ", "テラスタル"],
        "立ち回り": ["立ち回り", "運用", "使い方", "動き方"],
    }

    info_count = 0
    for category, keywords in info_keywords.items():
        if any(kw in answer for kw in keywords):
            info_count += 1
    scores["情報網羅性"] = round(info_count / len(info_keywords) * 10, 1)

    # 回答の長さ（適切な長さか）
    length = len(answer)
    if length < 50:
        scores["回答量"] = 1
    elif length < 200:
        scores["回答量"] = 4
    elif length < 800:
        scores["回答量"] = 8
    elif length < 1500:
        scores["回答量"] = 10
    else:
        scores["回答量"] = 7  # 長すぎ

    # 日本語率
    jp_chars = sum(1 for c in answer if "\u3040" <= c <= "\u9fff")
    jp_ratio = jp_chars / max(len(answer), 1)
    scores["日本語品質"] = round(min(jp_ratio * 15, 10), 1)

    # 合計
    scores["合計"] = round(sum(scores.values()), 1)

    return scores


def compare_results(base_results: list[dict], ft_results: list[dict]):
    """ベースモデル vs fine-tuneモデルの比較"""
    print("\n" + "=" * 60)
    print("評価結果比較")
    print("=" * 60)

    base_total = 0
    ft_total = 0

    for base, ft in zip(base_results, ft_results):
        q = base["question"]
        print(f"\n--- Q: {q} ---")

        if base["error"]:
            print(f"  ベース: エラー ({base['error']})")
            base_score = {"合計": 0}
        else:
            base_score = score_answer(base["answer"])
            print(f"  ベース: {base_score}")

        if ft["error"]:
            print(f"  fine-tune: エラー ({ft['error']})")
            ft_score = {"合計": 0}
        else:
            ft_score = score_answer(ft["answer"])
            print(f"  fine-tune: {ft_score}")

        base_total += base_score["合計"]
        ft_total += ft_score["合計"]

        # 改善度
        diff = ft_score["合計"] - base_score["合計"]
        if diff > 0:
            print(f"  → fine-tuneが +{diff:.1f} 改善 ✅")
        elif diff < 0:
            print(f"  → fine-tuneが {diff:.1f} 悪化 ⚠️")
        else:
            print("  → 同等")

    n = len(base_results)
    print(f"\n{'=' * 60}")
    print("総合スコア:")
    print(f"  ベースモデル: {base_total:.1f} (平均 {base_total / n:.1f})")
    print(f"  fine-tuneモデル: {ft_total:.1f} (平均 {ft_total / n:.1f})")
    improvement = ((ft_total - base_total) / max(base_total, 1)) * 100
    print(f"  改善率: {improvement:+.1f}%")
    print(f"{'=' * 60}")


def save_results(results: list[dict], filepath: str):
    """結果をJSONで保存"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"結果を保存: {filepath}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ポケモントレーナーモデル評価")
    parser.add_argument(
        "--mode", choices=["mlx", "ollama"], default="ollama", help="推論エンジン"
    )
    parser.add_argument("--base-model", required=True, help="ベースモデル名")
    parser.add_argument(
        "--ft-model", default=None, help="fine-tuneモデル名（Ollama用）"
    )
    parser.add_argument("--adapter-path", default=None, help="アダプターパス（MLX用）")
    parser.add_argument("--output", default="./eval_results.json", help="結果出力先")
    args = parser.parse_args()

    print("=== ベースモデル評価 ===")
    if args.mode == "ollama":
        base_results = eval_with_ollama(args.base_model, EVAL_QUESTIONS)
    else:
        base_results = eval_with_mlx(args.base_model, None, EVAL_QUESTIONS)

    ft_results = None
    if args.ft_model or args.adapter_path:
        print("\n=== fine-tuneモデル評価 ===")
        if args.mode == "ollama" and args.ft_model:
            ft_results = eval_with_ollama(args.ft_model, EVAL_QUESTIONS)
        elif args.adapter_path:
            ft_results = eval_with_mlx(
                args.base_model, args.adapter_path, EVAL_QUESTIONS
            )

    if ft_results:
        compare_results(base_results, ft_results)

    # 保存
    output = {
        "base_model": args.base_model,
        "base_results": base_results,
    }
    if ft_results:
        output["ft_model"] = args.ft_model or "adapter"
        output["ft_results"] = ft_results
    save_results(output, args.output)
