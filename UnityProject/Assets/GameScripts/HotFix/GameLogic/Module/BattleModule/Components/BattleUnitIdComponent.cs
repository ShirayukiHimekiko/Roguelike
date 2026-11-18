using Entitas;
using Entitas.CodeGeneration.Attributes;

namespace GameLogic
{
    /// <summary>单位所属玩家的稳定 ID。</summary>
    [Context("Battle")]
    public sealed class BattleUnitIdComponent : IComponent
    {
        public long PlayerId;
    }
}
