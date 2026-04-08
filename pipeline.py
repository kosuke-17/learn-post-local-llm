#!/usr/bin/env python3
"""
ポケモントレーナーモデル: fine-tune → GGUF変換 → Ollama登録 パイプライン
Mac M5 + MLX + mlx-lm 用
"""

# =====================================================
# このファイルはコマンド集・手順書です
# 各ステップをターミナルで実行してください
# =====================================================

INSTRUCTIONS = """
========================================
ポケモントレーナーモデル 構築手順
========================================

■ 前提条件
  - Mac M5 (32GB)
  - Python 3.10+
  - Ollama インストール済み

========================================
STEP 0: 環境構築
========================================

# Python仮想環境を作成
python3 -m venv ~/pokemon-llm-env
source ~/pokemon-llm-env/bin/activate

# 必要パッケージをインストール
pip install mlx-lm anthropic

========================================
STEP 1: データセット生成
========================================

# APIキーを設定
export ANTHROPIC_API_KEY='your-key-here'

# データ生成（200件、約10〜15分）
python generate_dataset.py -n 200 -o ./dataset

# 確認
wc -l dataset/*.jsonl
# → train.jsonl: ~160件, valid.jsonl: ~20件, test.jsonl: ~20件

# 中身を確認
head -1 dataset/train.jsonl | python3 -m json.tool

========================================
STEP 2: ベースモデルの選択とテスト
========================================

# 32GBメモリなら 7B〜8B がおすすめ
# まずベースモデルをテスト

# 選択肢1: Llama 3.2 3B (軽量・高速、実験向き)
python -m mlx_lm.generate \\
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \\
  --prompt "ミミッキュを対戦用に育成したいんだけど、おすすめの型を教えて" \\
  --max-tokens 500

# 選択肢2: Qwen 2.5 7B (日本語に強い、本命)
python -m mlx_lm.generate \\
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \\
  --prompt "ミミッキュを対戦用に育成したいんだけど、おすすめの型を教えて" \\
  --max-tokens 500

# 選択肢3: Llama 3.1 8B (バランス型)
python -m mlx_lm.generate \\
  --model mlx-community/Meta-Llama-3.1-8B-Instruct-4bit \\
  --prompt "ミミッキュを対戦用に育成したいんだけど、おすすめの型を教えて" \\
  --max-tokens 500

========================================
STEP 3: LoRA fine-tune
========================================

# Qwen2.5-7B でfine-tune（おすすめ）
python -m mlx_lm.lora \\
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \\
  --train \\
  --data ./dataset \\
  --iters 200 \\
  --batch-size 4 \\
  --lora-layers 16 \\
  --learning-rate 1e-5 \\
  --adapter-path ./adapters

# 学習完了後、アダプター付きでテスト
python -m mlx_lm.generate \\
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \\
  --adapter-path ./adapters \\
  --prompt "ガブリアスの育成論を教えて" \\
  --max-tokens 500

========================================
STEP 4: モデルのfuse（アダプター統合）
========================================

# LoRAアダプターをベースモデルに統合
python -m mlx_lm.fuse \\
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \\
  --adapter-path ./adapters \\
  --save-path ./pokemon-trainer-model

========================================
STEP 5: GGUF変換
========================================

# llama.cpp をクローン（GGUF変換ツール）
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
pip install -r requirements.txt

# HuggingFace形式 → GGUF変換
python convert_hf_to_gguf.py ../pokemon-trainer-model \\
  --outfile ../pokemon-trainer.gguf \\
  --outtype q8_0

cd ..

========================================
STEP 6: Ollama に登録
========================================

# Modelfile を作成（下記の内容で pokemon.Modelfile を保存）
cat > pokemon.Modelfile << 'EOF'
FROM ./pokemon-trainer.gguf

SYSTEM あなたはポケモンSV（スカーレット・バイオレット）の対戦に精通したポケモントレーナーだ。育成論・パーティ構築・対戦の立ち回りについて的確なアドバイスを行う。性格・特性・努力値・技構成・テラスタイプを含む具体的な育成プランを提案する。

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

TEMPLATE \"\"\"{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
\"\"\"

PARAMETER stop "<|im_end|>"
EOF

# Ollamaでモデルを作成
ollama create pokemon-trainer -f pokemon.Modelfile

# テスト！
ollama run pokemon-trainer "カイリューの育成論を教えて"

========================================
STEP 7: 評価・改善
========================================

# test.jsonl の質問でモデルを評価
# → 回答の質が低い場合:
#   1. データセットを増やす（300〜500件）
#   2. イテレーション数を増やす（--iters 500）
#   3. 低品質データを手動で除外・修正

========================================
"""

if __name__ == "__main__":
    print(INSTRUCTIONS)
