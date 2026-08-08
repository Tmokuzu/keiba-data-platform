using System.Globalization;
using System.Text;

namespace JvLinkImporter.Parsing;

public static class FixedWidth
{
    private static readonly Encoding ShiftJis = Encoding.GetEncoding("shift_jis");
    private static readonly Encoding Windows1252 = Encoding.GetEncoding(1252);

    public static string Text(string raw, int start, int length)
    {
        if (start >= raw.Length)
        {
            return "";
        }

        var safeLength = Math.Min(length, raw.Length - start);
        return DecodeShiftJisMojibake(raw.Substring(start, safeLength))
            .Trim('\0', ' ', '　');
    }

    public static int? Int(string raw, int start, int length)
    {
        var text = Text(raw, start, length);
        return int.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value)
            ? value
            : null;
    }

    public static double? Double(string raw, int start, int length, double scale = 1)
    {
        var text = Text(raw, start, length);
        return double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out var value)
            ? value / scale
            : null;
    }

    public static DateOnly? Date(string raw, int start, int length)
    {
        var text = Text(raw, start, length);
        return DateOnly.TryParseExact(text, "yyyyMMdd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var value)
            ? value
            : null;
    }

    private static string DecodeShiftJisMojibake(string value)
    {
        if (string.IsNullOrEmpty(value))
        {
            return value;
        }

        var bytes = new List<byte>(value.Length);
        for (var i = 0; i < value.Length; i++)
        {
            var character = value[i];
            if (character <= byte.MaxValue)
            {
                bytes.Add((byte)character);
                continue;
            }

            var encoded = Windows1252.GetBytes([character]);
            bytes.Add(encoded.Length > 0 ? encoded[0] : (byte)'?');
        }

        return ShiftJis.GetString(bytes.ToArray());
    }
}
