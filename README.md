# keiba-data-platform

中央競馬AI用のデータ基盤プロジェクトです。

このリポジトリはJRA-VAN Data Lab. 由来の終了済み・確定済みレースデータをPostgreSQLに保存し、AI予測プロジェクトが読みやすい `ai` 層ビューとして公開します。Phase1 MVP以降は、複勝に限定したモデル学習、予測、Safe Agent、バックテスト、検証レポートも同じCLIから実行できます。

AI側、たとえば `keiba-ai-engine` は学習・バックテストでは原則として `ai_race_entries` と `ai_horse_history` だけを読みます。raw/core層の構造や将来のJRA-VAN取り込み仕様が変わっても、AI側の変更を小さく保つためです。

## 構成

```text
ended raw CSV -> raw tables -> sync-ended -> core tables -> ai views
```

- `raw` 層: CSV/JRA-VAN由来データをまず保存する取り込み口
- `core` 層: 終了済み・確定済みレースだけを保存する正規化済みテーブル
- `ai` 層: 学習・バックテストが読む安定したビュー
- `temp` ディレクトリ: 当日予測用の未確定データをParquetで一時保存する場所

Phase1ではJV-Link本接続は未実装です。`src/ingestion/jvlink_placeholder.py` に将来差し替え用の入口だけを置いています。

## ドキュメント

詳細な運用手順と設定説明は `docs/` に分けています。

- ユーザー向け入口: `docs/user/quickstart.md`
- 日常利用の手順: `docs/user/usage.md`
- 設定説明: `docs/user/configuration.md`
- 運用手順: `docs/user/operations.md`
- Codex向け作業入口: `AGENTS.md`
- Codex向け詳細: `docs/codex/context.md`, `docs/codex/commands.md`

## 重要な設計方針

core DBには、終了済み・確定済みのレースデータだけを保存します。

当日予測時に取得する出走表、オッズ、馬体重はcore DBには保存しません。当日データは `temp/` 配下のParquet、またはメモリ上のDataFrameとして扱います。

予測時は、前日までのcore DBと当日一時データを結合して特徴量を作ります。レース後、結果と払戻が確定したものだけを `sync-ended` でcore DBに差分保存します。

予測再現性のため、予測結果は `prediction_outputs` に保存できます。必要な場合だけ、予測入力のスナップショットを `prediction_input_snapshots` に保存できます。

AIの学習・バックテストにはcore DBのみを使います。当日の未確定出走表・オッズ・馬体重を学習用DBに混ぜないことを最優先ルールにします。

## セットアップ

Python 3.11以上と `uv` を想定しています。

```bash
uv sync
```

以降のコマンドは `uv run` 経由で実行します。

```bash
uv run python main.py --help
```

## .env

`.env.example` を `.env` にコピーして編集します。

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=keiba
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

## PostgreSQL作成例

PostgreSQLは、DBファイルを直接リポジトリ内に作るのではなく、PostgreSQLサーバーを起動して、その中に `keiba` データベースを作ります。

ローカル検証用にDBの格納先をこのリポジトリの1つ上の `../HorseRacingDB` にしたい場合は、PostgreSQLのデータディレクトリとして初期化します。

Windows PowerShell例:

```powershell
cd path\to\keiba-data-platform
mkdir ..\HorseRacingDB

initdb -D ..\HorseRacingDB -U postgres -W -E UTF8
pg_ctl -D ..\HorseRacingDB -l ..\HorseRacingDB\postgres.log start
createdb -h localhost -p 5432 -U postgres keiba
```

`initdb`, `pg_ctl`, `createdb` が見つからない場合は、PostgreSQLの `bin` ディレクトリをPATHに追加するか、フルパスで実行します。

例:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\initdb.exe" -D ..\HorseRacingDB -U postgres -W -E UTF8
& "C:\Program Files\PostgreSQL\16\bin\pg_ctl.exe" -D ..\HorseRacingDB -l ..\HorseRacingDB\postgres.log start
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -h localhost -p 5432 -U postgres keiba
```

WSL/Linux例:

```bash
mkdir -p ../HorseRacingDB
initdb -D ../HorseRacingDB -U postgres -W -E UTF8
pg_ctl -D ../HorseRacingDB -l ../HorseRacingDB/postgres.log start
createdb -h localhost -p 5432 -U postgres keiba
```

すでにPostgreSQLサーバーが起動している場合は、ログインしてDBだけ作成しても構いません。

```sql
CREATE DATABASE keiba;
```

その後、`.env` の接続情報を合わせてから接続確認します。

```bash
uv run python main.py check-db
```

## CSV配置

`data/raw/` に以下のCSVを配置します。

- `races.csv` -> `raw_races`
- `entries.csv` -> `raw_entries`
- `results.csv` -> `raw_results`
- `payouts.csv` -> `raw_payouts`
- `odds.csv` -> `raw_odds`

CSVヘッダーはSQL定義のカラム名に合わせます。`imported_at` は省略可能です。

`sync-ended` は `raw_results` と `raw_payouts` が存在するレースだけをcore層へ保存します。未確定の当日出走表や当日オッズをrawに取り込んだ場合でも、結果と払戻が揃うまではcore層へ同期されません。

例: `data/raw/races.csv`

```csv
race_id,race_date,course,race_no,race_name,surface,distance,direction,weather,ground_condition,race_class,race_grade,age_condition,sex_condition,field_size,start_time,source
202401010101,2024-01-06,中山,1,3歳未勝利,ダート,1200,右,晴,良,未勝利,,3歳,混合,16,10:05,csv
```

このリポジトリには、JRA-VAN接続前の確認用として `source=dummy` のCSVを `data/raw/` に置いています。8頭立て50レース、合計400出走行のサンプルです。先頭40レースは結果・払戻ありの確定済みレース、末尾10レースは出走表・オッズだけがある未確定扱いのレースです。fresh DBで `sync-ended` すると、core DBには確定済み40レースだけが同期されます。

## 実行コマンド

```bash
uv run python main.py check-db
uv run python main.py init-db
uv run python main.py import-csv
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
uv run python main.py check-odds-snapshots --date 2026-06-06
uv run python main.py predict-today --date 2026-06-06 --today-csv data/today/entries_20260606.csv
uv run python main.py segmented-backtest-report
uv run python main.py optimize-thresholds
```

`check-odds-snapshots` は `raw_*` 層の出走表とオッズを読むため、当日データをcore DBへ
混在させずに締切前複勝オッズのカバレッジを確認できます。`ready=true` は出走馬の95%以上に
有効な事前オッズがあることを示します。

複勝ターゲットは、8頭以上では3着以内、5〜7頭では2着以内として扱います。既存DBを使う
場合は `build-ai-views` を実行してビューを更新し、その後にモデルを再学習してください。

`predict-today` は入力CSVを `temp/` と `data/processed/prediction_logs/{run_id}/` に保存して
から、確定済み履歴と結合して予測します。未確定の出走表・オッズ・馬体重はcore DBへ保存
しません。CSVには少なくとも `race_id` と `horse_id` が必要で、`race_date` と `field_size` は
省略時にコマンド引数・レース内の出走馬数から補います。

`segmented-backtest-report` は `walk-forward-backtest` が出力した確定済みの買い目明細を、
競馬場・距離・馬場・人気帯・オッズ帯・期待値帯・年月で集計します。ROIは常に
`払戻額 / 賭け金` であり、1.0を超えると利益が出ていることを示します。

`optimize-thresholds` は `predictions_place.csv` を時系列で分割し、検証期間だけでSafe Agentの
閾値を選びます。テスト期間は、選んだ固定閾値の最終評価にしか使いません。レポートを見て
閾値を変更した場合は、同じテスト期間での評価を再利用せず、Walk-Forwardで再検証してください。

一括実行:

```bash
uv run python main.py run-all
```

## Phase2 複勝モデル

Phase2では、複勝のみを対象に LightGBM / CatBoost / XGBoost とアンサンブル予測を実行します。単勝・ワイド等の券種にはまだ対応していません。

追加依存関係:

```bash
uv sync
```

主要コマンド:

```bash
uv run python main.py train-place-model
uv run python main.py train-catboost-place
uv run python main.py train-xgboost-place
uv run python main.py train-all-models
uv run python main.py predict
uv run python main.py predict-ensemble
uv run python main.py safe-agent
uv run python main.py backtest-safe-agent
uv run python main.py model-compare
uv run python main.py walk-forward-backtest
uv run python main.py ablation-test
uv run python main.py phase2-report
```

出力:

- `models/lgbm_place_model.pkl`, `models/lgbm_place_metrics.json`
- `models/catboost_place_model.pkl`, `models/catboost_place_metrics.json`
- `models/xgboost_place_model.pkl`, `models/xgboost_place_metrics.json`
- `data/processed/predictions_place.csv`
- `data/processed/model_compare_summary.csv`
- `data/processed/walk_forward_summary.csv`
- `data/processed/walk_forward_detail.csv`
- `data/processed/ablation_summary.csv`
- `data/processed/phase2_report.json`

`predict-ensemble` は以下を出力します。

- `place_prob_lgbm`
- `place_prob_catboost`
- `place_prob_xgboost`
- `place_prob_ensemble_raw`
- `place_prob_calibrated`
- `place_prob_final`
- `model_uncertainty`
- `expected_value_place`
- `market_place_prob`
- `value_gap`
- `bet_score`

アンサンブルは `config.yaml` の `ensemble.method` で `simple_average` または `weighted_average` を選べます。`weighted_average` では `ensemble.weights` を使います。

Calibrationはvalidデータのみでfitし、testデータではfitしません。レース内確率補正では、8頭以上は複勝枠3、5から7頭は複勝枠2として、`race_id` ごとの合計確率を補正します。

Safe Agentは既存条件に加え、`safe_agent.max_model_uncertainty` を使います。`model_uncertainty <= 0.06` は通常stake、`0.06 < model_uncertainty <= 0.10` は1段階減額、`0.10` 超はBUYしません。

このプロジェクトの予測、バックテスト、検証結果は将来の利益を保証しません。実運用前に時系列分割、Walk-Forward、外部期間検証、資金管理ルールを必ず確認してください。

`run-all` は以下を順番に実行します。

1. DB接続確認
2. スキーマ作成
3. CSV取り込み
4. 終了済み・確定済みレースだけをcore層へ同期
5. AIビュー作成
6. データ品質チェック

## 日次運用手順

予測・分析で使う前に、前日までに終了・確定したレースをcore DBへ同期します。レース終了直後に取り込む必要はありません。次回使いたいタイミングで、必要な確定済みデータをrawへ置いてから同期します。

```bash
uv run python main.py import-csv
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
```

その後、当日予測用の未確定データを取得します。当日データはcore DBには保存せず、`temp/` 配下のParquet、またはメモリ上のDataFrameとして扱います。

```text
core DBの前日までの確定済みデータ
+ temp/ または DataFrame の当日出走表・オッズ・馬体重
-> 予測用特徴量
```

`sync-ended` は独立コマンドです。実行した時点でrawに存在するデータのうち、結果と払戻が揃っている確定済みレースだけをcore DBへ同期します。未確定の出走表・オッズ・馬体重はcore DBへ同期されません。

## ダミーデータ確認

JRA-VANから取得する前に、同梱のダミーCSVでDB作成からAIビュー作成まで確認できます。

古いダミーデータをすでに取り込んだDBでは、UPSERTだけではCSVから消えた古いraw行は削除されません。期待件数をきれいに確認したい場合は、fresh DBで実行するか、確認用DBを作り直してから実行してください。

```bash
uv run python main.py check-db
uv run python main.py init-db
uv run python main.py import-csv
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
```

fresh DBで実行した場合の目安は以下です。

- rawには50レース、400出走行が入る
- coreの `races` には結果・払戻が揃った40レースだけ入る
- `ai_race_entries` は確定済み40レースの320出走行になる
- `target_place` は複勝圏内なら1、それ以外なら0になる
- `horse_results_history` には対象レース `202401060601` より前の日付の履歴レースが入る
- 末尾10レースの未確定データはcore DBにもAIビューにも入らない

品質チェック結果は `logs/data_quality_report.json` に出力されます。

確認SQL例:

```sql
SELECT COUNT(*) FROM raw_races;
SELECT COUNT(*) FROM races;
SELECT COUNT(*) FROM entries;
SELECT target_place, COUNT(*) FROM ai_race_entries GROUP BY target_place ORDER BY target_place;
SELECT race_id, race_date, horse_id, finish_position
FROM horse_results_history
WHERE horse_id = 'H000001'
ORDER BY race_date;
```

## 作成されるテーブル

raw層:

- `raw_races`
- `raw_entries`
- `raw_results`
- `raw_payouts`
- `raw_odds`

core層:

- `races`
- `entries`
- `results`
- `payouts`
- `odds_snapshots`
- `horse_results_history`
- `prediction_outputs`
- `prediction_input_snapshots`

AI層ビュー:

- `ai_race_entries`
- `ai_horse_history`

## データ品質チェック

`uv run python main.py validate` は以下を確認し、`logs/data_quality_report.json` に保存します。

- `races` 件数
- `entries` 件数
- `results` 件数
- `race_id` の重複
- `entries.race_id` が `races` に存在するか
- `results.race_id, horse_id` が `entries` に存在するか
- `field_size` と `entries` 件数の差異
- `odds_win <= 0` の件数
- `odds_place_min <= 0` の件数
- `payout_place` 欠損件数
- `horse_id` 欠損件数

## 将来のJRA-VAN連携

Phase1ではCSV取り込みを実装しています。将来は `JvLinkDataSource` を実装し、同じrawテーブルに保存することで、core層とAIビューの利用方法を維持したまま本接続へ差し替える想定です。
