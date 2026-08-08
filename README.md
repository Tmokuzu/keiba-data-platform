# keiba-data-platform

中央競馬の複勝予測を扱う、ローカル完結のデータ基盤・学習・予測CLIです。
日常運用はこのリポジトリだけで完結します。予測やバックテストは利益を保証しません。

## 最初に読む場所

- [利用ガイド](docs/user/usage.md): セットアップから当日予測、検証までの手順
- [クイックスタート](docs/user/quickstart.md): 最初のDB作成と動作確認
- [設定](docs/user/configuration.md): `.env` と `config.yaml`
- [運用・トラブルシューティング](docs/user/operations.md): 障害時と日常更新
- [JV-Link Importer](jvlink_importer/README.md): WindowsでJRA-VAN Data Lab.から直接取り込む場合
- [中央競馬向け特徴量設計](docs/design/central_feature_design.md): 精度改善の設計と取込拡張の優先順位

## 設計

```text
CSV または WindowsのJV-Link
  -> raw_*                 取込データ。未確定レースを含めてよい
  -> sync-ended
  -> core tables           結果・払戻・全出走馬の結果がそろった確定レースだけ
  -> ai_race_entries       学習・バックテスト用の安定ビュー

当日の出走表・オッズ
  -> raw_* / temp/
  -> predict-today
  -> prediction_logs/      core DBには入れない
```

### 守るルール

- 対象券種は複勝のみです。
- core層には未確定データを保存しません。
- 5〜7頭立ては2着以内、8頭以上は3着以内を複勝的中とします。
- 校正と閾値選択は検証期間だけで行い、テスト期間は最終評価専用です。
- 過去に後から取得した市場オッズは学習に使いません。時刻付きオッズはレース前の
  `import-rt-odds` で取得したものだけを保存します。

## 最短手順

```bash
uv sync
cp .env.example .env
# .env にPostgreSQL接続情報を設定

uv run python main.py check-db
uv run python main.py init-db
```

確定済みデータをCSVから取り込む場合:

```bash
uv run python main.py import-csv
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
uv run python main.py train-all-models
```

当日予測:

```bash
uv run python main.py check-odds-snapshots --date 2026-06-06
uv run python main.py predict-today \
  --date 2026-06-06 \
  --today-csv data/today/entries_20260606.csv
```

詳しいCSV形式、出力先、検証順序は [利用ガイド](docs/user/usage.md) を参照してください。

## 主なコマンド

| 目的 | コマンド |
| --- | --- |
| DB接続確認 | `check-db` |
| スキーマ作成・更新 | `init-db` |
| raw層へCSV取込 | `import-csv` |
| 確定済みデータだけを同期 | `sync-ended` |
| 学習用ビュー更新 | `build-ai-views` |
| モデル一括学習 | `train-all-models` |
| アンサンブル予測 | `predict-ensemble` |
| 当日CSVの予測 | `predict-today --date ... --today-csv ...` |
| 締切前オッズ確認 | `check-odds-snapshots --date ...` |
| Walk-Forward検証 | `walk-forward-backtest` |
| セグメント分析 | `segmented-backtest-report` |
| 閾値最適化 | `optimize-thresholds` |

すべてのコマンドは次の形式で実行します。

```bash
uv run python main.py <command>
```

## 生成物とGit

`models/`、`data/processed/`、`temp/`、ログ、`.env`、
`jvlink_importer/appsettings.json` はローカル生成物または機密設定です。Gitには追加しません。

## 開発者向け

AI実装を変更する場合は [AGENTS.md](AGENTS.md) と
[docs/codex/context.md](docs/codex/context.md) を先に読んでください。
