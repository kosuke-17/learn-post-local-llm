#!/usr/bin/env python3
"""
ポケモン育成論データセット生成スクリプト
Claude APIを使って初代（第1世代）ポケモンの育成論データを生成する
"""

import argparse
import json
import os
import random
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("anthropic パッケージが必要です: pip install anthropic")
    exit(1)

# =====================================================
# 初代（第1世代）ポケモンリスト（対戦でよく使われるポケモン）
# =====================================================
POKEMON_LIST = [
    # 御三家
    "フシギバナ",
    "リザードン",
    "カメックス",
    # ノーマル
    "ケンタロス",
    "カビゴン",
    "ポリゴン",
    "カイリキー",
    "ラッキー",
    "プクリン",
    "ペルシアン",
    # 電気
    "サンダース",
    "ピカチュウ",
    "エレブー",
    "マルマイン",
    # 水
    "スターミー",
    "ラプラス",
    "ギャラドス",
    "シャワーズ",
    "ニョロボン",
    "ヤドラン",
    "パルシェン",
    "キングラー",
    # 炎
    "ウインディ",
    "ブースター",
    "キュウコン",
    # 草
    "ナッシー",
    "ウツボット",
    "ラフレシア",
    "モンジャラ",
    # エスパー
    "フーディン",
    "スリーパー",
    "ルージュラ",
    "ナッシー",
    # ゴースト
    "ゲンガー",
    # 毒
    "ニドキング",
    "ニドクイン",
    "ベトベトン",
    "ゴルバット",
    # 地面・岩
    "ダグトリオ",
    "サイドン",
    "ゴローニャ",
    "イワーク",
    "ガラガラ",
    # 氷
    "ラプラス",
    "ルージュラ",
    "フリーザー",
    # 飛行
    "プテラ",
    "ピジョット",
    # ドラゴン
    "カイリュー",
    # 虫
    "カイロス",
    "ストライク",
    # 伝説
    "サンダー",
    "ファイヤー",
    "フリーザー",
    "ミュウツー",
]
# 重複を除去
POKEMON_LIST = sorted(set(POKEMON_LIST))

# =====================================================
# 質問テンプレート
# =====================================================
QUESTION_TEMPLATES = {
    "single_build": [
        "{pokemon}を対戦用に育成したい。おすすめの型を教えて。",
        "{pokemon}の育成論を教えてください。努力値・技構成を含めて。",
        "{pokemon}を使いたいんだけど、どう育てればいい？",
        "{pokemon}のおすすめの技構成は？",
        "{pokemon}で一番強い型って何？",
        "{pokemon}の努力値配分で迷ってる。おすすめは？",
        "ニンテンドウカップで{pokemon}を使いたい。育成方針を教えて。",
    ],
    "role_based": [
        "物理受けとして優秀なポケモンのおすすめ育成論を教えて。",
        "特殊アタッカーでおすすめのポケモンと育成論は？",
        "まひ撒き要員に向いてるポケモンを教えて。",
        "眠り要員としておすすめのポケモンと型は？",
        "先発で出すのにおすすめのポケモンと育成は？",
        "特殊受けにおすすめのポケモンと育成論を教えて。",
        "交代先として優秀なポケモンの育成を教えて。",
        "リフレクター要員のおすすめと育成論を教えて。",
        "影分身を使った戦術でおすすめのポケモンと育成は？",
    ],
    "counter": [
        "{pokemon}が重いんだけど、対策できるポケモンと育成を教えて。",
        "{pokemon}に勝てるポケモンを教えて。具体的な育成論も。",
        "相手の{pokemon}に困ってる。どう対策すればいい？",
        "{pokemon}を受けられるポケモンのおすすめ育成論は？",
    ],
    "party_building": [
        "{pokemon}を軸にしたパーティ構築を考えたい。相性のいいポケモンは？",
        "{pokemon}と{pokemon2}を両方使いたい。残りのパーティメンバーのおすすめは？",
        "初心者向けのパーティ構築を教えて。主要メンバーの育成論も含めて。",
        "初代の対戦環境でおすすめのパーティ構築は？",
        "吹雪パーティを組みたい。おすすめのメンバーと育成論を教えて。",
        "眠り+身代わり戦術のパーティを組みたい。メンバーと育成論は？",
    ],
    "beginner": [
        "初代のステータス経験値（努力値）って何？どう振ればいいの？",
        "初代の個体値って何？対戦で重要？",
        "対戦用ポケモンの育成手順を最初から教えて。",
        "初代の急所の仕組みがわからない。素早さとの関係を教えて。",
        "初代の特殊ステータスの仕組みを教えて。",
        "素早さの仕組みがわからない。調整ってどうやるの？",
        "初代で対戦を始めたい。最初に育てるべきポケモンは？",
        "タイプ相性を活かした育成のコツを教えて。",
    ],
    "comparison": [
        "{pokemon}と{pokemon2}、どっちを育てるべき？違いや強みを比較して。",
        "物理アタッカーなら{pokemon}と{pokemon2}どっちがおすすめ？",
    ],
    "gen1_mechanics": [
        "初代の凍り状態って自然回復しないの？どう活用する？",
        "{pokemon}の急所率ってどのくらい？切りつけるや葉っぱカッターとの相性は？",
        "初代の吹雪が強いって聞いたけど、なぜ？どう活用する？",
        "初代の破壊光線って倒したら反動なしって本当？活用法を教えて。",
    ],
}

# =====================================================
# Claude API呼び出し用のシステムプロンプト
# =====================================================
SYSTEM_PROMPT = """あなたはポケモン赤・緑（第1世代）の対戦に精通したポケモントレーナーです。
初代ポケモン（赤・緑・青・ピカチュウ版）の仕様に基づいた育成論を提供してください。

回答のガイドライン:
- ステータス経験値（努力値に相当）の配分、技構成を必ず含める
- 初代の個体値は0〜15、努力値は各ステータス最大65535
- なぜその技構成にするのか理由を簡潔に説明する
- 想定される立ち回りや役割を説明する
- 初代特有の仕様（急所率が素早さ依存、特殊が攻防一体、凍りが自然回復しない等）を考慮する
- 複数の型がある場合は代表的なものを1〜2つ紹介する
- 敬語は使わず、フレンドリーだが的確なトーンで回答する

注意:
- 初代に存在しないポケモンや技は使わない（第1世代の151匹と初代の技のみ）
- 初代の対戦環境（ニンテンドウカップ等）を意識した実用的なアドバイスをする
- 初心者にも分かりやすい説明を心がける
"""


def build_question(template_category: str, pokemon_list: list[str]) -> str:
    """テンプレートからランダムに質問を生成"""
    templates = QUESTION_TEMPLATES[template_category]
    template = random.choice(templates)

    pokemon = random.choice(pokemon_list)
    pokemon2 = random.choice([p for p in pokemon_list if p != pokemon])

    return template.format(pokemon=pokemon, pokemon2=pokemon2)


def generate_all_questions(target_count: int = 200) -> list[dict]:
    """全カテゴリからバランスよく質問を生成"""
    questions = []

    # カテゴリごとの比率
    category_weights = {
        "single_build": 0.35,  # メインの育成論
        "role_based": 0.15,
        "counter": 0.12,
        "party_building": 0.12,
        "beginner": 0.10,
        "comparison": 0.06,
        "gen1_mechanics": 0.10,
    }

    for category, weight in category_weights.items():
        count = max(1, int(target_count * weight))
        for _ in range(count):
            q = build_question(category, POKEMON_LIST)
            questions.append({"category": category, "question": q})

    random.shuffle(questions)
    return questions[:target_count]


def call_claude_api(client: anthropic.Anthropic, question: str) -> str | None:
    """Claude APIで回答を生成"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
        )
        return response.content[0].text
    except anthropic.RateLimitError:
        print("  → レート制限。30秒待機...")
        time.sleep(30)
        return call_claude_api(client, question)
    except Exception as e:
        print(f"  → エラー: {e}")
        return None


def generate_dataset(
    target_count: int = 200,
    output_dir: str = "./dataset",
    delay: float = 1.0,
):
    """データセット全体を生成"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY 環境変数を設定してください")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        return

    client = anthropic.Anthropic(api_key=api_key)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    raw_file = output_path / "raw_data.jsonl"
    questions = generate_all_questions(target_count)

    print("=== ポケモン育成論データセット生成 ===")
    print(f"生成予定: {len(questions)} 件")
    print(f"出力先: {raw_file}")
    print()

    generated = 0
    # 既存データがあればスキップ（途中再開対応）
    existing = 0
    if raw_file.exists():
        with open(raw_file) as f:
            existing = sum(1 for _ in f)
        print(f"既存データ: {existing} 件 (スキップして続行)")

    with open(raw_file, "a", encoding="utf-8") as f:
        for i, item in enumerate(questions):
            if i < existing:
                continue

            question = item["question"]
            category = item["category"]
            print(f"[{i + 1}/{len(questions)}] ({category}) {question[:50]}...")

            answer = call_claude_api(client, question)
            if answer is None:
                print("  → スキップ")
                continue

            record = {
                "messages": [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer},
                ],
                "category": category,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            generated += 1

            if delay > 0:
                time.sleep(delay)

    print(f"\n完了！ 生成: {generated} 件")
    print(f"保存先: {raw_file}")

    # train/valid/test に分割
    split_dataset(raw_file, output_path)


def split_dataset(
    raw_file: Path,
    output_dir: Path,
    train_ratio: float = 0.8,
    valid_ratio: float = 0.1,
):
    """データセットを train/valid/test に分割（mlx-lm 形式）"""
    with open(raw_file, encoding="utf-8") as f:
        data = [json.loads(line) for line in f if line.strip()]

    random.shuffle(data)
    n = len(data)
    train_end = int(n * train_ratio)
    valid_end = int(n * (train_ratio + valid_ratio))

    splits = {
        "train": data[:train_end],
        "valid": data[train_end:valid_end],
        "test": data[valid_end:],
    }

    for split_name, split_data in splits.items():
        out_file = output_dir / f"{split_name}.jsonl"
        with open(out_file, "w", encoding="utf-8") as f:
            for record in split_data:
                # mlx-lm 形式: messages キーのみ
                mlx_record = {"messages": record["messages"]}
                f.write(json.dumps(mlx_record, ensure_ascii=False) + "\n")
        print(f"  {split_name}: {len(split_data)} 件 → {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ポケモン育成論データセット生成")
    parser.add_argument("-n", "--count", type=int, default=200, help="生成するデータ数")
    parser.add_argument("-o", "--output", default="./dataset", help="出力ディレクトリ")
    parser.add_argument(
        "-d", "--delay", type=float, default=1.0, help="API呼び出し間隔(秒)"
    )
    args = parser.parse_args()

    generate_dataset(
        target_count=args.count,
        output_dir=args.output,
        delay=args.delay,
    )
