using System;
using System.Collections.Generic;
using GameLogic;
using TrueSync;

const long one = 1L << 32;
var totals = new Dictionary<string, (int Checked, int Mismatches)>();

void Check(string operation, string inputs, long actual, long expected)
{
    totals.TryGetValue(operation, out var counts);
    counts.Checked++;
    if (actual != expected)
    {
        if (counts.Mismatches == 0)
        {
            Console.WriteLine($"DIFF {operation} ({inputs}): project={actual}, upstream={expected}");
        }

        counts.Mismatches++;
    }

    totals[operation] = counts;
}

long[] values = { -64 * one, -3 * one - 1, -one, -one / 3, -one / 256, -1, 0, 1, one / 256, one / 3, one, 3 * one + 1, 64 * one };
foreach (long raw in values)
{
    FixedPoint x = FixedPoint.FromRaw(raw);
    FP upstreamX = FP.FromRaw(raw);
    Check("Negate", $"raw={raw}", (-x).RawValue, (-upstreamX).RawValue);
    foreach (long other in values)
    {
        FixedPoint y = FixedPoint.FromRaw(other);
        FP upstreamY = FP.FromRaw(other);
        string input = $"raw={raw},{other}";
        Check("Add", input, (x + y).RawValue, (upstreamX + upstreamY).RawValue);
        Check("Subtract", input, (x - y).RawValue, (upstreamX - upstreamY).RawValue);
        Check("Multiply", input, (x * y).RawValue, (upstreamX * upstreamY).RawValue);
        if (Math.Abs(other) >= one / 256 || (other != 0 && Math.Abs(raw) <= 1))
        {
            Check("Divide", input, (x / y).RawValue, (upstreamX / upstreamY).RawValue);
        }
    }

    if (raw >= 0)
    {
        Check("Sqrt", $"raw={raw}", FixedPoint.Sqrt(x).RawValue, FP.Sqrt(upstreamX).RawValue);
    }
}

foreach (float value in new[] { -6.25f, -0.1f, -0.0001f, 0f, 0.0001f, 0.1f, 6.25f })
{
    Check("FromFloat", $"value={value}", FixedPoint.FromFloat(value).RawValue, ((FP)value).RawValue);
}

foreach (int value in new[] { int.MinValue, -6, -1, 0, 1, 6, int.MaxValue })
{
    Check("FromInt", $"value={value}", FixedPoint.FromInt(value).RawValue, ((FP)value).RawValue);
}

foreach (long raw in new[] { -one, 0L, one })
{
    Check("DivideByZero", $"raw={raw}", (FixedPoint.FromRaw(raw) / FixedPoint.Zero).RawValue,
        (FP.FromRaw(raw) / FP.Zero).RawValue);
}

foreach ((long x, long y, long z) in new[]
{
    (one, 0L, 0L), (-one, 0L, 0L), (0L, 0L, one), (0L, 0L, -one),
    (one, one, one), (-one, one, -one), (one / 3, -2 * one, one / 256),
    (one / 256, -one / 256, 0L), (-one / 3, 0L, -one / 3)
})
{
    var vector2 = new FixedVector2(FixedPoint.FromRaw(x), FixedPoint.FromRaw(y));
    var upstream2 = new TSVector2(FP.FromRaw(x), FP.FromRaw(y));
    string input = $"raw={x},{y},{z}";
    Check("Vector2.LengthSquared", input, vector2.LengthSquared().RawValue, upstream2.LengthSquared().RawValue);
    if (x != 0 || y != 0)
    {
        var normal2 = vector2.Normalized();
        var upstreamNormal2 = upstream2.normalized;
        Check("Vector2.Normalized", $"{input}.X", normal2.X.RawValue, upstreamNormal2.x.RawValue);
        Check("Vector2.Normalized", $"{input}.Y", normal2.Y.RawValue, upstreamNormal2.y.RawValue);
    }

    var vector3 = new FixedVector3(vector2.X, vector2.Y, FixedPoint.FromRaw(z));
    var upstream3 = new TSVector(upstream2.x, upstream2.y, FP.FromRaw(z));
    var normal3 = vector3.Normalized();
    var upstreamNormal3 = upstream3.normalized;
    Check("Vector3.Normalized", $"{input}.X", normal3.X.RawValue, upstreamNormal3.x.RawValue);
    Check("Vector3.Normalized", $"{input}.Y", normal3.Y.RawValue, upstreamNormal3.y.RawValue);
    Check("Vector3.Normalized", $"{input}.Z", normal3.Z.RawValue, upstreamNormal3.z.RawValue);
    var projectCross = FixedVector3.Cross(FixedVector3.Up, vector3);
    var upstreamCross = TSVector.Cross(TSVector.up, upstream3);
    Check("Vector3.Cross", $"{input}.X", projectCross.X.RawValue, upstreamCross.x.RawValue);
    Check("Vector3.Cross", $"{input}.Y", projectCross.Y.RawValue, upstreamCross.y.RawValue);
    Check("Vector3.Cross", $"{input}.Z", projectCross.Z.RawValue, upstreamCross.z.RawValue);
    var rotation = FixedQuaternion.LookRotation(vector3, FixedVector3.Up);
    var upstreamRotation = TSQuaternion.LookRotation(upstream3, TSVector.up);
    Check("Quaternion.LookRotation", $"{input}.X", rotation.X.RawValue, upstreamRotation.x.RawValue);
    Check("Quaternion.LookRotation", $"{input}.Y", rotation.Y.RawValue, upstreamRotation.y.RawValue);
    Check("Quaternion.LookRotation", $"{input}.Z", rotation.Z.RawValue, upstreamRotation.z.RawValue);
    Check("Quaternion.LookRotation", $"{input}.W", rotation.W.RawValue, upstreamRotation.w.RawValue);
}

int checkedCount = 0;
int mismatchCount = 0;
foreach (var entry in totals)
{
    checkedCount += entry.Value.Checked;
    mismatchCount += entry.Value.Mismatches;
    Console.WriteLine($"{entry.Key}: {entry.Value.Checked} compared, {entry.Value.Mismatches} differences");
}

Console.WriteLine($"TOTAL: {checkedCount} compared, {mismatchCount} differences");
return mismatchCount == 0 ? 0 : 1;
