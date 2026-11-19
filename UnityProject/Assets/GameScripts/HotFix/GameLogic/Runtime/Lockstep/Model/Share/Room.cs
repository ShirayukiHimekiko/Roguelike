using System;
using System.Collections.Generic;

namespace GameLogic
{
    /// <summary>单局锁步的共享状态。帧推进、世界替换和释放由 RoomSystem 执行。</summary>
    public sealed class Room
    {
        internal LockstepWorldSetup WorldSetup { get; }
        internal IReadOnlyDictionary<long, int> PlayerSlots { get; }
        internal int LocalPlayerSlot { get; }
        internal int AuthorityFrame { get; set; } = -1;
        internal FrameBuffer FrameBuffer { get; set; }
        internal LockstepWorld World { get; set; }
        internal FixedTimeCounter Clock { get; set; }
        internal Action<Room, long> UpdateFrame { get; set; }
        internal ReplayUpdater ReplayUpdater { get; }

        /// <summary>最近成功推进的房间帧。</summary>
        public int CurrentFrame { get { return AuthorityFrame; } }

        /// <summary>本局记录或重演的录像。</summary>
        public Replay Replay { get; }

        /// <summary>当局是否由录像驱动。</summary>
        public bool IsReplay { get { return ReplayUpdater != null; } }

        /// <summary>实时局已从逻辑帧内自然结束。</summary>
        public bool IsFinished { get; internal set; }

        /// <summary>每次装配并提交新世界后增加，同区间回放复用世界时保持原值。</summary>
        public int WorldRevision { get; internal set; }

        /// <summary>当前回放倍率。</summary>
        public int ReplaySpeed { get { return ReplayUpdater?.Speed ?? 1; } }

        /// <summary>待处理的定位帧，-1 表示当前没有定位请求。</summary>
        public int ReplaySeekTargetFrame { get { return ReplayUpdater?.SeekTargetFrame ?? -1; } }

        /// <summary>最近一次回放分歧所在帧，-1 表示当前没有分歧。</summary>
        public int ReplayDivergedFrame { get { return ReplayUpdater?.DivergedFrame ?? -1; } }

        /// <summary>回放是否在演算前停步、在末帧后发现分歧，或正常完成。</summary>
        public ReplayPlaybackStatus PlaybackStatus { get { return ReplayUpdater?.Status ?? ReplayPlaybackStatus.Playing; } }

        /// <summary>建立开局数据与输入槽，等待宿主进场后初始化世界。</summary>
        internal Room(Replay replay, IReadOnlyDictionary<long, int> playerSlots, int localPlayerSlot,
            LockstepWorldSetup worldSetup, bool isReplay)
        {
            Replay = replay;
            PlayerSlots = playerSlots;
            LocalPlayerSlot = localPlayerSlot;
            WorldSetup = worldSetup;
            FrameBuffer = new FrameBuffer(playerSlots);
            ReplayUpdater = isReplay ? new ReplayUpdater() : null;
        }
    }
}
