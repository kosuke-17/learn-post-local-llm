# Pokemon Trainer LLM - ポストトレーニング実践

既存の LLM（Qwen2.5-7B）に対して **ポストトレーニング（LoRA fine-tuning）** を行い、ポケモンSV の育成論に特化させるプロジェクト。

## ポストトレーニングとは

事前学習済みの汎用 LLM をベースに、特定ドメインのデータで追加学習（fine-tuning）を行うことで、専門的な知識や回答スタイルを獲得させる手法。ゼロからモデルを学習するのではなく、既に言語能力を持ったモデルの上に専門性を積み上げる。

本プロジェクトでは以下の流れでポストトレーニングを実践する:

1. **データセット作成** - ポケモン育成論の Q&A データを用意
2. **LoRA fine-tuning** - MLX を使ってベースモデルを追加学習
3. **デプロイ** - GGUF 変換 → Ollama に登録してローカルで推論

## 前提条件

- Apple Silicon Mac (32GB+)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/)

## セットアップ

```bash
# 依存パッケージのインストール
uv sync
```

## 手順

### STEP 1: データセット生成

50件の育成論データセットを用意済み。

```bash
wc -l train.jsonl valid.jsonl test.jsonl
# train: 40件, valid: 5件, test: 5件
```

### STEP 2: ベースモデルのテスト

fine-tune 前の回答品質を確認する。

```bash
# Qwen2.5-7B（日本語に強い、おすすめ）
uv run mlx_lm.generate --model mlx-community/Qwen2.5-7B-Instruct-4bit --prompt "ミミッキュを対戦用に育成したいんだけど、おすすめの型を教えて" --max-tokens 500
```

### STEP 3: LoRA fine-tune

```bash
uv run python -m mlx_lm.lora \
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --train \
  --data ./ \
  --iters 200 \
  --batch-size 4 \
  --lora-layers 16 \
  --learning-rate 1e-5 \
  --adapter-path ./adapters
```

### STEP 4: fine-tune 後のテスト

```bash
uv run python -m mlx_lm.generate \
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --adapter-path ./adapters \
  --prompt "ガブリアスの育成論を教えて" \
  --max-tokens 500
```

### STEP 5: モデルの fuse（アダプター統合）

```bash
uv run python -m mlx_lm.fuse \
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --adapter-path ./adapters \
  --save-path ./pokemon-trainer-model
```

### STEP 6: GGUF 変換

```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
pip install -r requirements.txt

python convert_hf_to_gguf.py ../pokemon-trainer-model \
  --outfile ../pokemon-trainer.gguf \
  --outtype q8_0

cd ..
```

### STEP 7: Ollama に登録

```bash
# Modelfile 作成
cat > pokemon.Modelfile << 'EOF'
FROM ./pokemon-trainer.gguf

SYSTEM あなたはポケモンSV（スカーレット・バイオレット）の対戦に精通したポケモントレーナーだ。育成論・パーティ構築・対戦の立ち回りについて的確なアドバイスを行う。

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
"""

PARAMETER stop "<|im_end|>"
EOF

# Ollama にモデル登録
ollama create pokemon-trainer -f pokemon.Modelfile

# テスト
ollama run pokemon-trainer "カイリューの育成論を教えて"
```

## ファイル構成

```
├── sample-data.jsonl       # 全データ（50件）
├── train.jsonl             # 学習データ（40件）
├── valid.jsonl             # 検証データ（5件）
├── test.jsonl              # テストデータ（5件）
├── generate-dataset.py     # データセット生成スクリプト（API使用）
├── check-quality.py        # データ品質チェック
├── evaluate.py             # モデル評価
├── pipeline.py             # 手順書（レガシー）
└── pyproject.toml          # プロジェクト設定
```
