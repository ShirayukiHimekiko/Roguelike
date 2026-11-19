using System.Diagnostics;

namespace GameLogic
{
    /// <summary>
    /// 根据当局开战时间计算各逻辑帧的计划到期时刻。
    /// </summary>
    public sealed class FixedTimeCounter
    {
        internal const int FRAME_INTERVAL_MS = 50;

        private long _startTimeMs;
        private int _startFrame;

        /// <summary>本局时钟当前的步长，单位为毫秒。</summary>
        internal int Interval { get; private set; } = FRAME_INTERVAL_MS;

        /// <summary>
        /// 以开战时刻作为第零帧的到期时刻。
        /// </summary>
        internal FixedTimeCounter(long startTimeMs)
        {
            _startTimeMs = startTimeMs;
        }

        /// <summary>
        /// 返回指定帧的计划到期时刻，单位为毫秒。
        /// </summary>
        internal long FrameTime(int frame)
        {
            return _startTimeMs + ((long)frame - _startFrame) * Interval;
        }

        /// <summary>以指定帧和时刻重设时间锚点。</summary>
        internal void Reset(long time, int frame)
        {
            _startTimeMs = time;
            _startFrame = frame;
        }

        /// <summary>改变步长，同时保留切换帧的到期时刻。</summary>
        internal void ChangeInterval(int interval, int frame)
        {
            Reset(FrameTime(frame), frame);
            Interval = interval;
        }

        /// <summary>
        /// 从单调时钟采样，并按整数毫秒量化。
        /// </summary>
        public static long ReadMilliseconds()
        {
            return Stopwatch.GetTimestamp() * 1000 / Stopwatch.Frequency;
        }
    }
}
