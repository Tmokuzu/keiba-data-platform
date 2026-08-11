# クイックスタート

通常の利用手順は [利用ガイド](usage.md) を参照してください。このページは初回セットアップと
最短の確認手順だけをまとめています。

## 初期設定

```bash
uv sync
cp .env.example .env
```

`.env` にPostgreSQL接続情報を設定します。

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=keiba
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

接続を確認します。

```bash
uv run python main.py check-db
```

## 確定済みデータの取り込み

Place CSV files in `data/raw/`, then run:

```bash
uv run python main.py init-db
uv run python main.py import-csv
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
```

`sync-ended` がcore層へ送るのは、終了・確定済みレースだけです。当日・未確定データはraw層または
`temp/` に置き、core DBには混在させません。

JV-Link の追加アーカイブ（`SNPN` の CK を含む）を取り込んだ後は、学習前に次を一度実行します。

```bash
uv run python main.py init-db
uv run python main.py normalize-jv-snapshots
uv run python main.py normalize-jv-training
```

CK は各レース時点の馬の中央実績・賞金を追加する特徴量です。取り込めていない期間は欠損のまま扱い、
将来の成績で補いません。

`normalize-jv-training` はJV-Linkの坂路（HC）・ウッドチップ（WC）調教を正規化します。調教日が
対象レース日より前の記録だけを特徴量化します。

## Phase 2の学習と予測

Train all place models and build ensemble predictions:

```bash
uv run python main.py train-all-models
uv run python main.py predict-ensemble
uv run python main.py safe-agent
uv run python main.py backtest-safe-agent
```

大量データで前処理と学習を分けたい場合は、前処理結果を一時キャッシュしてから実行できます。
このキャッシュと学習済みモデルはGit管理されません。データを再取込した場合はキャッシュを作り直します。

```bash
uv run python main.py prepare-training-frame
uv run python main.py train-all-models --use-prepared-frame
```

検証レポート:

```bash
uv run python main.py model-compare
uv run python main.py walk-forward-backtest
uv run python main.py ablation-test
uv run python main.py phase2-report
```

当日予測、締切前オッズ確認、出力の読み方は [利用ガイド](usage.md) を参照してください。
バックテストやモデル指標は将来の利益を保証しません。
