namespace GameLogic
{
    /// <summary>一个战斗单位的初始数据。</summary>
    public readonly struct BattleUnitStartData
    {
        /// <summary>单位所属玩家的稳定 ID。</summary>
        public long PlayerId { get; }

        /// <summary>初始定点位置。</summary>
        public FixedVector3 Position { get; }

        /// <summary>初始定点旋转。</summary>
        public FixedQuaternion Rotation { get; }

        /// <summary>保存单位开局数据。</summary>
        public BattleUnitStartData(long playerId, FixedVector3 position, FixedQuaternion rotation)
        {
            PlayerId = playerId;
            Position = position;
            Rotation = rotation;
        }
    }
}
