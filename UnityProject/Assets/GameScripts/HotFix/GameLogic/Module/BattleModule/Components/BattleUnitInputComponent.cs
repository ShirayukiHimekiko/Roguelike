using Entitas;
using Entitas.CodeGeneration.Attributes;

namespace GameLogic
{
    /// <summary>房间已确定的单位当帧输入。</summary>
    [Context("Battle")]
    public sealed class BattleUnitInputComponent : IComponent
    {
        public BattleInput Input;
    }
}
