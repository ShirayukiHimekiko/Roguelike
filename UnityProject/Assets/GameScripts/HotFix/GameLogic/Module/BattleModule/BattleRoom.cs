using TEngine;

namespace GameLogic
{
    /// <summary>
    /// 持有当局状态机、权威步进、帧输入和战斗世界。
    /// </summary>
    public sealed class BattleRoom
    {
        private IFsm<BattleRoom> _fsm;

        /// <summary>
        /// 当前正在执行或最近推进的帧。首次推进前和退局后为 -1。
        /// </summary>
        public int CurrentFrame
        {
            get { return AuthorityFrame; }
        }

        /// <summary>
        /// 当局已经确认的权威帧号。
        /// </summary>
        internal int AuthorityFrame { get; private set; } = -1;

        /// <summary>
        /// 通过校验并按开局顺序保存的单位数据。
        /// </summary>
        internal BattleUnitStartData[] InitialUnits { get; }

        /// <summary>
        /// 本地玩家在当局输入中的固定下标。
        /// </summary>
        internal int LocalUnitSlot { get; }

        /// <summary>
        /// 本局的帧输入缓冲。
        /// </summary>
        internal BattleFrameBuffer FrameBuffer { get; set; }

        /// <summary>
        /// 本局的 Entitas 战斗世界。
        /// </summary>
        internal BattleWorld World { get; set; }

        /// <summary>
        /// 当局开战时建立的帧时钟。
        /// </summary>
        internal FixedTimeCounter Clock { get; set; }

        /// <summary>
        /// 开战时建立，结束时释放的固定帧更新器。
        /// </summary>
        internal BattleUpdater Updater { get; set; }

        /// <summary>
        /// 保存开战数据并启动战斗初始化状态。
        /// </summary>
        internal BattleRoom(BattleUnitStartData[] initialUnits, int localUnitSlot)
        {
            InitialUnits = initialUnits;
            LocalUnitSlot = localUnitSlot;
            _fsm = GameModule.Fsm.CreateFsm(this,
                new InitializeBattleState(),
                new StartBattleState(),
                new RunBattleState(),
                new EndBattleState());
            _fsm.Start<InitializeBattleState>();
        }

        /// <summary>
        /// 确认房间帧号，写入输入并执行一帧世界。
        /// </summary>
        internal void Tick(int frame, BattleFrameInputs inputs)
        {
            AuthorityFrame = frame;
            World.ApplyInputs(inputs);
            World.Tick();
        }

        /// <summary>
        /// 读取本局指定单位当前的定点状态。
        /// </summary>
        public bool TryGetUnitState(long playerId, out BattleUnitState state)
        {
            if (World != null)
            {
                return World.TryGetUnitState(playerId, out state);
            }

            state = default;
            return false;
        }

        /// <summary>
        /// 进入结束状态，停止当局推进并释放状态机。
        /// </summary>
        internal void Close()
        {
            var state = (BattleRoomState)_fsm.CurrentState;
            state.EndBattle(_fsm);
            Release();
        }

        /// <summary>
        /// 注销房间状态机并释放本局资源。
        /// </summary>
        internal void Release()
        {
            GameModule.Fsm.DestroyFsm<BattleRoom>();
            _fsm = null;
            Clock = null;
            Updater = null;
            World.Release();
            World = null;
            FrameBuffer = null;
            AuthorityFrame = -1;
        }
    }
}
