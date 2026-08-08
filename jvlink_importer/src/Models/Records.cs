namespace JvLinkImporter.Models;

public interface IJvRecord;

public sealed record RaceRecord(
    string RaceId,
    DateOnly RaceDate,
    string Course,
    int RaceNo,
    string? RaceName,
    string? Surface,
    int? Distance,
    string? Direction,
    string? Weather,
    string? GroundCondition,
    string? RaceClass,
    string? RaceGrade,
    string? AgeCondition,
    string? SexCondition,
    int? FieldSize,
    string? StartTime) : IJvRecord;

public sealed record EntryRecord(
    string RaceId,
    string HorseId,
    string? HorseName,
    int? HorseNo,
    int? FrameNo,
    string? JockeyId,
    string? JockeyName,
    string? TrainerId,
    string? TrainerName,
    int? HorseAge,
    string? HorseSex,
    double? WeightCarried,
    double? BodyWeight,
    double? BodyWeightDiff,
    double? OddsWin,
    double? OddsPlaceMin,
    double? OddsPlaceMax,
    int? Popularity) : IJvRecord;

public sealed record ResultRecord(
    string RaceId,
    string HorseId,
    int? FinishPosition,
    string? FinishTime,
    string? Margin,
    string? CornerOrder,
    double? Last3F) : IJvRecord;

public sealed record PayoutRecord(
    string RaceId,
    string TicketType,
    string Combination,
    int? Payout) : IJvRecord;

public sealed record OddsRecord(
    string RaceId,
    int HorseNo,
    double? OddsWin,
    double? OddsPlaceMin,
    double? OddsPlaceMax,
    int? Popularity) : IJvRecord;

public sealed record HorseHistoryRecord(
    string RaceId,
    DateOnly RaceDate,
    string HorseId,
    string? HorseName,
    string? Course,
    string? Surface,
    int? Distance,
    string? GroundCondition,
    string? RaceClass,
    int? FieldSize,
    int? FinishPosition,
    double? Margin,
    double? Last3F,
    int? Popularity,
    double? WeightCarried,
    double? BodyWeight,
    double? BodyWeightDiff,
    string? JockeyId,
    string? TrainerId) : IJvRecord;
