using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 状态基类：对外公开切换方法，Manager 不需要知道具体状态类型。
    /// </summary>
    public abstract class GameAppState : FsmState<GameAppManager>
    {
        public void SwitchState<TState>(IFsm<GameAppManager> fsm) where TState : FsmState<GameAppManager>
        {
#if UNITY_EDITOR
            
            if (GetType() == typeof(TState))
            {
                return;
            }
#endif
            
            ChangeState<TState>(fsm);
        }
    }
}
