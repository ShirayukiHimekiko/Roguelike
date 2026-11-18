using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 供战斗房间从当前状态转入结束状态。
    /// </summary>
    internal abstract class BattleRoomState : FsmState<BattleRoom>
    {
        /// <summary>
        /// 将当局状态机切到战斗结束。
        /// </summary>
        internal void EndBattle(IFsm<BattleRoom> fsm)
        {
            ChangeState<EndBattleState>(fsm);
        }
    }
}
