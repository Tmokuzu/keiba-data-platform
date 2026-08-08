# 利用ガイド

`keiba-data-platform` は、中央競馬の**複勝のみ**を対象にしたローカルのデータ基盤・予測CLIです。
予測やバックテストの結果は利益を保証しません。実運用前には、時系列検証と資金管理を必ず確認してください。

## 最初に一度だけ行うこと

プロジェクト直下で、Python環境とPostgreSQL接続を準備します。

```bash
uv sync
cp .env.example .env
```

`.env` にPostgreSQL接続情報を入力します。

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=keiba
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

接続とテーブル定義を確認します。

```bash
uv run python main.py check-db
uv run python main.py init-db
```

## 1. 確定済みデータを取り込む

JRA-VANから直接取り込む場合は、Windowsで `jvlink_importer/` を実行します。詳細は
[JV-Link Importer](../../jvlink_importer/README.md) を参照してください。取込先はraw層であり、
次の `sync-ended` 以降の手順はCSV取込の場合と共通です。

`data/raw/` に、少なくとも次のCSVを置きます。CSVヘッダーは `sql/001_create_raw_tables.sql` の列名に合わせます。

- `races.csv`
- `entries.csv`
- `results.csv`
- `payouts.csv`
- `odds.csv`（時刻付きオッズがある場合）

取り込みと確定済みデータの同期:

```bash
uv run python main.py import-csv
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
```

`import-csv` はraw層に保存します。`sync-ended` がcore層に送るのは、結果と払戻がそろった
確定レースだけです。当日の出走表・オッズをraw層に置いても、core層や学習データには入りません。

## 2. モデルを学習する

履歴データを取り込んだ後、複数モデルとアンサンブル校正器を作成します。

```bash
uv run python main.py train-all-models
```

作成される主なファイル:

- `models/lgbm_place_model.pkl`
- `models/catboost_place_model.pkl`
- `models/xgboost_place_model.pkl`
- `models/ensemble_place_calibrator.pkl`
- `data/processed/predictions_place.csv`

複勝ターゲットの定義や特徴量を変更した場合は、`build-ai-views` の後に必ず再学習してください。

## 3. 当日の予測を行う

### 3-1. 締切前オッズの確認

当日の `races.csv`、`entries.csv`、`odds.csv` をraw層に取り込んでから、カバレッジを確認します。

```bash
uv run python main.py import-csv
uv run python main.py check-odds-snapshots --date 2026-06-06
```

出力の `ready: true` は、発走時刻の設定分前までの複勝オッズが出走馬の95%以上にあることを示します。
この確認はraw層だけを読むため、当日データをcore層へ保存しません。

### 3-2. 当日CSVから予測する

予測用に、レース情報と出走馬情報を1行ずつ結合したCSVを用意します。最低限必要な列は
`race_id` と `horse_id` です。精度のため、次の列も含めてください。

```text
race_id,race_date,course,race_no,surface,distance,ground_condition,field_size,
horse_id,horse_name,horse_no,frame_no,jockey_id,trainer_id,horse_sex,
weight_carried,body_weight,body_weight_diff,odds_win,odds_place_min,
odds_place_max,popularity
```

`race_date` を省略すると `--date` の値、`field_size` を省略すると各レースの出走馬数を使います。

```bash
uv run python main.py predict-today \
  --date 2026-06-06 \
  --today-csv data/today/entries_20260606.csv
```

このコマンドは、確定済み履歴だけを参照して特徴量を作ります。当日CSVはcore DBには書き込まず、
以下に実行単位で保存します。

```text
temp/today_YYYYMMDD_<run-id>.parquet
data/processed/prediction_logs/YYYYMMDD_<run-id>/
  today_input.csv
  features.csv
  predictions.csv
  bets.csv
  metadata.json
```

`bets.csv` の `action=BUY` がSafe Agentの条件を満たした買い目です。`stake` は推奨購入額で、
`action=SKIP` は購入対象外です。

## 4. モデルを検証する

学習結果を採用する前に、次を順に確認します。

```bash
uv run python main.py model-compare
uv run python main.py walk-forward-backtest
uv run python main.py segmented-backtest-report
uv run python main.py optimize-thresholds
uv run python main.py ablation-test
uv run python main.py phase2-report
```

| コマンド | 目的 | 主な出力 |
| --- | --- | --- |
| `model-compare` | LightGBM・CatBoost・XGBoost・アンサンブルを比較 | `model_compare_summary.csv` |
| `walk-forward-backtest` | 年次で学習期間と評価期間をずらし、再現性を確認 | `walk_forward_summary.csv`、`walk_forward_detail.csv` |
| `segmented-backtest-report` | コース・距離・馬場・人気帯などの成績を確認 | `segmented_backtest_report.csv` |
| `optimize-thresholds` | 検証期間だけでSafe Agent閾値を選ぶ | `threshold_optimization_report.json` |
| `ablation-test` | 特徴量群を除外して依存度を確認 | `ablation_summary.csv` |
| `phase2-report` | 上記をまとめた判断用レポート | `phase2_report.json` |

ROIはすべて `払戻額 / 賭け金` です。1.0を超えると利益、1.0未満は損失を示します。
`optimize-thresholds` のテスト期間は、閾値選択には使いません。レポートを見て閾値を変えた場合は、
同じテスト結果を再利用せず、Walk-Forwardで再検証してください。

## 日常運用の流れ

```text
確定後: raw CSVを取り込む -> sync-ended -> build-ai-views -> 必要なら再学習
当日:   raw CSV/オッズを取り込む -> check-odds-snapshots -> predict-today
定期:   model-compare -> walk-forward-backtest -> 各種レポート
```

設定値の意味は [configuration.md](configuration.md)、障害時の確認は
[operations.md](operations.md) を参照してください。
