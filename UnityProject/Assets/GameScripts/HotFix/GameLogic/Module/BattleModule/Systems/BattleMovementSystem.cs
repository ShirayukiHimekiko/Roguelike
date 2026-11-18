using Entitas;

namespace GameLogic
{
    /// <summary>按当局注册顺序推进示例单位的定点移动和朝向。</summary>
    internal sealed class BattleMovementSystem : IExecuteSystem
    {
        private static readonly FixedPoint Speed = FixedPoint.FromInt(6);
        private static readonly FixedPoint StepMilliseconds = FixedPoint.FromInt(FixedTimeCounter.FRAME_INTERVAL_MS);
        private static readonly FixedPoint MillisecondsPerSecond = FixedPoint.FromInt(1000);
        private static readonly FixedPoint MinDisplacementSquared = FixedPoint.FromFloat(0.0001f);

        private readonly BattleEntity[] _units;

        /// <summary>使用开局时确定的单位更新顺序。</summary>
        internal BattleMovementSystem(BattleEntity[] units)
        {
            _units = units;
        }

        /// <summary>把本帧输入转成 XZ 平面位移，并按位移更新旋转。</summary>
        public void Execute()
        {
            foreach (BattleEntity unit in _units)
            {
                FixedVector2 direction = unit.gameLogicBattleUnitInput.Input.Direction;
                FixedVector2 displacement = direction * Speed * StepMilliseconds / MillisecondsPerSecond;
                if (displacement.LengthSquared() < MinDisplacementSquared)
                {
                    continue;
                }

                FixedVector3 oldPosition = unit.gameLogicBattlePosition.Position;
                var offset = new FixedVector3(displacement.X, FixedPoint.Zero, displacement.Y);
                FixedVector3 position = oldPosition + offset;
                unit.ReplaceGameLogicBattlePosition(position);
                unit.ReplaceGameLogicBattleRotation(FixedQuaternion.LookRotation(position - oldPosition, FixedVector3.Up));
            }
        }
    }
}
