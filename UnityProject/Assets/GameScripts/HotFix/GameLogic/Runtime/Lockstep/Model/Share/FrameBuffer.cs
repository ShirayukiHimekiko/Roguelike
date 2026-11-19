using System;
using System.Collections.Generic;

namespace GameLogic
{
    /// <summary>收集下帧输入，并按帧号保存已确定输入的环形历史。</summary>
    internal sealed class FrameBuffer
    {
        private const int DEFAULT_HISTORY_CAPACITY = 60 * (1000 / FixedTimeCounter.FRAME_INTERVAL_MS);

        private readonly PlayerFrameInput[] _pendingInputs;
        private readonly bool[] _hasPendingInput;
        private readonly PlayerFrameInput[] _confirmedInputs;
        private readonly int[] _historyFrames;
        private readonly PlayerFrameInput[] _historyInputs;
        private readonly WorldSnapshot[] _snapshots;
        private readonly IReadOnlyDictionary<long, int> _playerSlots;

        /// <summary>按当局玩家表分配输入槽和历史空间，默认保留 60 秒逻辑帧。</summary>
        internal FrameBuffer(IReadOnlyDictionary<long, int> playerSlots, int historyCapacity = DEFAULT_HISTORY_CAPACITY)
        {
            _playerSlots = playerSlots;
            int playerCount = playerSlots.Count;
            _pendingInputs = new PlayerFrameInput[playerCount];
            _hasPendingInput = new bool[playerCount];
            _confirmedInputs = new PlayerFrameInput[playerCount];
            _historyFrames = new int[historyCapacity];
            _historyInputs = new PlayerFrameInput[historyCapacity * playerCount];
            _snapshots = new WorldSnapshot[historyCapacity];
            Array.Fill(_historyFrames, -1);
        }

        /// <summary>提交该槽下一帧的输入。同一帧内保留最后一次提交。</summary>
        internal void Submit(int slot, PlayerFrameInput input)
        {
            _pendingInputs[slot] = input;
            _hasPendingInput[slot] = true;
        }

        /// <summary>合入本帧提交并保存已确定输入。缺失的槽沿用最近的确认值。</summary>
        internal OneFrameInputs Seal(int frame)
        {
            for (int slot = 0; slot < _confirmedInputs.Length; slot++)
            {
                if (_hasPendingInput[slot])
                {
                    _confirmedInputs[slot] = _pendingInputs[slot];
                    _hasPendingInput[slot] = false;
                }
            }

            return Store(frame, new OneFrameInputs(_confirmedInputs, 0));
        }

        /// <summary>保存已确定输入，供权威和回放共用。</summary>
        internal OneFrameInputs Store(int frame, OneFrameInputs inputs)
        {
            int historySlot = frame % _historyFrames.Length;
            int offset = historySlot * _confirmedInputs.Length;
            inputs.CopyTo(_historyInputs, offset, _confirmedInputs.Length);
            _historyFrames[historySlot] = frame;
            _snapshots[historySlot] = null;
            return new OneFrameInputs(_historyInputs, offset, _playerSlots);
        }

        /// <summary>保存已封存帧的演算前快照。</summary>
        internal void StoreSnapshot(WorldSnapshot snapshot)
        {
            _snapshots[snapshot.Frame % _historyFrames.Length] = snapshot;
        }

        /// <summary>返回仍在历史中的帧前快照。</summary>
        internal bool TryGetSnapshot(int frame, out WorldSnapshot snapshot)
        {
            snapshot = null;
            if (TryGetHistorySlot(frame, out int slot))
            {
                snapshot = _snapshots[slot];
            }

            return snapshot != null;
        }

        /// <summary>按帧号和玩家槽读取仍在历史中的输入值。</summary>
        internal bool TryGetInput(int frame, int playerSlot, out PlayerFrameInput input)
        {
            input = default;
            if (!TryGetHistorySlot(frame, out int historySlot))
            {
                return false;
            }

            input = _historyInputs[historySlot * _confirmedInputs.Length + playerSlot];
            return true;
        }

        /// <summary>检查外部帧号是否仍占用其环形槽。</summary>
        private bool TryGetHistorySlot(int frame, out int slot)
        {
            slot = 0;
            if (frame < 0)
            {
                return false;
            }

            slot = frame % _historyFrames.Length;
            return _historyFrames[slot] == frame;
        }
    }
}
