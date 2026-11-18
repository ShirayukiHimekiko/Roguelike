/* Copyright (C) <2009-2011> <Thorben Linneweber, Jitter Physics>
*
*  This software is provided 'as-is', without any express or implied
*  warranty.  In no event will the authors be held liable for any damages
*  arising from the use of this software.
*
*  Permission is granted to anyone to use this software for any purpose,
*  including commercial applications, and to alter it and redistribute it
*  freely, subject to the following restrictions:
*
*  1. The origin of this software must not be misrepresented; you must not
*      claim that you wrote the original software. If you use this software
*      in a product, an acknowledgment in the product documentation would be
*      appreciated but is not required.
*  2. Altered source versions must be plainly marked as such, and must not be
*      misrepresented as being the original software.
*  3. This notice may not be removed or altered from any source distribution.
*/

// 改写版本，保留上游战斗路径所需的定点运算。
namespace GameLogic
{
    /// <summary>三维定点向量，用于战斗位置与方向。</summary>
    public readonly struct FixedVector3
    {
        /// <summary>世界上方向。</summary>
        internal static readonly FixedVector3 Up = new FixedVector3(FixedPoint.Zero, FixedPoint.One, FixedPoint.Zero);

        /// <summary>X 分量。</summary>
        public FixedPoint X { get; }

        /// <summary>Y 分量。</summary>
        public FixedPoint Y { get; }

        /// <summary>Z 分量。</summary>
        public FixedPoint Z { get; }

        /// <summary>建立三维定点向量。</summary>
        public FixedVector3(FixedPoint x, FixedPoint y, FixedPoint z)
        {
            X = x;
            Y = y;
            Z = z;
        }

        /// <summary>定点归一化。</summary>
        internal FixedVector3 Normalized()
        {
            FixedPoint lengthSquared = X * X + Y * Y + Z * Z;
            FixedPoint factor = FixedPoint.One / FixedPoint.Sqrt(lengthSquared);
            return new FixedVector3(X * factor, Y * factor, Z * factor);
        }

        /// <summary>计算向量叉乘。</summary>
        internal static FixedVector3 Cross(FixedVector3 left, FixedVector3 right)
        {
            return new FixedVector3(
                left.Y * right.Z - left.Z * right.Y,
                left.Z * right.X - left.X * right.Z,
                left.X * right.Y - left.Y * right.X);
        }

        /// <summary>按分量相加。</summary>
        public static FixedVector3 operator +(FixedVector3 left, FixedVector3 right)
        {
            return new FixedVector3(left.X + right.X, left.Y + right.Y, left.Z + right.Z);
        }

        /// <summary>按分量相减。</summary>
        public static FixedVector3 operator -(FixedVector3 left, FixedVector3 right)
        {
            return new FixedVector3(left.X - right.X, left.Y - right.Y, left.Z - right.Z);
        }
    }
}
