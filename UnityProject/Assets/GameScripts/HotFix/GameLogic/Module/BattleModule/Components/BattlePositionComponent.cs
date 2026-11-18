using Entitas;
using Entitas.CodeGeneration.Attributes;

namespace GameLogic
{
    /// <summary>单位的三维定点位置。</summary>
    [Context("Battle")]
    public sealed class BattlePositionComponent : IComponent
    {
        public FixedVector3 Position;
    }
}
