using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 战斗进行。由 TEngine 每次轮询驱动当局帧更新器。
    /// </summary>
    internal sealed class RunBattleState : BattleRoomState
    {
        /// <summary>
        /// 用当局的整数毫秒时钟判断下一帧是否到期。
        /// </summary>
        protected override void OnUpdate(IFsm<BattleRoom> fsm, float elapseSeconds, float realElapseSeconds)
        {
            BattleRoom room = fsm.Owner;
            room.Updater.Update(room.Clock, FixedTimeCounter.ReadMilliseconds(), room.ExecuteTick);
        }
    }
}
