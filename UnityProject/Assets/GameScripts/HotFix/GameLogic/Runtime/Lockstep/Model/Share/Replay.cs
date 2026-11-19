using System.Collections.Generic;

namespace GameLogic
{
    /// <summary>录像的开局数据、完整帧输入与定期世界检查点。</summary>
    public sealed class Replay
    {
        internal const int CHECKPOINT_INTERVAL = 1200;

        internal long LocalPlayerId { get; }
        internal IReadOnlyList<long> PlayerIds { get; }
        internal uint RandomSeed { get; }
        internal List<RecordedFrame> Frames { get; } = new List<RecordedFrame>();
        internal List<WorldSnapshot> Checkpoints { get; } = new List<WorldSnapshot>();

        /// <summary>已记录的逻辑帧数量。</summary>
        public int FrameCount { get { return Frames.Count; } }

        /// <summary>末帧执行及清理后的状态指纹。旧 V3 录像没有此字段。</summary>
        public ulong? TerminalHash { get; internal set; }

        /// <summary>保存创建和恢复该局所需的确定性初值。</summary>
        internal Replay(long localPlayerId, IReadOnlyList<long> playerIds, uint randomSeed)
        {
            LocalPlayerId = localPlayerId;
            PlayerIds = playerIds;
            RandomSeed = randomSeed;
        }

        /// <summary>独立保存当帧已确认输入和帧前状态。</summary>
        internal void Record(OneFrameInputs inputs, WorldSnapshot snapshot)
        {
            var copy = new PlayerFrameInput[PlayerIds.Count];
            inputs.CopyTo(copy, 0, copy.Length);
            Frames.Add(new RecordedFrame(copy, snapshot.Hash));
            if (snapshot.Frame % CHECKPOINT_INTERVAL == 0)
            {
                Checkpoints.Add(snapshot);
            }
        }
    }

    /// <summary>录像里的一帧输入和执行前的状态指纹。</summary>
    internal readonly struct RecordedFrame
    {
        internal PlayerFrameInput[] Inputs { get; }
        internal ulong Hash { get; }

        /// <summary>保存该帧的已确认输入和状态指纹。</summary>
        internal RecordedFrame(PlayerFrameInput[] inputs, ulong hash)
        {
            Inputs = inputs;
            Hash = hash;
        }
    }
}
