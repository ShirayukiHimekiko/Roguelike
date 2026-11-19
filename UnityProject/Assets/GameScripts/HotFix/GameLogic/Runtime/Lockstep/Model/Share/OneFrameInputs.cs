using System;
using System.Collections.Generic;

namespace GameLogic
{
    /// <summary>帧输入的只读视图。接入方在当帧回调内同步读取。</summary>
    public readonly struct OneFrameInputs
    {
        private readonly PlayerFrameInput[] _inputs;
        private readonly int _offset;
        private readonly IReadOnlyDictionary<long, int> _playerSlots;

        /// <summary>读取本帧指定玩家的封存输入。</summary>
        public bool TryGetInput(long playerId, out PlayerFrameInput input)
        {
            if (_playerSlots.TryGetValue(playerId, out int slot))
            {
                input = _inputs[_offset + slot];
                return true;
            }

            input = default;
            return false;
        }

        /// <summary>引用房间在本帧同步消费的输入槽。</summary>
        internal OneFrameInputs(PlayerFrameInput[] inputs, int offset, IReadOnlyDictionary<long, int> playerSlots = null)
        {
            _inputs = inputs;
            _offset = offset;
            _playerSlots = playerSlots;
        }

        /// <summary>复制当前帧的输入值到指定流转或历史空间。</summary>
        internal void CopyTo(PlayerFrameInput[] destination, int offset, int count)
        {
            Array.Copy(_inputs, _offset, destination, offset, count);
        }
    }
}
