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
    /// <summary>战斗世界使用的定点四元数。</summary>
    public readonly struct FixedQuaternion
    {
        /// <summary>无旋转。</summary>
        public static readonly FixedQuaternion Identity = new FixedQuaternion(
            FixedPoint.Zero, FixedPoint.Zero, FixedPoint.Zero, FixedPoint.One);

        /// <summary>X 分量。</summary>
        public FixedPoint X { get; }

        /// <summary>Y 分量。</summary>
        public FixedPoint Y { get; }

        /// <summary>Z 分量。</summary>
        public FixedPoint Z { get; }

        /// <summary>W 分量。</summary>
        public FixedPoint W { get; }

        /// <summary>建立定点四元数。</summary>
        public FixedQuaternion(FixedPoint x, FixedPoint y, FixedPoint z, FixedPoint w)
        {
            X = x;
            Y = y;
            Z = z;
            W = w;
        }

        /// <summary>按前方向和上方向建立定点旋转。</summary>
        internal static FixedQuaternion LookRotation(FixedVector3 direction, FixedVector3 upwards)
        {
            // 正交基的三个向量分别对应上游旋转矩阵的第 1、2、3 行。
            FixedVector3 forward = direction.Normalized();
            FixedVector3 right = FixedVector3.Cross(upwards, forward).Normalized();
            FixedVector3 up = FixedVector3.Cross(forward, right);
            FixedPoint trace = right.X + up.Y + forward.Z;

            if (trace > FixedPoint.Zero)
            {
                FixedPoint root = FixedPoint.Sqrt(trace + FixedPoint.One);
                FixedPoint factor = FixedPoint.Half / root;
                return new FixedQuaternion(
                    (up.Z - forward.Y) * factor,
                    (forward.X - right.Z) * factor,
                    (right.Y - up.X) * factor,
                    root * FixedPoint.Half);
            }

            if (right.X >= up.Y && right.X >= forward.Z)
            {
                FixedPoint root = FixedPoint.Sqrt(FixedPoint.One + right.X - up.Y - forward.Z);
                FixedPoint factor = FixedPoint.Half / root;
                return new FixedQuaternion(
                    FixedPoint.Half * root,
                    (right.Y + up.X) * factor,
                    (right.Z + forward.X) * factor,
                    (up.Z - forward.Y) * factor);
            }

            if (up.Y > forward.Z)
            {
                FixedPoint root = FixedPoint.Sqrt(FixedPoint.One + up.Y - right.X - forward.Z);
                FixedPoint factor = FixedPoint.Half / root;
                return new FixedQuaternion(
                    (up.X + right.Y) * factor,
                    FixedPoint.Half * root,
                    (forward.Y + up.Z) * factor,
                    (forward.X - right.Z) * factor);
            }

            FixedPoint zRoot = FixedPoint.Sqrt(FixedPoint.One + forward.Z - right.X - up.Y);
            FixedPoint zFactor = FixedPoint.Half / zRoot;
            return new FixedQuaternion(
                (forward.X + right.Z) * zFactor,
                (forward.Y + up.Z) * zFactor,
                FixedPoint.Half * zRoot,
                (right.Y - up.X) * zFactor);
        }
    }
}
