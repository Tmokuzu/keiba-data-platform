using JvLinkImporter.Models;
using Microsoft.Extensions.Logging;
using Npgsql;
using System.Security.Cryptography;
using System.Text;

namespace JvLinkImporter.Database;

public sealed class PostgresRepository : IAsyncDisposable
{
    private readonly NpgsqlDataSource _dataSource;
    private readonly ILogger<PostgresRepository> _logger;
    private readonly bool _captureMarketOdds;

    public PostgresRepository(
        string connectionString,
        ILogger<PostgresRepository> logger,
        bool captureMarketOdds)
    {
        _logger = logger;
        _captureMarketOdds = captureMarketOdds;
        _dataSource = NpgsqlDataSource.Create(connectionString);
    }

    public Task UpsertAsync(IJvRecord record)
    {
        return record switch
        {
            RaceRecord race => UpsertRaceAsync(race),
            EntryRecord entry => UpsertEntryAsync(entry),
            ResultRecord result => UpsertResultAsync(result),
            PayoutRecord payout => UpsertPayoutAsync(payout),
            OddsRecord odds => UpsertOddsAsync(odds),
            // Core history is derived by Python's sync-ended pipeline.
            // JV-Link records must not bypass raw/core separation.
            HorseHistoryRecord => Task.CompletedTask,
            _ => throw new NotSupportedException($"Unsupported record type: {record.GetType().Name}")
        };
    }

    public async Task StoreRawRecordAsync(string dataSpec, string raw)
    {
        var hashBytes = SHA256.HashData(Encoding.UTF8.GetBytes($"{dataSpec}\n{raw}"));
        var recordHash = Convert.ToHexString(hashBytes).ToLowerInvariant();
        var recordType = raw.Length >= 2 ? raw[..2] : "";
        const string sql = """
            INSERT INTO raw_jv_records (record_hash, data_spec, record_type, raw_payload, source)
            VALUES (@record_hash, @data_spec, @record_type, @raw_payload, 'jvlink')
            ON CONFLICT (record_hash) DO NOTHING
            """;
        await using var command = _dataSource.CreateCommand(sql);
        Add(command, "record_hash", recordHash);
        Add(command, "data_spec", dataSpec);
        Add(command, "record_type", recordType);
        Add(command, "raw_payload", raw);
        await ExecuteAsync(command);
    }

    public async Task<IReadOnlyList<string>> LoadRaceIdsByDateAsync(DateOnly raceDate)
    {
        const string sql = """
            SELECT race_id
            FROM raw_races
            WHERE race_date = @race_date
            ORDER BY race_id
            """;
        await using var command = _dataSource.CreateCommand(sql);
        Add(command, "race_date", raceDate);
        var raceIds = new List<string>();
        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            raceIds.Add(reader.GetString(0));
        }

        return raceIds;
    }

    private async Task UpsertRaceAsync(RaceRecord record)
    {
        const string sql = """
            INSERT INTO raw_races (
                race_id, race_date, course, race_no, race_name, surface, distance, direction,
                weather, ground_condition, race_class, race_grade, age_condition, sex_condition,
                field_size, start_time, source
            )
            VALUES (
                @race_id, @race_date, @course, @race_no, @race_name, @surface, @distance,
                @direction, @weather, @ground_condition, @race_class, @race_grade,
                @age_condition, @sex_condition, @field_size, @start_time, 'jvlink'
            )
            ON CONFLICT (race_id) DO UPDATE SET
                race_date = EXCLUDED.race_date,
                course = EXCLUDED.course,
                race_no = EXCLUDED.race_no,
                race_name = EXCLUDED.race_name,
                surface = EXCLUDED.surface,
                distance = EXCLUDED.distance,
                direction = EXCLUDED.direction,
                weather = EXCLUDED.weather,
                ground_condition = EXCLUDED.ground_condition,
                race_class = EXCLUDED.race_class,
                race_grade = EXCLUDED.race_grade,
                age_condition = EXCLUDED.age_condition,
                sex_condition = EXCLUDED.sex_condition,
                field_size = EXCLUDED.field_size,
                start_time = EXCLUDED.start_time,
                source = EXCLUDED.source,
                imported_at = CURRENT_TIMESTAMP
            """;
        await using var command = _dataSource.CreateCommand(sql);
        Add(command, "race_id", record.RaceId);
        Add(command, "race_date", record.RaceDate);
        Add(command, "course", record.Course);
        Add(command, "race_no", record.RaceNo);
        Add(command, "race_name", record.RaceName);
        Add(command, "surface", record.Surface);
        Add(command, "distance", record.Distance);
        Add(command, "direction", record.Direction);
        Add(command, "weather", record.Weather);
        Add(command, "ground_condition", record.GroundCondition);
        Add(command, "race_class", record.RaceClass);
        Add(command, "race_grade", record.RaceGrade);
        Add(command, "age_condition", record.AgeCondition);
        Add(command, "sex_condition", record.SexCondition);
        Add(command, "field_size", record.FieldSize);
        Add(command, "start_time", record.StartTime);
        await ExecuteAsync(command);
    }

    private async Task UpsertEntryAsync(EntryRecord record)
    {
        const string sql = """
            INSERT INTO raw_entries (
                race_id, horse_id, horse_name, horse_no, frame_no, jockey_id, jockey_name,
                trainer_id, trainer_name, horse_age, horse_sex, weight_carried,
                body_weight, body_weight_diff, odds_win, odds_place_min, odds_place_max,
                popularity, source
            )
            VALUES (
                @race_id, @horse_id, @horse_name, @horse_no, @frame_no, @jockey_id,
                @jockey_name, @trainer_id, @trainer_name, @horse_age, @horse_sex,
                @weight_carried, @body_weight, @body_weight_diff, @odds_win,
                @odds_place_min, @odds_place_max, @popularity, 'jvlink'
            )
            ON CONFLICT (race_id, horse_id) DO UPDATE SET
                horse_name = EXCLUDED.horse_name,
                horse_no = EXCLUDED.horse_no,
                frame_no = EXCLUDED.frame_no,
                jockey_id = EXCLUDED.jockey_id,
                jockey_name = EXCLUDED.jockey_name,
                trainer_id = EXCLUDED.trainer_id,
                trainer_name = EXCLUDED.trainer_name,
                horse_age = EXCLUDED.horse_age,
                horse_sex = EXCLUDED.horse_sex,
                weight_carried = EXCLUDED.weight_carried,
                body_weight = EXCLUDED.body_weight,
                body_weight_diff = EXCLUDED.body_weight_diff,
                odds_win = COALESCE(EXCLUDED.odds_win, raw_entries.odds_win),
                odds_place_min = COALESCE(EXCLUDED.odds_place_min, raw_entries.odds_place_min),
                odds_place_max = COALESCE(EXCLUDED.odds_place_max, raw_entries.odds_place_max),
                popularity = COALESCE(EXCLUDED.popularity, raw_entries.popularity),
                source = EXCLUDED.source,
                imported_at = CURRENT_TIMESTAMP
            """;
        await using var command = _dataSource.CreateCommand(sql);
        AddEntryParameters(command, record);
        await ExecuteAsync(command);
    }

    private async Task UpsertResultAsync(ResultRecord record)
    {
        const string sql = """
            INSERT INTO raw_results (
                race_id, horse_id, finish_position, finish_time, margin, corner_order, last_3f, source
            )
            VALUES (
                @race_id, @horse_id, @finish_position, @finish_time, @margin,
                @corner_order, @last_3f, 'jvlink'
            )
            ON CONFLICT (race_id, horse_id) DO UPDATE SET
                finish_position = EXCLUDED.finish_position,
                finish_time = EXCLUDED.finish_time,
                margin = EXCLUDED.margin,
                corner_order = EXCLUDED.corner_order,
                last_3f = EXCLUDED.last_3f,
                source = EXCLUDED.source,
                imported_at = CURRENT_TIMESTAMP
            """;
        await using var command = _dataSource.CreateCommand(sql);
        Add(command, "race_id", record.RaceId);
        Add(command, "horse_id", record.HorseId);
        Add(command, "finish_position", record.FinishPosition);
        Add(command, "finish_time", record.FinishTime);
        Add(command, "margin", record.Margin);
        Add(command, "corner_order", record.CornerOrder);
        Add(command, "last_3f", record.Last3F);
        await ExecuteAsync(command);
    }

    private async Task UpsertPayoutAsync(PayoutRecord record)
    {
        const string sql = """
            INSERT INTO raw_payouts (race_id, ticket_type, combination, payout, source)
            VALUES (@race_id, @ticket_type, @combination, @payout, 'jvlink')
            ON CONFLICT (race_id, ticket_type, combination) DO UPDATE SET
                payout = EXCLUDED.payout,
                source = EXCLUDED.source,
                imported_at = CURRENT_TIMESTAMP
            """;
        await using var command = _dataSource.CreateCommand(sql);
        Add(command, "race_id", record.RaceId);
        Add(command, "ticket_type", record.TicketType);
        Add(command, "combination", record.Combination);
        Add(command, "payout", record.Payout);
        await ExecuteAsync(command);
    }

    private async Task UpsertOddsAsync(OddsRecord record)
    {
        // Historical O1 data is retrieved after the race and is not a valid
        // pre-start market observation. Only the realtime command may persist it.
        if (!_captureMarketOdds)
        {
            return;
        }
        var snapshotTime = DateTime.Now;
        const string sql = """
            UPDATE raw_entries SET
                odds_win = COALESCE(@odds_win, odds_win),
                odds_place_min = COALESCE(@odds_place_min, odds_place_min),
                odds_place_max = COALESCE(@odds_place_max, odds_place_max),
                popularity = COALESCE(@popularity, popularity),
                imported_at = CURRENT_TIMESTAMP
            WHERE race_id = @race_id
              AND horse_no = @horse_no
            """;
        await using var command = _dataSource.CreateCommand(sql);
        Add(command, "race_id", record.RaceId);
        Add(command, "horse_no", record.HorseNo);
        Add(command, "odds_win", record.OddsWin);
        Add(command, "odds_place_min", record.OddsPlaceMin);
        Add(command, "odds_place_max", record.OddsPlaceMax);
        Add(command, "popularity", record.Popularity);
        await ExecuteAsync(command);

        await InsertOddsSnapshotAsync(
            record.RaceId,
            snapshotTime,
            "win",
            record.HorseNo.ToString(),
            record.OddsWin);
        await InsertOddsSnapshotAsync(
            record.RaceId,
            snapshotTime,
            "place",
            record.HorseNo.ToString(),
            record.OddsPlaceMin);
    }

    private async Task InsertOddsSnapshotAsync(
        string raceId,
        DateTime snapshotTime,
        string ticketType,
        string combination,
        double? odds)
    {
        if (odds is null)
        {
            return;
        }

        const string sql = """
            INSERT INTO raw_odds (
                race_id, snapshot_time, ticket_type, combination, odds, source
            )
            VALUES (
                @race_id, @snapshot_time, @ticket_type, @combination, @odds, 'jvlink'
            )
            ON CONFLICT (race_id, snapshot_time, ticket_type, combination) DO UPDATE SET
                odds = EXCLUDED.odds,
                source = EXCLUDED.source,
                imported_at = CURRENT_TIMESTAMP
            """;
        await using var command = _dataSource.CreateCommand(sql);
        Add(command, "race_id", raceId);
        Add(command, "snapshot_time", snapshotTime);
        Add(command, "ticket_type", ticketType);
        Add(command, "combination", combination);
        Add(command, "odds", odds);
        await ExecuteAsync(command);
    }

    private void AddEntryParameters(NpgsqlCommand command, EntryRecord record)
    {
        Add(command, "race_id", record.RaceId);
        Add(command, "horse_id", record.HorseId);
        Add(command, "horse_name", record.HorseName);
        Add(command, "horse_no", record.HorseNo);
        Add(command, "frame_no", record.FrameNo);
        Add(command, "jockey_id", record.JockeyId);
        Add(command, "jockey_name", record.JockeyName);
        Add(command, "trainer_id", record.TrainerId);
        Add(command, "trainer_name", record.TrainerName);
        Add(command, "horse_age", record.HorseAge);
        Add(command, "horse_sex", record.HorseSex);
        Add(command, "weight_carried", record.WeightCarried);
        Add(command, "body_weight", record.BodyWeight);
        Add(command, "body_weight_diff", record.BodyWeightDiff);
        Add(command, "odds_win", _captureMarketOdds ? record.OddsWin : null);
        Add(command, "odds_place_min", _captureMarketOdds ? record.OddsPlaceMin : null);
        Add(command, "odds_place_max", _captureMarketOdds ? record.OddsPlaceMax : null);
        Add(command, "popularity", _captureMarketOdds ? record.Popularity : null);
    }

    private async Task ExecuteAsync(NpgsqlCommand command)
    {
        var rows = await command.ExecuteNonQueryAsync();
        _logger.LogDebug("Upsert affected {Rows} rows", rows);
    }

    private static void Add(NpgsqlCommand command, string name, object? value)
    {
        command.Parameters.AddWithValue(name, value ?? DBNull.Value);
    }

    public async ValueTask DisposeAsync()
    {
        await _dataSource.DisposeAsync();
    }
}
