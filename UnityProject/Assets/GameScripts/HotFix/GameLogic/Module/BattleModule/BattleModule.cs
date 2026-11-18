using System;
using System.Collections.Generic;

namespace GameLogic
{
    /// <summary>
    /// 管理当前战斗房间的创建和释放。
    /// </summary>
    public sealed class BattleModule : Singleton<BattleModule>
    {
        private BattleRoom _currentRoom;

        /// <summary>
        /// 创建并启动一局战斗，返回本局房间。
        /// </summary>
        /// <param name="startData">本地玩家和按更新顺序排列的初始单位。</param>
        /// <exception cref="ArgumentNullException">缺少开战数据。</exception>
        /// <exception cref="ArgumentException">单位配置缺失、玩家 ID 重复或本地玩家未配置。</exception>
        /// <exception cref="InvalidOperationException">已有一局战斗尚未结束。</exception>
        public BattleRoom StartBattle(BattleStartData startData)
        {
            if (_currentRoom != null)
            {
                throw new InvalidOperationException("当前战斗结束后才能创建新战斗。");
            }

            if (startData == null)
            {
                throw new ArgumentNullException(nameof(startData));
            }

            IReadOnlyList<BattleUnitStartData> units = startData.Units;
            if (units == null)
            {
                throw new ArgumentException("缺少初始单位列表。", nameof(startData));
            }

            var initialUnits = new BattleUnitStartData[units.Count];
            var playerIds = new HashSet<long>();
            int localUnitSlot = -1;
            for (int slot = 0; slot < initialUnits.Length; slot++)
            {
                BattleUnitStartData unit = units[slot];
                if (!playerIds.Add(unit.PlayerId))
                {
                    throw new ArgumentException("初始单位的玩家 ID 重复。", nameof(startData));
                }

                initialUnits[slot] = unit;
                if (unit.PlayerId == startData.LocalPlayerId)
                {
                    localUnitSlot = slot;
                }
            }

            if (localUnitSlot < 0)
            {
                throw new ArgumentException("初始单位中缺少本地玩家。", nameof(startData));
            }

            _currentRoom = new BattleRoom(initialUnits, localUnitSlot);
            return _currentRoom;
        }

        /// <summary>
        /// 为当前房间的本地玩家提交下次推进要使用的输入。
        /// </summary>
        public bool SubmitLocalInput(BattleRoom room, BattleInput input)
        {
            if (room == null || room != _currentRoom)
            {
                return false;
            }

            room.FrameBuffer.Submit(room.LocalUnitSlot, input);
            return true;
        }

        /// <summary>
        /// 停止并释放当局的帧更新器，随后进场流程可以清理业务和场景。
        /// </summary>
        public bool EndBattle(BattleRoom room)
        {
            if (room == null || room != _currentRoom)
            {
                return false;
            }

            _currentRoom = null;
            room.Close();
            return true;
        }

        /// <summary>
        /// 随游戏逻辑释放当前房间。
        /// </summary>
        protected override void OnRelease()
        {
            if (_currentRoom != null)
            {
                _currentRoom.Release();
                _currentRoom = null;
            }
        }
    }
}
