using System;

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
        /// <param name="executeTick">同步执行一帧战斗逻辑的入口。</param>
        /// <exception cref="ArgumentNullException">缺少帧执行入口。</exception>
        /// <exception cref="InvalidOperationException">已有一局战斗尚未结束。</exception>
        public BattleRoom StartBattle(Action<int> executeTick)
        {
            if (_currentRoom != null)
            {
                throw new InvalidOperationException("当前战斗结束后才能创建新战斗。");
            }

            if (executeTick == null)
            {
                throw new ArgumentNullException(nameof(executeTick));
            }

            _currentRoom = new BattleRoom(executeTick);
            return _currentRoom;
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
