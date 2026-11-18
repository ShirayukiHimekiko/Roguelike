namespace GameLogic
{
    /// <summary>收集下帧输入并保留上一帧已经确定的输入。</summary>
    internal sealed class BattleFrameBuffer
    {
        private readonly BattleInput[] _pendingInputs;
        private readonly bool[] _hasPendingInput;
        private readonly BattleInput[] _confirmedInputs;

        /// <summary>按开战时确定的单位数分配输入槽。</summary>
        internal BattleFrameBuffer(int unitCount)
        {
            _pendingInputs = new BattleInput[unitCount];
            _hasPendingInput = new bool[unitCount];
            _confirmedInputs = new BattleInput[unitCount];
        }

        /// <summary>提交该槽下一帧的输入。同一帧内保留最后一次提交。</summary>
        internal void Submit(int slot, BattleInput input)
        {
            _pendingInputs[slot] = input;
            _hasPendingInput[slot] = true;
        }

        /// <summary>合入本帧提交。缺失的槽继承上一帧，首帧为默认值。</summary>
        internal BattleFrameInputs Seal()
        {
            for (int slot = 0; slot < _confirmedInputs.Length; slot++)
            {
                if (_hasPendingInput[slot])
                {
                    _confirmedInputs[slot] = _pendingInputs[slot];
                    _hasPendingInput[slot] = false;
                }
            }

            return new BattleFrameInputs(_confirmedInputs);
        }
    }
}
