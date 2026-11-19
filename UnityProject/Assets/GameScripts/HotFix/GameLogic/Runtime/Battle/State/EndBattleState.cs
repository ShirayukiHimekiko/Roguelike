using Cysharp.Threading.Tasks;
using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 战斗结束。房间进入该状态后由所有者释放。
    /// </summary>
    internal sealed class EndBattleState : BattleManagerState
    {
        /// <summary>停止轮询，由当前战斗所有者完成收尾。</summary>
        protected override void OnEnter(IFsm<BattleManager> fsm)
        {
            fsm.Owner.ExitBattleAsync().Forget();
        }
    }
}
