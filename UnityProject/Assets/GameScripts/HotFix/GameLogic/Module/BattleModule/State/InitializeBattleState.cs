using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 战斗初始化。完成当局准备后进入战斗开始。
    /// </summary>
    internal sealed class InitializeBattleState : BattleRoomState
    {
        /// <summary>
        /// 当前骨架的准备流程同步完成。
        /// </summary>
        protected override void OnEnter(IFsm<BattleRoom> fsm)
        {
            ChangeState<StartBattleState>(fsm);
        }
    }
}
