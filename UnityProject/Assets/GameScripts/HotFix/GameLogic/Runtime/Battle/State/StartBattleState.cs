using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 战斗开始。建立当局时钟后立即进入战斗进行。
    /// </summary>
    internal sealed class StartBattleState : BattleManagerState
    {
        /// <summary>
        /// 采集开战时间锚点并初始化第零帧的调度。
        /// </summary>
        protected override void OnEnter(IFsm<BattleManager> fsm)
        {
            fsm.Owner.Room.Start(FixedTimeCounter.ReadMilliseconds());
            ChangeState<RunBattleState>(fsm);
        }
    }
}
