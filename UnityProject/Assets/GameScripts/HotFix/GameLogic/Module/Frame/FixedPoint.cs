using System;
using System.Globalization;

namespace GameLogic.FixedPoint
{
    /// <summary>
    /// 用有符号 64 位整数保存十进制百万分之一刻度。
    /// </summary>
    public readonly struct Fixed64
    {
        public const long Scale = 1_000_000L;

        /// <summary>
        /// 从已经定标的原始值构造。
        /// </summary>
        public Fixed64(long raw)
        {
            Raw = raw;
        }

        /// <summary>
        /// 定标后的整数。
        /// </summary>
        public readonly long Raw;

        /// <summary>
        /// 读取最多六位小数的 invariant 十进制文本。超精度或超范围时拒绝。
        /// </summary>
        public static Fixed64 Parse(string text)
        {
            if (string.IsNullOrEmpty(text))
                throw new FormatException("定点数需要非空的十进制文本。");

            int point = text.IndexOf('.');
            if (point >= 0 && text.Length - point - 1 > 6)
                throw new FormatException("定点数最多支持六位小数。");

            const NumberStyles style = NumberStyles.AllowLeadingSign | NumberStyles.AllowDecimalPoint;
            decimal value = decimal.Parse(text, style, CultureInfo.InvariantCulture);
            return new Fixed64(checked((long)(value * Scale)));
        }
    }

    /// <summary>
    /// 两轴均使用 Fixed64 原始整数刻度的坐标。
    /// </summary>
    public readonly struct Point2
    {
        /// <summary>
        /// 按两个轴的定点原始值构造。
        /// </summary>
        public Point2(long xRaw, long yRaw)
        {
            XRaw = xRaw;
            YRaw = yRaw;
        }

        /// <summary>
        /// 横轴定点原始值。
        /// </summary>
        public readonly long XRaw;

        /// <summary>
        /// 纵轴定点原始值。
        /// </summary>
        public readonly long YRaw;
    }
}
