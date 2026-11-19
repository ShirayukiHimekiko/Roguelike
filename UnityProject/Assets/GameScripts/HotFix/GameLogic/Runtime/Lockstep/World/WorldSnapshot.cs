using System.Buffers.Binary;

namespace GameLogic
{
    /// <summary>一帧演算前按稳定顺序编码的世界状态。</summary>
    internal sealed class WorldSnapshot
    {
        internal const int HEADER_SIZE = 2 * sizeof(int) + sizeof(long) + sizeof(bool);

        /// <summary>这份状态对应的下一待执行帧。</summary>
        internal int Frame { get; }

        /// <summary>以小端顺序编码的状态。</summary>
        internal byte[] Data { get; }

        /// <summary>同一字节序列的 64 位 FNV-1a 值。</summary>
        internal ulong Hash { get; }

        /// <summary>接管快照字节并计算其状态指纹。</summary>
        internal WorldSnapshot(byte[] data)
        {
            Data = data;
            Frame = BinaryPrimitives.ReadInt32LittleEndian(data);
            Hash = StableBytesHash.Compute(data);
        }
    }
}
