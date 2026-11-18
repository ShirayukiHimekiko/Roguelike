using System;

namespace GameLogic
{
    /// <summary>
    /// 有符号 64 位定点数，低 32 位表示小数。
    /// </summary>
    public readonly struct FixedPoint : IEquatable<FixedPoint>, IComparable<FixedPoint>
    {
        private const int FRACTIONAL_BITS = 32;
        private const long RAW_ONE = 1L << FRACTIONAL_BITS;
        private const long LOW_BITS_MASK = 0xFFFFFFFFL;

        /// <summary>
        /// 定点数零。
        /// </summary>
        public static readonly FixedPoint Zero = default;

        /// <summary>
        /// 定点数一。
        /// </summary>
        public static readonly FixedPoint One = new FixedPoint(RAW_ONE);

        /// <summary>
        /// 源算法使用的最小有限值。
        /// </summary>
        public static readonly FixedPoint MinValue = new FixedPoint(long.MinValue + 2);

        /// <summary>
        /// 源算法使用的最大有限值，也是除数为零时的返回值。
        /// </summary>
        public static readonly FixedPoint MaxValue = new FixedPoint(long.MaxValue - 1);

        /// <summary>
        /// 定点数的底层整数表示。
        /// </summary>
        public long RawValue { get; }

        private FixedPoint(long rawValue)
        {
            RawValue = rawValue;
        }

        /// <summary>
        /// 将整数转换为定点数。
        /// </summary>
        public static FixedPoint FromInt(int value)
        {
            return new FixedPoint((long)value << FRACTIONAL_BITS);
        }

        /// <summary>
        /// 从底层整数表示恢复定点数。
        /// </summary>
        public static FixedPoint FromRaw(long rawValue)
        {
            return new FixedPoint(rawValue);
        }

        /// <summary>
        /// 按底层整数相加。
        /// </summary>
        public static FixedPoint operator +(FixedPoint left, FixedPoint right)
        {
            return new FixedPoint(unchecked(left.RawValue + right.RawValue));
        }

        /// <summary>
        /// 按底层整数相减。
        /// </summary>
        public static FixedPoint operator -(FixedPoint left, FixedPoint right)
        {
            return new FixedPoint(unchecked(left.RawValue - right.RawValue));
        }

        /// <summary>
        /// 对底层整数取反，遇到底层最小整数时返回最大有限值。
        /// </summary>
        public static FixedPoint operator -(FixedPoint value)
        {
            if (value.RawValue == long.MinValue)
            {
                return MaxValue;
            }

            return new FixedPoint(-value.RawValue);
        }

        /// <summary>
        /// 用 32 位高低部分相乘并恢复定点缩放。
        /// </summary>
        public static FixedPoint operator *(FixedPoint left, FixedPoint right)
        {
            long leftHigh = left.RawValue >> FRACTIONAL_BITS;
            long rightHigh = right.RawValue >> FRACTIONAL_BITS;
            ulong leftLow = (ulong)(left.RawValue & LOW_BITS_MASK);
            ulong rightLow = (ulong)(right.RawValue & LOW_BITS_MASK);

            long lowProduct = (long)((leftLow * rightLow) >> FRACTIONAL_BITS);
            long highProduct = (leftHigh * rightHigh) << FRACTIONAL_BITS;
            long mixedProduct = unchecked((long)leftLow * rightHigh + leftHigh * (long)rightLow);
            return new FixedPoint(unchecked(lowProduct + mixedProduct + highProduct));
        }

        /// <summary>
        /// 用移位长除法保留小数位，舍入后恢复商的符号。
        /// </summary>
        public static FixedPoint operator /(FixedPoint left, FixedPoint right)
        {
            long dividend = left.RawValue;
            long divisor = right.RawValue;
            if (divisor == 0)
            {
                return MaxValue;
            }

            unchecked
            {
                ulong remainder = (ulong)(dividend >= 0 ? dividend : -dividend);
                ulong divider = (ulong)(divisor >= 0 ? divisor : -divisor);
                ulong quotient = 0;
                int bitPosition = FRACTIONAL_BITS + 1;
                bool negative = (dividend ^ divisor) < 0;

                while ((divider & 0xFUL) == 0 && bitPosition >= 4)
                {
                    divider >>= 4;
                    bitPosition -= 4;
                }

                while (remainder != 0 && bitPosition >= 0)
                {
                    int shift = Math.Min(CountLeadingZeroes(remainder), bitPosition);
                    remainder <<= shift;
                    bitPosition -= shift;

                    ulong partialQuotient = remainder / divider;
                    remainder %= divider;
                    quotient += partialQuotient << bitPosition;

                    if ((partialQuotient & ~(ulong.MaxValue >> bitPosition)) != 0)
                    {
                        return negative ? MinValue : MaxValue;
                    }

                    remainder <<= 1;
                    --bitPosition;
                }

                // 多算一位用于舍入，再恢复商的符号。
                long result = (long)((quotient + 1) >> 1);
                return new FixedPoint(negative ? -result : result);
            }
        }

        /// <summary>
        /// 判断两个值的底层整数是否相同。
        /// </summary>
        public static bool operator ==(FixedPoint left, FixedPoint right)
        {
            return left.RawValue == right.RawValue;
        }

        /// <summary>
        /// 判断两个值的底层整数是否不同。
        /// </summary>
        public static bool operator !=(FixedPoint left, FixedPoint right)
        {
            return left.RawValue != right.RawValue;
        }

        /// <summary>
        /// 判断左值是否小于右值。
        /// </summary>
        public static bool operator <(FixedPoint left, FixedPoint right)
        {
            return left.RawValue < right.RawValue;
        }

        /// <summary>
        /// 判断左值是否大于右值。
        /// </summary>
        public static bool operator >(FixedPoint left, FixedPoint right)
        {
            return left.RawValue > right.RawValue;
        }

        /// <summary>
        /// 判断左值是否小于或等于右值。
        /// </summary>
        public static bool operator <=(FixedPoint left, FixedPoint right)
        {
            return left.RawValue <= right.RawValue;
        }

        /// <summary>
        /// 判断左值是否大于或等于右值。
        /// </summary>
        public static bool operator >=(FixedPoint left, FixedPoint right)
        {
            return left.RawValue >= right.RawValue;
        }

        /// <inheritdoc />
        public bool Equals(FixedPoint other)
        {
            return RawValue == other.RawValue;
        }

        /// <inheritdoc />
        public override bool Equals(object obj)
        {
            return obj is FixedPoint other && Equals(other);
        }

        /// <inheritdoc />
        public override int GetHashCode()
        {
            return RawValue.GetHashCode();
        }

        /// <inheritdoc />
        public int CompareTo(FixedPoint other)
        {
            return RawValue.CompareTo(other.RawValue);
        }

        /// <summary>
        /// 计算非零整数最高有效位之前的零位数，供长除法移位。
        /// </summary>
        private static int CountLeadingZeroes(ulong value)
        {
            int count = 0;
            while ((value & 0xF000000000000000UL) == 0)
            {
                count += 4;
                value <<= 4;
            }

            while ((value & 0x8000000000000000UL) == 0)
            {
                ++count;
                value <<= 1;
            }

            return count;
        }
    }
}
