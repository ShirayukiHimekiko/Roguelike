using System;
using System.IO;
using Cysharp.Threading.Tasks;
using TEngine;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;

namespace GameLogic
{
    /// <summary>主场景中的单机开始、退局和回放操作。</summary>
    public sealed class BattleManager : Singleton<BattleManager>
    {
        private const string LAST_RECORDING_FILE = "battle-last-v4.replay";
        private const string LEGACY_RECORDING_FILE = "battle-last-v3.replay";
        private const int SEEK_STEP = 100;

        private Room _room;
        private Scene _roomScene;
        private IFsm<BattleManager> _fsm;
        private bool _fileBusy;
        private bool _released;
        private int _reportedDivergence = -1;

        /// <summary>世界装配或从检查点替换完成后，通知宿主可访问的新世界。</summary>
        public event Action<LockstepWorld> WorldChanged;

        /// <summary>创建单机房间，等当前主场景就绪后开始推进。</summary>
        public void StartBattle()
        {
            if (_released || _room != null || _fileBusy)
            {
                return;
            }

            EnterBattle(RoomSystem.CreateLocal(0, Array.Empty<long>()));
        }

        /// <summary>从菜单异步加载并播放最后保存的一局。</summary>
        internal async UniTask StartLastReplayAsync()
        {
            if (_released || _room != null || _fileBusy)
            {
                return;
            }

            _fileBusy = true;
            Room room;
            try
            {
                string directory = Application.persistentDataPath;
                Replay recording = await ClientHelper.LoadReplayAsync(Path.Combine(directory, LAST_RECORDING_FILE));
                if (recording == null && !_released)
                {
                    recording = await ClientHelper.LoadReplayAsync(Path.Combine(directory, LEGACY_RECORDING_FILE));
                }

                if (_released)
                {
                    return;
                }

                if (recording == null)
                {
                    Log.Info("还没有已保存的单机战斗录像。");
                    return;
                }

                room = RoomSystem.CreateReplay(recording);
            }
            catch (Exception exception) when (exception is IOException || exception is InvalidDataException ||
                exception is UnauthorizedAccessException || exception is ArgumentException)
            {
                Log.Error($"读取单机录像失败：{exception.Message}");
                return;
            }
            finally
            {
                _fileBusy = false;
            }

            EnterBattle(room);
        }

        /// <summary>接管当局房间并启动战斗流程。</summary>
        private void EnterBattle(Room room)
        {
            if (_fsm != null)
            {
                GameModule.Fsm.DestroyFsm(_fsm);
            }

            _room = room;
            _roomScene = SceneChangeHelper.BindActiveScene();
            _reportedDivergence = -1;
            _fsm = GameModule.Fsm.CreateFsm(this,
                new InitializeBattleState(), new StartBattleState(), new RunBattleState(), new EndBattleState());
            _fsm.Start<InitializeBattleState>();
            GameModule.UI.CloseUI<StartUI>();
        }

        /// <summary>查询当局绑定场景的就绪情况。</summary>
        internal LocalSceneReadiness GetSceneReadiness()
        {
            return SceneChangeHelper.GetReadiness(_roomScene);
        }

        /// <summary>返回当前流程持有的当局房间。</summary>
        internal Room Room { get { return _room; } }

        /// <summary>建立房间的初始世界并通知宿主。</summary>
        internal void InitializeRoomWorld()
        {
            _room.InitializeWorld();
            WorldChanged?.Invoke(_room.World);
        }

        /// <summary>轮询当局，待更新返回后再通知宿主已替换的世界。</summary>
        internal void UpdateRoom(long nowMs)
        {
            int previousRevision = _room.WorldRevision;
            _room.Update(nowMs);
            if (_room.WorldRevision != previousRevision)
            {
                WorldChanged?.Invoke(_room.World);
            }
        }

        /// <summary>判断准备或进行中的战斗是否收到退局命令。</summary>
        internal bool IsExitRequested()
        {
            Keyboard keyboard = Keyboard.current;
            return keyboard != null && keyboard.escapeKey.wasPressedThisFrame;
        }

        /// <summary>将回放快捷键转换为房间命令，并报告首次分歧。</summary>
        internal void UpdateReplayCommands()
        {
            if (!_room.IsReplay)
            {
                return;
            }

            Keyboard keyboard = Keyboard.current;
            if (keyboard != null)
            {
                if (keyboard.tabKey.wasPressedThisFrame)
                {
                    int speed = _room.ReplaySpeed == 8 ? 1 : _room.ReplaySpeed * 2;
                    _room.ChangeReplaySpeed(speed);
                }

                int seek = (keyboard.rightArrowKey.wasPressedThisFrame ? SEEK_STEP : 0) -
                    (keyboard.leftArrowKey.wasPressedThisFrame ? SEEK_STEP : 0);
                if (seek != 0)
                {
                    int origin = _room.ReplaySeekTargetFrame >= 0 ? _room.ReplaySeekTargetFrame : _room.CurrentFrame;
                    int target = Math.Min(_room.Replay.FrameCount - 1, Math.Max(0, origin + seek));
                    if (_room.JumpReplay(target))
                    {
                        _reportedDivergence = -1;
                        return;
                    }
                }
            }

            int divergence = _room.ReplayDivergedFrame;
            if (divergence >= 0 && divergence != _reportedDivergence)
            {
                _reportedDivergence = divergence;
                if (_room.PlaybackStatus == ReplayPlaybackStatus.TerminalDiverged)
                {
                    Log.Error($"回放第 {divergence} 帧已执行，末帧执行后的状态 hash 与录像不一致。");
                }
                else
                {
                    Log.Error($"回放第 {divergence} 帧的帧前状态 hash 与录像不一致，该帧未执行。");
                }
            }
        }

        /// <summary>先结束房间并恢复菜单，再保存已完成的实时录像。</summary>
        internal async UniTask ExitBattleAsync()
        {
            Room ending = _room;
            _room = null;
            _roomScene = default;
            Replay recording = null;
            try
            {
                recording = ending.SealReplay();
            }
            finally
            {
                ending.Release();
                _fileBusy = recording != null;
                GameModule.UI.ShowUIAsync<StartUI>();
            }

            if (recording == null)
            {
                return;
            }

            try
            {
                string path = Path.Combine(Application.persistentDataPath, LAST_RECORDING_FILE);
                await ClientHelper.SaveReplayAsync(path, recording);
            }
            catch (Exception exception) when (exception is IOException || exception is InvalidDataException ||
                exception is UnauthorizedAccessException)
            {
                Log.Error($"保存单机录像失败：{exception.Message}");
            }
            finally
            {
                _fileBusy = false;
            }
        }

        /// <summary>释放本地流程，使仍在读取录像的流程退出。</summary>
        protected override void OnRelease()
        {
            _released = true;
            WorldChanged = null;
            _roomScene = default;
            if (_fsm != null)
            {
                if (!_fsm.IsDestroyed)
                {
                    GameModule.Fsm.DestroyFsm(_fsm);
                }
                _fsm = null;
            }

            if (_room != null)
            {
                _room.Release();
                _room = null;
            }
        }
    }
}
