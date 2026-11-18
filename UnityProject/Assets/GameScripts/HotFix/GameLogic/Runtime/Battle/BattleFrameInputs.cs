namespace GameLogic
{
    /// <summary>本帧确定后的输入，按开局时确定的单位槽访问。</summary>
    internal readonly struct BattleFrameInputs
    {
        private readonly BattleInput[] _inputs;

        /// <summary>读取所属单位的输入值。</summary>
        internal BattleInput this[int slot]
        {
            get { return _inputs[slot]; }
        }

        /// <summary>引用房间在本帧同步消费的输入槽。</summary>
        internal BattleFrameInputs(BattleInput[] inputs)
        {
            _inputs = inputs;
        }
    }
}
