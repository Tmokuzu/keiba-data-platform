# JRA-VAN JV-Link Importer

Windows上でJV-Linkを呼び出し、取得したJRA-VAN Data Lab.データをこのプロジェクトの
PostgreSQL raw層へ保存する取込ツールです。

AI本体はWSL/Linux側のPythonで動かし、この取込ツールだけWindows側で実行する想定です。

## 前提

- Windows
- .NET 8 SDK
- JRA-VAN Data Lab.登録済み
- JV-Linkインストール済み
- JV-Linkへ利用キー設定済み
- PostgreSQLへ接続可能

## セットアップ

```powershell
cd jvlink_importer
copy appsettings.example.json appsettings.json
dotnet restore
```

`appsettings.json`の接続文字列を環境に合わせて変更してください。
`dotnet run`は`jvlink_importer`ディレクトリで実行してください。

取込前に、プロジェクトルートでPython側のテーブルを作成します。

```bash
uv run python main.py init-db
```

WSL側PostgreSQLへWindowsから接続する場合、まずPowerShellで疎通確認します。

```powershell
Test-NetConnection localhost -Port 5432
```

## 取得方針

予測に使える可能性があるJV-Linkレコードは、対応パーサーが未実装でも `raw_jv_records`
へそのまま保存します。これは将来の固定長位置検証・特徴量追加のための監査元データです。
正規化済みの `raw_races` 等に書き込まれるのは、現在パーサー対応しているレコードだけです。

Python側で先にアーカイブテーブルを作成してください。

```bash
uv run python main.py init-db
```

## 実行

まずJV-Link接続確認:

```powershell
dotnet run -- check
```

過去データを取得:

```powershell
dotnet run -- import-setup --from 20230101000000 --types RA,SE,HR,O1 --max-read 20000 --progress-every 1000
```

通常差分を取得:

```powershell
dotnet run -- import-diff --from 20240101000000 --types RA,SE,HR,O1 --max-read 20000 --progress-every 1000
```

`--data-spec` により、JRA-VANの追加データ種別も取得・アーカイブできます。最初は各種別で
`scan-types-*` を実行し、件数とレコード種別を確認してから本取込してください。

| 目的 | DataSpec | 主なレコード | 現在の扱い |
| --- | --- | --- | --- |
| レース・成績・払戻 | `RACE` | RA, SE, HR, O1〜O6 | RA/SE/HR/O1を正規化、全件アーカイブ |
| 馬・騎手・調教師等の差分マスタ | `DIFN` | UM, KS, CH, BR, BN, RC | アーカイブ、次段階で正規化 |
| 出走時点の着度数 | `SNPN` | CK | アーカイブ、次段階で特徴量化 |
| 坂路調教 | `SLOP` | HC | アーカイブ、次段階で特徴量化 |
| ウッド調教 | `WOOD` | WC | アーカイブ、次段階で特徴量化 |
| 血統 | `BLOD` | HN, SK, BT | アーカイブ、次段階で特徴量化 |
| コース情報 | `COMM` | CS | アーカイブ、次段階で特徴量化 |
| データマイニング予想 | `MING` | DM, TM | アーカイブ、採用は別途検証 |

例: まずCKの提供レコードを確認してから取得する場合。

```powershell
dotnet run -- scan-types-setup --from 20230101000000 --data-spec SNPN --max-read 100000
dotnet run -- import-setup --from 20230101000000 --data-spec SNPN --max-read 20000 --progress-every 1000
```

取得可能な全期間のDataSpecを一括でアーカイブする場合は、Windows PowerShellで次を実行します。
既定は1999-06-01以降で、`RACE` も含めます。提供開始前・契約対象外の種別は警告を出して次へ
進みます。既に正規化済みのRACEを再取得しても、rawアーカイブはハッシュで重複保存しません。

```powershell
cd jvlink_importer
.\scripts\import-all-archive.ps1
# RACEを飛ばして追加種別だけ取得する場合
.\scripts\import-all-archive.ps1 -SkipRace
```

JRA-VANの契約・提供期間により取得可能範囲は異なります。特に時系列オッズは、実際にレース前に
取得・保存した時刻付きデータだけを期待値の学習・検証に使います。

当日の締切前オッズを時刻付きで保存:

```powershell
dotnet run -- import-rt-odds --date 2026-05-31 --progress-every 1
```

`import-rt-odds`は当日レースIDごとにリアルタイム系データを取得し、`O1`から読めた単勝・複勝オッズを`raw_odds`へ保存します。`snapshot_time`は取込実行時刻です。レース前に何度か実行することで、Python側の`check-odds-snapshots`が発走前オッズのカバレッジを確認できます。

`import-setup` と `import-diff` は過去データの市場オッズを保存しません。過去に取得した`O1`は
当時の締切前オッズではないため、学習・バックテストへの将来情報混入を避けるためです。市場オッズを
保存するのは、レース前に実行する `import-rt-odds` だけです。

最初は`--max-read`を小さめにして、PostgreSQLへ入る件数と中身を確認してください。
問題なければ`--max-read`を外すと、JV-Linkが返す対象データを最後まで読み込みます。
`--progress-every`は何レコードごとに進捗ログを出すかを指定します。

parser実装前に、JV-Linkから返る生レコードを確認:

```powershell
dotnet run -- dump-raw-setup --from 20230101000000 --out raw_jv_records.txt --limit 100
```

返ってくるレコード種別の分布を確認:

```powershell
dotnet run -- scan-types-setup --from 20230101000000 --max-read 100000
```

ファイルにも保存する場合:

```powershell
dotnet run -- scan-types-setup --from 20230101000000 --max-read 100000 --out C:\temp\type_counts.csv
```

Phase1に必要な`RA`/`SE`/`HR`/`O1`だけを探す場合:

```powershell
dotnet run -- dump-raw-setup --from 20230101000000 --out C:\temp\raw_race_records.txt --types RA,SE,HR,O1 --limit 100 --max-read 20000
```

`JVRead failed. Code=-3`が出る場合は、JV-Linkがまだファイルをダウンロード中です。現在の雛形は`appsettings.json`の以下の設定で待機リトライします。

```json
"DownloadWaitMilliseconds": 2000,
"MaxDownloadWaitRetries": 300
```

見つからない場合は、実行したPowerShellのカレントディレクトリを確認します。

```powershell
Get-Location
Get-ChildItem -Recurse -Filter raw_jv_records.txt
```

迷う場合は絶対パスで指定してください。

```powershell
dotnet run -- dump-raw-setup --from 20230101000000 --out C:\temp\raw_jv_records.txt --limit 100
```

## 実装方針

JV-Linkから返るデータはレコード種別ごとの固定長文字列です。この取込ツールでは、JV-Link呼び出し、ログ、PostgreSQL upsert、Phase1に必要な主要レコードのparserを用意しています。

`src/Parsing/JvRecordParser.cs`は以下をraw層へ保存します。

- `RA` レース情報 -> `raw_races`
- `SE` 出走馬情報・成績 -> `raw_entries` / `raw_results`
- `HR` 払戻 -> `raw_payouts`
- `O1` 単勝・複勝オッズ -> `raw_entries` / `raw_odds`

取込後はプロジェクトルートで次を実行します。`sync-ended` が全出走馬に対応する結果と払戻のそろった
レースだけをcore層へ送り、未確定または部分取込の当日データはraw層に残します。

```bash
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
```

`import-setup`や`import-diff`で過去レースの`O1`を取り込んだ場合も`odds_snapshots`へ保存されますが、`snapshot_time`は取込時刻です。そのため過去レースの締切前オッズとしては扱えません。厳密なバックテスト用には、当時の時刻付きオッズを別途保存しておく必要があります。現在の`odds_snapshots`は主に当日予想・今後の実運用ログ用です。

固定長位置はJRA-VAN SDKに含まれる「JV-Data仕様書」に依存します。実データで不自然な値が出る場合は、生レコードを`dump-raw-*`で保存してparser位置を調整してください。
