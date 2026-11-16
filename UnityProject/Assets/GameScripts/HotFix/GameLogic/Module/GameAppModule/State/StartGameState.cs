using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 进入即切到运行；Start 只作为启动入口，不在这里停留。
    /// </summary>
    public sealed class StartGameState : GameAppState
    {
        protected override void OnEnter(IFsm<GameAppManager> fsm)
        {
            ChangeState<RunGameState>(fsm);
        }
    }
}
