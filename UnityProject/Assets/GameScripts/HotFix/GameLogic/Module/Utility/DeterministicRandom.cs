using System.IO;

namespace GameLogic
{
    /// <summary>使用 MT19937 单种子算法生成可恢复的 31 位整数序列。</summary>
    internal sealed class DeterministicRandom
    {
        private const int STATE_COUNT = 624;
        private const int STATE_OFFSET = 397;
        private readonly uint[] _state = new uint[STATE_COUNT];
        private int _index;

        /// <summary>以单个种子建立初始序列。</summary>
        internal DeterministicRandom(uint seed)
        {
            _state[0] = seed;
            for (int index = 1; index < STATE_COUNT; index++)
            {
                uint previous = _state[index - 1];
                _state[index] = unchecked(1812433253u * (previous ^ (previous >> 30)) + (uint)index);
            }

            _index = STATE_COUNT;
        }

        /// <summary>从快照恢复状态与下一输出位置。</summary>
        internal DeterministicRandom(BinaryReader reader)
        {
            _index = reader.ReadInt32();
            for (int index = 0; index < STATE_COUNT; index++)
            {
                _state[index] = reader.ReadUInt32();
            }
        }

        /// <summary>生成与上游整数 Next 相同的 31 位值。</summary>
        internal int Next()
        {
            if (_index == STATE_COUNT)
            {
                for (int index = 0; index < STATE_COUNT; index++)
                {
                    uint bits = (_state[index] & 0x80000000u) |
                        (_state[(index + 1) % STATE_COUNT] & 0x7fffffffu);
                    uint feedback = (bits & 1u) != 0 ? 0x9908b0dfu : 0u;
                    _state[index] = _state[(index + STATE_OFFSET) % STATE_COUNT] ^ (bits >> 1) ^ feedback;
                }

                _index = 0;
            }

            uint value = _state[_index++];
            value ^= value >> 11;
            value ^= (value << 7) & 0x9d2c5680u;
            value ^= (value << 15) & 0xefc60000u;
            value ^= value >> 18;
            return (int)(value >> 1);
        }

        /// <summary>写入下一输出位置和完整内部状态。</summary>
        internal void Write(BinaryWriter writer)
        {
            writer.Write(_index);
            foreach (uint value in _state)
            {
                writer.Write(value);
            }
        }
    }
}
