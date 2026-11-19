using System;

namespace GameLogic
{
    /// <summary>对已规范编码的字节计算 64 位 FNV-1a 指纹。</summary>
    internal static class StableBytesHash
    {
        internal static ulong Compute(ReadOnlySpan<byte> data)
        {
            ulong hash = 14695981039346656037UL;
            foreach (byte value in data)
            {
                hash = unchecked((hash ^ value) * 1099511628211UL);
            }

            return hash;
        }
    }
}
