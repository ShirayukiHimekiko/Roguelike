using System;
using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 持有当局状态机、帧时钟和固定帧更新器。
    /// </summary>
    public sealed class BattleRoom
    {
        private IFsm<BattleRoom> _fsm;

        /// <summary>
        /// 当前正在执行或最近推进的帧。首次推进前和退局后为 -1。
        /// </summary>
        public int CurrentFrame
        {
            get { return Updater == null ? -1 : Updater.CurrentFrame; }
        }

        /// <summary>
        /// 当局同步执行一帧战斗逻辑的入口。
        /// </summary>
        internal Action<int> ExecuteTick { get; private set; }

        /// <summary>
        /// 当局开战时建立的帧时钟。
        /// </summary>
        internal FixedTimeCounter Clock { get; set; }

        /// <summary>
        /// 开战时建立，结束时释放的固定帧更新器。
        /// </summary>
        internal BattleUpdater Updater { get; set; }

        /// <summary>
        /// 保存当局逻辑入口并启动战斗初始化状态。
        /// </summary>
        internal BattleRoom(Action<int> executeTick)
        {
            ExecuteTick = executeTick;
            _fsm = GameModule.Fsm.CreateFsm(this,
                new InitializeBattleState(),
                new StartBattleState(),
                new RunBattleState(),
                new EndBattleState());
            _fsm.Start<InitializeBattleState>();
        }

        /// <summary>
        /// 进入结束状态，停止当局推进并释放状态机。
        /// </summary>
        internal void Close()
        {
            var state = (BattleRoomState)_fsm.CurrentState;
            state.EndBattle(_fsm);
            Release();
        }

        /// <summary>
        /// 注销房间状态机并释放本局资源。
        /// </summary>
        internal void Release()
        {
            GameModule.Fsm.DestroyFsm<BattleRoom>();
            _fsm = null;
            Clock = null;
            Updater = null;
            ExecuteTick = null;
        }
    }
}
