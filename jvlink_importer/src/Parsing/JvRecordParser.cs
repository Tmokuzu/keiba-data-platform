using JvLinkImporter.Models;
using Microsoft.Extensions.Logging;

namespace JvLinkImporter.Parsing;

public sealed class JvRecordParser
{
    private readonly ILogger<JvRecordParser> _logger;

    public JvRecordParser(ILogger<JvRecordParser> logger)
    {
        _logger = logger;
    }

    public IReadOnlyList<IJvRecord> Parse(string raw)
    {
        if (raw.Length < 2)
        {
            return [];
        }

        var normalized = raw.TrimStart('\ufeff');
        if (normalized.Length < 2)
        {
            return [];
        }

        raw = normalized;
        var recordType = raw[..2];
        return recordType switch
        {
            "RA" => ParseRace(raw),
            "SE" => ParseEntryOrResult(raw),
            "HR" => ParsePayout(raw),
            "O1" => ParseOdds1(raw),
            _ => Skip(recordType)
        };
    }

    private IReadOnlyList<IJvRecord> ParseRace(string raw)
    {
        var raceDate = DateOnly.ParseExact(
            FixedWidth.Text(raw, 11, 4) + FixedWidth.Text(raw, 15, 4),
            "yyyyMMdd");
        var courseCode = FixedWidth.Text(raw, 19, 2);
        var surface = SurfaceFromTrackCode(FixedWidth.Text(raw, 705, 2));
        var ground = surface == "ダート"
            ? GroundCondition(FixedWidth.Text(raw, 889, 1))
            : GroundCondition(FixedWidth.Text(raw, 888, 1));

        return
        [
            new RaceRecord(
                RaceId(raw),
                raceDate,
                CourseName(courseCode),
                FixedWidth.Int(raw, 25, 2) ?? 0,
                FixedWidth.Text(raw, 32, 60),
                surface,
                FixedWidth.Int(raw, 697, 4),
                DirectionFromTrackCode(FixedWidth.Text(raw, 705, 2)),
                Weather(FixedWidth.Text(raw, 887, 1)),
                ground,
                FixedWidth.Text(raw, 634, 3),
                FixedWidth.Text(raw, 614, 1),
                FixedWidth.Text(raw, 622, 3),
                FixedWidth.Text(raw, 618, 3),
                FixedWidth.Int(raw, 883, 2) ?? FixedWidth.Int(raw, 881, 2),
                FixedWidth.Text(raw, 873, 4))
        ];
    }

    private IReadOnlyList<IJvRecord> ParseEntryOrResult(string raw)
    {
        var raceId = RaceId(raw);
        var raceDate = DateOnly.ParseExact(
            FixedWidth.Text(raw, 11, 4) + FixedWidth.Text(raw, 15, 4),
            "yyyyMMdd");
        var horseId = FixedWidth.Text(raw, 30, 10);
        var horseName = FixedWidth.Text(raw, 40, 36);
        var bodyWeight = FixedWidth.Int(raw, 324, 3);
        var bodyWeightDiff = FixedWidth.Int(raw, 328, 3);
        if (FixedWidth.Text(raw, 327, 1) == "-")
        {
            bodyWeightDiff *= -1;
        }

        var winOddsRaw = FixedWidth.Int(raw, 359, 4);
        var winOdds = winOddsRaw is null or 0 or 9999 ? null : winOddsRaw / 10.0;
        var finish = FixedWidth.Int(raw, 334, 2);
        if (finish == 0)
        {
            finish = null;
        }

        var last3F = FixedWidth.Int(raw, 390, 3);
        var last3FValue = last3F is null or 0 or 999 ? null : last3F / 10.0;

        return
        [
            new EntryRecord(
                raceId,
                horseId,
                horseName,
                FixedWidth.Int(raw, 28, 2),
                FixedWidth.Int(raw, 27, 1),
                FixedWidth.Text(raw, 296, 5),
                FixedWidth.Text(raw, 306, 8),
                FixedWidth.Text(raw, 85, 5),
                FixedWidth.Text(raw, 90, 8),
                FixedWidth.Int(raw, 82, 2),
                HorseSex(FixedWidth.Text(raw, 78, 1)),
                (FixedWidth.Int(raw, 288, 3) ?? 0) / 10.0,
                bodyWeight,
                bodyWeightDiff,
                winOdds,
                null,
                null,
                FixedWidth.Int(raw, 363, 2)),
            new ResultRecord(
                raceId,
                horseId,
                finish,
                FixedWidth.Text(raw, 338, 4),
                FixedWidth.Text(raw, 342, 3),
                CornerOrder(raw),
                last3FValue),
            new HorseHistoryRecord(
                raceId,
                raceDate,
                horseId,
                horseName,
                null,
                null,
                null,
                null,
                null,
                null,
                finish,
                null,
                last3FValue,
                FixedWidth.Int(raw, 363, 2),
                (FixedWidth.Int(raw, 288, 3) ?? 0) / 10.0,
                bodyWeight,
                bodyWeightDiff,
                FixedWidth.Text(raw, 296, 5),
                FixedWidth.Text(raw, 85, 5))
        ];
    }

    private IReadOnlyList<IJvRecord> ParsePayout(string raw)
    {
        var records = new List<IJvRecord>();
        var raceId = RaceId(raw);
        AddPayouts(records, raw, raceId, "win", 102, 3, 13, 2, 9);
        AddPayouts(records, raw, raceId, "place", 141, 5, 13, 2, 9);
        return records;
    }

    private IReadOnlyList<IJvRecord> ParseOdds1(string raw)
    {
        var raceId = RaceId(raw);
        var oddsByHorse = new Dictionary<int, OddsRecord>();

        for (var i = 0; i < 28; i++)
        {
            var start = 43 + i * 8;
            var horseNo = FixedWidth.Int(raw, start, 2);
            if (horseNo is null or 0)
            {
                continue;
            }

            var oddsRaw = FixedWidth.Int(raw, start + 2, 4);
            var odds = oddsRaw is null or 0 or 9999 ? null : oddsRaw / 10.0;
            oddsByHorse[horseNo.Value] = new OddsRecord(
                raceId,
                horseNo.Value,
                odds,
                null,
                null,
                FixedWidth.Int(raw, start + 6, 2));
        }

        for (var i = 0; i < 28; i++)
        {
            var start = 267 + i * 12;
            var horseNo = FixedWidth.Int(raw, start, 2);
            if (horseNo is null or 0)
            {
                continue;
            }

            var minRaw = FixedWidth.Int(raw, start + 2, 4);
            var maxRaw = FixedWidth.Int(raw, start + 6, 4);
            var min = minRaw is null or 0 or 9999 ? null : minRaw / 10.0;
            var max = maxRaw is null or 0 or 9999 ? null : maxRaw / 10.0;
            oddsByHorse.TryGetValue(horseNo.Value, out var existing);
            oddsByHorse[horseNo.Value] = new OddsRecord(
                raceId,
                horseNo.Value,
                existing?.OddsWin,
                min,
                max,
                existing?.Popularity);
        }

        return oddsByHorse.Values.Cast<IJvRecord>().ToList();
    }

    private IReadOnlyList<IJvRecord> Skip(string recordType)
    {
        _logger.LogDebug("Skipping unsupported JV record type: {RecordType}", recordType);
        return [];
    }

    private static string RaceId(string raw)
    {
        return string.Concat(
            FixedWidth.Text(raw, 11, 4),
            FixedWidth.Text(raw, 15, 4),
            FixedWidth.Text(raw, 19, 2),
            FixedWidth.Text(raw, 21, 2),
            FixedWidth.Text(raw, 23, 2),
            FixedWidth.Text(raw, 25, 2));
    }

    private static void AddPayouts(
        List<IJvRecord> records,
        string raw,
        string raceId,
        string ticketType,
        int start,
        int repeat,
        int width,
        int combinationWidth,
        int payoutWidth)
    {
        for (var i = 0; i < repeat; i++)
        {
            var offset = start + i * width;
            var combination = FixedWidth.Text(raw, offset, combinationWidth);
            var payout = FixedWidth.Int(raw, offset + combinationWidth, payoutWidth);
            if (string.IsNullOrWhiteSpace(combination) || combination.All(c => c == '0') || payout is null or 0)
            {
                continue;
            }
            records.Add(new PayoutRecord(raceId, ticketType, combination, payout));
        }
    }

    private static string? CornerOrder(string raw)
    {
        var corners = new[]
        {
            FixedWidth.Text(raw, 351, 2),
            FixedWidth.Text(raw, 353, 2),
            FixedWidth.Text(raw, 355, 2),
            FixedWidth.Text(raw, 357, 2),
        }.Where(value => !string.IsNullOrWhiteSpace(value) && value != "00");
        return string.Join("-", corners);
    }

    private static string CourseName(string code)
    {
        return code switch
        {
            "01" => "札幌",
            "02" => "函館",
            "03" => "福島",
            "04" => "新潟",
            "05" => "東京",
            "06" => "中山",
            "07" => "中京",
            "08" => "京都",
            "09" => "阪神",
            "10" => "小倉",
            _ => code
        };
    }

    private static string? SurfaceFromTrackCode(string code)
    {
        if (string.IsNullOrWhiteSpace(code) || code == "00")
        {
            return null;
        }
        if (code.StartsWith("1") || code.StartsWith("2"))
        {
            return "芝";
        }
        if (code.StartsWith("3"))
        {
            return "ダート";
        }
        if (code.StartsWith("5") || code.StartsWith("6"))
        {
            return "障害";
        }
        return null;
    }

    private static string? DirectionFromTrackCode(string code)
    {
        return code switch
        {
            "11" or "12" or "13" or "14" or "15" or "16" or "17" or "18" or "19" => "右",
            "21" or "22" or "23" or "24" or "25" or "26" or "27" or "28" or "29" => "左",
            _ => null
        };
    }

    private static string? GroundCondition(string code)
    {
        return code switch
        {
            "1" => "良",
            "2" => "稍重",
            "3" => "重",
            "4" => "不良",
            _ => null
        };
    }

    private static string? Weather(string code)
    {
        return code switch
        {
            "1" => "晴",
            "2" => "曇",
            "3" => "雨",
            "4" => "小雨",
            "5" => "雪",
            "6" => "小雪",
            _ => null
        };
    }

    private static string? HorseSex(string code)
    {
        return code switch
        {
            "1" => "牡",
            "2" => "牝",
            "3" => "セ",
            _ => null
        };
    }
}
