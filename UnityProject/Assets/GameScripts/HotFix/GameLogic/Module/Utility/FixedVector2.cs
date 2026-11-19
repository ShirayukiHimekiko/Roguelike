/*
MIT License
Copyright © 2006 The Mono.Xna Team

All rights reserved.

Authors
 * Alan McGovern

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

// 改写版本，保留上游战斗路径所需的定点运算。
namespace GameLogic
{
    /// <summary>二维定点向量，用于战斗移动输入。</summary>
    public readonly struct FixedVector2
    {
        /// <summary>X 分量。</summary>
        public FixedPoint X { get; }

        /// <summary>Y 分量。</summary>
        public FixedPoint Y { get; }

        /// <summary>建立二维定点向量。</summary>
        public FixedVector2(FixedPoint x, FixedPoint y)
        {
            X = x;
            Y = y;
        }

        /// <summary>计算长度平方。</summary>
        public FixedPoint LengthSquared()
        {
            return X * X + Y * Y;
        }

        /// <summary>按定点长度归一化方向。</summary>
        public FixedVector2 Normalized()
        {
            return this / FixedPoint.Sqrt(LengthSquared());
        }

        /// <summary>按定点标量缩放。</summary>
        public static FixedVector2 operator *(FixedVector2 vector, FixedPoint factor)
        {
            return new FixedVector2(vector.X * factor, vector.Y * factor);
        }

        /// <summary>先求定点倒数，再乘各分量。</summary>
        public static FixedVector2 operator /(FixedVector2 vector, FixedPoint divisor)
        {
            return vector * (FixedPoint.One / divisor);
        }
    }
}
