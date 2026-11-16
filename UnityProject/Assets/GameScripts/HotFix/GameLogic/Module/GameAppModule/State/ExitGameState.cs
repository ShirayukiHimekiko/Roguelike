using TEngine;

namespace GameLogic
{
    public sealed class ExitGameState : GameAppState
    {
        protected override void OnEnter(IFsm<GameAppManager> fsm)
        {
            ChangeState<EndGameState>(fsm);
        }
    }
}
