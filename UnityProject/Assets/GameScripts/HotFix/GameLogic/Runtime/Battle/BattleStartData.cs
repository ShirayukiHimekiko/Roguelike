using System.Collections.Generic;

namespace GameLogic
{
    /// <summary>单机战斗开局时提交的配置。</summary>
    public sealed class BattleStartData
    {
        /// <summary>由本地玩家操控的单位 ID。</summary>
        public long LocalPlayerId { get; }

        /// <summary>按逻辑更新顺序排列的初始单位。</summary>
        public IReadOnlyList<BattleUnitStartData> Units { get; }

        /// <summary>保存本地玩家及开局单位列表。</summary>
        public BattleStartData(long localPlayerId, IReadOnlyList<BattleUnitStartData> units)
        {
            LocalPlayerId = localPlayerId;
            Units = units;
        }
    }
}
