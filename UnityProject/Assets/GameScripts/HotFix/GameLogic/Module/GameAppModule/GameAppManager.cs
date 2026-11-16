using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 生命周期唯一入口：创建并持有一个 5 状态 FSM。
    /// 同时订阅应用暂停/恢复、游戏退出和销毁。
    /// </summary>
    public sealed class GameAppManager : Singleton<GameAppManager>
    {
        private IFsm<GameAppManager> _fsm;

        private bool _isStarted;

        private GameAppState _currentState
        {
            get
            {
                if (_fsm.CurrentState is not GameAppState state)
                {
                    Log.Error($"[GameApp] current state is not GameAppState: {_fsm.CurrentState?.GetType().Name ?? "null"}.");
                
                    return null;
                }

                return state;
            }
        }

        protected override void OnInit()
        {
            _fsm = GameModule.Fsm.CreateFsm("GameApp", this,
                new StartGameState(),
                new RunGameState(),
                new PauseGameState(),
                new EndGameState(),
                new ExitGameState());

            Utility.Unity.AddOnApplicationPauseListener(OnApplicationPause);
            
            Utility.Unity.AddOnApplicationQuitListener(OnApplicationQuit);
        }

        public void Start()
        {
            if (_isStarted)
            {
                Log.Info("[GameApp] start ignored: manager already started.");
                    
                return;
            }

            _isStarted = true;
            
            // Start 可能被重复调用（热更重入）；Fsm.Start 重复会抛，只留这一条
            if (_fsm.IsRunning)
            {
                return;
            }

            _fsm.Start<StartGameState>();
            
            Log.Info($"[GameApp] fsm started");
        }

        private void OnApplicationPause(bool paused)
        {
            if (!_isStarted)
            {
                Log.Info("[GameApp] pause ignored: manager not started.");
                    
                return;
            }
            
            // 应用进入后台后 Update 不会再跑，不能等下一帧；这里直接切状态
            if (paused)
            {
                _currentState.SwitchState<PauseGameState>(_fsm);
                    
                Log.Info("[GameApp] fsm pause.");

                return;
            }

            _currentState.SwitchState<RunGameState>(_fsm);
                
            Log.Info("[GameApp] fsm resume.");
        }

        private void OnApplicationQuit()
        {
            if (!_isStarted)
            {
                Log.Info("[GameApp] quit ignored: manager not started.");
                    
                return;
            }
            
            _currentState.SwitchState<ExitGameState>(_fsm);
                
            Log.Info("[GameApp] fsm quit.");
        }

        protected override void OnRelease()
        {
            _isStarted = false;
            
            Utility.Unity.RemoveOnApplicationPauseListener(OnApplicationPause);
            
            Utility.Unity.RemoveOnApplicationQuitListener(OnApplicationQuit);

            // player 关闭顺序可能先 ModuleSystem.Shutdown，FSM 已被回收；只留这一条
            if (!_fsm.IsDestroyed)
            {
                GameModule.Fsm.DestroyFsm(_fsm);
            }

            _fsm = null;
            
            Log.Info("[GameApp] manager released.");
        }
    }
}
