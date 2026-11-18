using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 战斗开始。建立当局时钟后立即进入战斗进行。
    /// </summary>
    internal sealed class StartBattleState : BattleRoomState
    {
        /// <summary>
        /// 采集开战时间锚点并初始化第零帧的调度。
        /// </summary>
        protected override void OnEnter(IFsm<BattleRoom> fsm)
        {
            BattleRoom room = fsm.Owner;
            room.Clock = new FixedTimeCounter(FixedTimeCounter.ReadMilliseconds());
            room.Updater = new BattleUpdater();

            ChangeState<RunBattleState>(fsm);
        }
    }
}
