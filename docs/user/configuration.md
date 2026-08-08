# Configuration

The main runtime file is `config.yaml`. Use `config.example.yaml` as a clean template.

## Environment

Database credentials live in `.env`, not in Git:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=keiba
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

## Paths

`paths` is the preferred structured location:

```yaml
paths:
  raw_data_dir: data/raw
  temp_data_dir: temp
  processed_data_dir: data/processed
  model_dir: models
  log_dir: logs
```

`raw_data_dir` and `temp_data_dir` also remain at the top level for backward compatibility.

## Modeling

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

Calibration must be fit on valid data only. Test data is for evaluation.

## Ensemble

```yaml
ensemble:
  method: simple_average
  weights:
    lgbm: 0.34
    catboost: 0.33
    xgboost: 0.33
```

Supported methods:

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

`model_uncertainty > max_model_uncertainty` means no BUY.

## Validation

Walk-forward folds are configurable:

```yaml
validation:
  walk_forward:
    folds:
      - train_start: 2016
        train_end: 2019
        valid_start: 2020
        valid_end: 2020
        test_start: 2021
        test_end: 2021
```

Keep all folds chronological.
