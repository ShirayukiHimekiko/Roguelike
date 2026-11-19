using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 战斗初始化。完成当局准备后进入战斗开始。
    /// </summary>
    internal sealed class InitializeBattleState : BattleManagerState
    {
        /// <summary>准备完成后建立世界、初始化系统，再进入开战。</summary>
        protected override void OnUpdate(IFsm<BattleManager> fsm, float elapseSeconds, float realElapseSeconds)
        {
            BattleManager manager = fsm.Owner;
            LocalSceneReadiness readiness = manager.GetSceneReadiness();
            if (manager.IsExitRequested() || readiness == LocalSceneReadiness.Unavailable)
            {
                ChangeState<EndBattleState>(fsm);
                return;
            }

            if (readiness != LocalSceneReadiness.Ready)
            {
                return;
            }

            manager.InitializeRoomWorld();
            ChangeState<StartBattleState>(fsm);
        }
    }
}
