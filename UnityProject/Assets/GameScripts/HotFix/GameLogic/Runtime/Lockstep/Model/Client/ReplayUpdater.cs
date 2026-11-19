namespace GameLogic
{
    /// <summary>回放的当前位置是否可以继续，以及分歧发生在帧前还是末帧之后。</summary>
    public enum ReplayPlaybackStatus
    {
        Playing,
        Completed,
        FrameDiverged,
        TerminalDiverged
    }

    /// <summary>当局回放的倍率、定位请求和停止状态。</summary>
    internal sealed class ReplayUpdater
    {
        internal int Speed { get; set; } = 1;
        internal int SeekTargetFrame { get; set; } = -1;
        internal bool PrepareSeek { get; set; }
        internal ReplayPlaybackStatus Status { get; set; }
        internal int DivergedFrame { get; set; } = -1;
    }
}
