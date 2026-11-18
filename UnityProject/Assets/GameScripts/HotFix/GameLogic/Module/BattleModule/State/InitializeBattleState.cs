using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 战斗初始化。完成当局准备后进入战斗开始。
    /// </summary>
    internal sealed class InitializeBattleState : BattleRoomState
    {
        /// <summary>
        /// 建立当局 Entitas 世界和本地输入槽。
        /// </summary>
        protected override void OnEnter(IFsm<BattleRoom> fsm)
        {
            BattleRoom room = fsm.Owner;
            room.World = new BattleWorld(room.InitialUnits);
            room.FrameBuffer = new BattleFrameBuffer(room.InitialUnits.Length);
            ChangeState<StartBattleState>(fsm);
        }
    }
}
