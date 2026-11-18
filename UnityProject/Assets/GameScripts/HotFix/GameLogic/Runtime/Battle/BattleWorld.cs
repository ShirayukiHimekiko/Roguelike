using System.Collections.Generic;
using Entitas;

namespace GameLogic
{
    /// <summary>持有当局 Entitas 世界、单位和固定顺序的系统树。</summary>
    internal sealed class BattleWorld
    {
        private readonly BattleContext _context = new BattleContext();
        private readonly Systems _systems = new Systems();
        private readonly BattleEntity[] _units;
        private readonly Dictionary<long, BattleEntity> _unitsByPlayerId;

        /// <summary>世界下一次待执行的帧号。</summary>
        internal int Frame { get; private set; }

        /// <summary>按开战数据顺序创建单位，并初始化当局系统树。</summary>
        internal BattleWorld(BattleUnitStartData[] initialUnits)
        {
            _units = new BattleEntity[initialUnits.Length];
            _unitsByPlayerId = new Dictionary<long, BattleEntity>(initialUnits.Length);
            for (int index = 0; index < initialUnits.Length; index++)
            {
                BattleUnitStartData initialUnit = initialUnits[index];
                BattleEntity entity = _context.CreateEntity();
                entity.AddGameLogicBattleUnitId(initialUnit.PlayerId);
                entity.AddGameLogicBattleUnitInput(default);
                entity.AddGameLogicBattlePosition(initialUnit.Position);
                entity.AddGameLogicBattleRotation(initialUnit.Rotation);
                _units[index] = entity;
                _unitsByPlayerId.Add(initialUnit.PlayerId, entity);
            }

            // 在这里按执行顺序注册具体战斗系统。
            _systems.Initialize();
        }

        /// <summary>把封存输入写入与开局顺序对应的单位组件。</summary>
        internal void ApplyInputs(BattleFrameInputs inputs)
        {
            for (int slot = 0; slot < _units.Length; slot++)
            {
                _units[slot].ReplaceGameLogicBattleUnitInput(inputs[slot]);
            }
        }

        /// <summary>执行并清理一帧，再推进世界帧号。</summary>
        internal void Tick()
        {
            _systems.Execute();
            _systems.Cleanup();
            Frame++;
        }

        /// <summary>按玩家 ID 读取单位当前的值类型状态。</summary>
        internal bool TryGetUnitState(long playerId, out BattleUnitState state)
        {
            if (_unitsByPlayerId.TryGetValue(playerId, out BattleEntity unit))
            {
                state = new BattleUnitState(
                    unit.gameLogicBattlePosition.Position,
                    unit.gameLogicBattleRotation.Rotation,
                    unit.gameLogicBattleUnitInput.Input);
                return true;
            }

            state = default;
            return false;
        }

        /// <summary>拆除系统、实体和玩家 ID 索引。</summary>
        internal void Release()
        {
            _systems.TearDown();
            _context.DestroyAllEntities();
            _unitsByPlayerId.Clear();
        }
    }
}
