using System.Diagnostics;

namespace GameLogic
{
    /// <summary>
    /// 根据当局开战时间计算各逻辑帧的计划到期时刻。
    /// </summary>
    internal sealed class FixedTimeCounter
    {
        internal const int FRAME_INTERVAL_MS = 50;

        private readonly long _startTimeMs;

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
            return _startTimeMs + frame * FRAME_INTERVAL_MS;
        }

        /// <summary>
        /// 从单调时钟采样，并按整数毫秒量化。
        /// </summary>
        internal static long ReadMilliseconds()
        {
            return Stopwatch.GetTimestamp() * 1000 / Stopwatch.Frequency;
        }
    }
}
