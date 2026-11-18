using Entitas;
using Entitas.CodeGeneration.Attributes;

namespace GameLogic
{
    /// <summary>单位的定点旋转。</summary>
    [Context("Battle")]
    public sealed class BattleRotationComponent : IComponent
    {
        public FixedQuaternion Rotation;
    }
}
