# コマンドリファレンス

README.md で使用している各コマンドの詳細な解説。

---

## uv sync

```bash
uv sync
```

`pyproject.toml` に定義された Python 依存パッケージをインストールする。npm の `npm install` に相当。uv は Rust 製の高速パッケージマネージャで、pip + venv の代替。

- 仮想環境（`.venv/`）が存在しなければ自動作成する
- ロックファイル（`uv.lock`）に基づいて再現可能なインストールを行う

---

## wc -l

```bash
wc -l train.jsonl valid.jsonl test.jsonl
```

各ファイルの行数をカウントする Unix コマンド。JSONL は1行1レコードなので、行数 = データ件数。

| オプション | 意味 |
|-----------|------|
| `-l` | 行数のみ表示（word count ではなく line count） |

---

## mlx_lm.generate

```bash
uv run mlx_lm.generate \
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --prompt "ミミッキュを対戦用に育成したいんだけど、おすすめの型を教えて" \
  --max-tokens 500
```

MLX 上でモデルにテキストを生成させるコマンド。

| オプション | 説明 |
|-----------|------|
| `--model` | 使用するモデル。Hugging Face のリポジトリ名を指定すると自動ダウンロードされる |
| `--prompt` | モデルへの入力テキスト |
| `--max-tokens` | 生成する最大トークン数。大きいほど長い回答が得られるが、時間もかかる |
| `--adapter-path` | LoRA アダプターのパス。指定するとfine-tune後のモデルとして動作する（STEP 4で使用） |

`uv run` は uv が管理する仮想環境内でコマンドを実行するプレフィックス。

---

## mlx_lm.lora

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

LoRA fine-tuning を実行するコマンド。ベースモデルにアダプターを追加学習させる。

| オプション | 説明 |
|-----------|------|
| `--model` | ベースモデルの指定 |
| `--train` | 学習モードで実行（これがないと評価のみ） |
| `--data` | データセットのディレクトリ。`train.jsonl`, `valid.jsonl`, `test.jsonl` を含むパスを指定 |
| `--iters` | 学習イテレーション（繰り返し）回数。多すぎると過学習、少なすぎると学習不足 |
| `--batch-size` | 1イテレーションで処理するデータ数。大きいほど学習が安定するがメモリを消費する |
| `--lora-layers` | アダプターを挿入する層数。多いほど表現力が上がるが、学習コストも増加 |
| `--learning-rate` | 学習率。小さいほど元のモデルの能力を壊しにくいが、学習が遅い。`1e-5` = 0.00001 |
| `--adapter-path` | 学習済みアダプターの保存先ディレクトリ |

`python -m mlx_lm.lora` は Python モジュールとして実行する形式。`mlx_lm.generate` と書き方が違うが、どちらも mlx-lm パッケージのコマンド。

---

## mlx_lm.fuse

```bash
uv run python -m mlx_lm.fuse \
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --adapter-path ./adapters \
  --save-path ./pokemon-trainer-model
```

ベースモデルと LoRA アダプターを1つのモデルに統合（fuse）するコマンド。

| オプション | 説明 |
|-----------|------|
| `--model` | ベースモデル |
| `--adapter-path` | 統合する LoRA アダプターのパス |
| `--save-path` | 統合後のモデルの保存先 |

fuse 前は「ベースモデル + アダプター」の2つが必要だが、fuse 後は1つのモデルとして扱える。GGUF 変換にはこの統合済みモデルが必要。

---

## convert_hf_to_gguf.py

```bash
python convert_hf_to_gguf.py ../pokemon-trainer-model \
  --outfile ../pokemon-trainer.gguf \
  --outtype q8_0
```

llama.cpp に含まれる変換スクリプト。Hugging Face 形式（safetensors）のモデルを GGUF 形式に変換する。

| 引数/オプション | 説明 |
|---------------|------|
| 第1引数 | 変換元モデルのディレクトリ（fuse で作成したもの） |
| `--outfile` | 出力ファイルのパス |
| `--outtype` | 量子化タイプ。`q8_0` は8bit量子化で品質とサイズのバランスが良い |

**量子化タイプの選択肢:**

| タイプ | 説明 |
|-------|------|
| `f16` | 非量子化（16bit）。最高品質だがサイズ大 |
| `q8_0` | 8bit量子化。品質の低下が少なくサイズ半分 |
| `q4_0` | 4bit量子化。サイズ最小だが品質が落ちる |

---

## ollama create

```bash
ollama create pokemon-trainer -f pokemon.Modelfile
```

GGUF モデルと Modelfile から Ollama にモデルを登録するコマンド。Docker の `docker build` に相当する。

| 引数/オプション | 説明 |
|---------------|------|
| 第1引数 | 登録するモデル名（任意の名前） |
| `-f` | Modelfile のパス |

---

## ollama run

```bash
ollama run pokemon-trainer "カイリューの育成論を教えて"
```

登録済みモデルで推論を実行する。引数なしで実行すると対話モードになる。

| 引数 | 説明 |
|------|------|
| 第1引数 | モデル名（`ollama create` で登録した名前） |
| 第2引数（任意） | プロンプト。省略すると対話モードで起動 |

---

## Modelfile の各ディレクティブ

```
FROM ./pokemon-trainer.gguf
SYSTEM あなたはポケモントレーナーだ...
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
TEMPLATE """..."""
PARAMETER stop "<|im_end|>"
```

| ディレクティブ | 説明 |
|--------------|------|
| `FROM` | ベースとなるモデルファイル（GGUF）またはモデル名 |
| `SYSTEM` | システムプロンプト。モデルの役割や振る舞いを定義 |
| `PARAMETER temperature` | 生成のランダム性。0に近いほど決定的、1に近いほど多様な回答 |
| `PARAMETER top_p` | 上位何%の確率のトークンから選ぶか。0.9 = 上位90% |
| `PARAMETER num_ctx` | コンテキストウィンドウのサイズ（トークン数） |
| `TEMPLATE` | プロンプトのフォーマット。モデルが学習時に使った形式に合わせる必要がある |
| `PARAMETER stop` | 生成停止トークン。この文字列が出たら生成を止める |
