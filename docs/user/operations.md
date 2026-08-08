# 運用・トラブルシューティング

## 確定後のデータ更新

1. `data/raw/` にCSVを置きます。
2. 次を実行します。

```bash
uv run python main.py import-csv
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
```

3. `logs/data_quality_report.json` を確認します。

当日の未確定データを予測に使う場合は、`sync-ended` は不要です。詳細は [利用ガイド](usage.md) の
「当日の予測を行う」を参照してください。

## raw層のCSV

- `races.csv`
- `entries.csv`
- `results.csv`
- `payouts.csv`
- `odds.csv`

CSVヘッダーは `sql/001_create_raw_tables.sql` の定義に合わせます。

WindowsのJV-Linkから直接取り込む場合は、同梱の `jvlink_importer/` を使います。取込ツールも
raw層へ書き込むため、Python CLIでは続けて `sync-ended` を実行してください。

## 生成ファイル

次のファイルはローカル成果物であり、Gitへコミットしません。

- `data/processed/`
- `models/`
- `data/postgres/`
- `logs/*.log`
- `logs/data_quality_report.json`

## よくある問題

`check-db` が失敗する場合は、`.env` の接続先、PostgreSQLの起動状態、DB名を確認します。管理された
実行環境ではローカルPostgreSQLのソケットやTCPポートが制限されることがあります。この場合、
アプリの設定を変えずに、ローカル端末またはDBアクセスを許可した実行環境で同じコマンドを再実行します。

```bash
uv run python main.py check-db
```

このプロジェクトでは、サンドボックス外の実行で `check-db` が成功することを確認しています。
再現性のため、実際に利用する接続情報は `.env` に明示してください。

`init-db` または `build-ai-views` が失敗する場合は、既存ビューを参照している接続が残っていないかを
確認してから再実行します。

`predict-today` がモデルファイル不足で失敗する場合は、確定済み履歴を取り込んだ後に
`uv run python main.py train-all-models` を実行します。

`check-odds-snapshots` が `ready: false` の場合は、`odds.csv` の `snapshot_time`、券種
（`place` または `複勝`）、馬番に対応する `combination`、発走時刻を確認します。

## モデル採用前の確認

Before relying on a model output:

- `validate` が成功している。
- `model-compare` と `walk-forward-backtest` が実データの年次範囲で完了している。
- `segmented-backtest-report` で大きな負けゾーンを確認した。
- `phase2-report` が存在する。
- 校正・閾値・購入額のルールをテスト期間で調整していない。

バックテストとモデル指標は将来の利益を保証しません。
