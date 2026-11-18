namespace GameLogic
{
    /// <summary>供查询和视图读取的当局单位状态。</summary>
    public readonly struct BattleUnitState
    {
        /// <summary>单位的定点位置。</summary>
        public FixedVector3 Position { get; }

        /// <summary>单位的定点旋转。</summary>
        public FixedQuaternion Rotation { get; }

        /// <summary>最近一次写入该单位的输入。</summary>
        public BattleInput Input { get; }

        /// <summary>保存单位位姿和输入的当前值。</summary>
        internal BattleUnitState(FixedVector3 position, FixedQuaternion rotation, BattleInput input)
        {
            Position = position;
            Rotation = rotation;
            Input = input;
        }
    }
}
