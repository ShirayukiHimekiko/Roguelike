using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 战斗进行。由 TEngine 每次轮询驱动当局帧更新器。
    /// </summary>
    internal sealed class RunBattleState : BattleManagerState
    {
        /// <summary>
        /// 用当局的整数毫秒时钟判断下一帧是否到期。
        /// </summary>
        protected override void OnUpdate(IFsm<BattleManager> fsm, float elapseSeconds, float realElapseSeconds)
        {
            BattleManager manager = fsm.Owner;
            if (manager.GetSceneReadiness() == LocalSceneReadiness.Unavailable)
            {
                ChangeState<EndBattleState>(fsm);
                return;
            }

            manager.UpdateRoom(FixedTimeCounter.ReadMilliseconds());
            if (manager.Room.IsFinished || manager.IsExitRequested())
            {
                ChangeState<EndBattleState>(fsm);
                return;
            }

            manager.UpdateReplayCommands();
        }
    }
}
