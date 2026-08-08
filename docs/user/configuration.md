# 設定

実行時設定は `config.yaml` です。初期化には `config.example.yaml` を使います。

## PostgreSQL接続

接続情報はGitへ入れず、`.env` に保存します。

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=keiba
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

## パス

`paths` で生成物と一時データの保存先を指定します。

```yaml
paths:
  raw_data_dir: data/raw
  temp_data_dir: temp
  processed_data_dir: data/processed
  model_dir: models
  log_dir: logs
```

`raw_data_dir` と `temp_data_dir` のトップレベル設定は後方互換用です。通常は `paths` を使います。

## モデル

`modeling` controls the place target, time split size, calibration, and probability correction:

```yaml
modeling:
  target: target_place
  ticket_type: place
  random_state: 42
  valid_size: 0.2
  test_size: 0.2
  calibration:
    method: isotonic
    fit_split: valid
```

複勝は8頭以上で3着以内、5〜7頭で2着以内を的中とします。校正は検証期間だけで行い、
テスト期間は評価専用です。

## アンサンブル

```yaml
ensemble:
  method: simple_average
  weights:
    lgbm: 0.34
    catboost: 0.33
    xgboost: 0.33
```

利用できる方式:

- `simple_average`
- `weighted_average`

## Safe Agent

```yaml
safe_agent:
  min_expected_value_place: 1.05
  min_value_gap: 0.03
  min_bet_score: 0.02
  max_model_uncertainty: 0.10
  stake_high: 1000
  stake_mid: 500
  stake_low: 300
```

`model_uncertainty > max_model_uncertainty` の馬は購入しません。`min_expected_value_place`、
`min_value_gap`、`min_bet_score` は `optimize-thresholds` の候補と一致しています。

## 締切前オッズ

```yaml
data:
  odds_snapshot_cutoff_minutes_before_start: 1
```

`check-odds-snapshots` が、有効なオッズとみなす発走前の猶予時間です。

## 検証

Walk-Forwardの期間と、閾値選択に必要な最小買い目数を設定できます。

```yaml
validation:
  threshold_optimization:
    min_validation_bets: 50
  walk_forward:
    folds:
      - train_start: 2016
        train_end: 2019
        valid_start: 2020
        valid_end: 2020
        test_start: 2021
        test_end: 2021
```

すべての期間は時系列順に保ってください。テスト期間を見て設定を変えた場合は、新しい将来期間または
Walk-Forwardで改めて評価します。
