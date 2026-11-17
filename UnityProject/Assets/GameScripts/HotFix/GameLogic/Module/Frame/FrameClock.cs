namespace GameLogic.Frame
{
    /// <summary>
    /// 供帧管理器使用的整数固定步累加器。
    /// </summary>
    internal sealed class FrameClock
    {
        public const int TickRate = 60;
        public const int MaxStepsPerUpdate = 4;
        public const long NanosecondsPerSecond = 1_000_000_000L;

        private long _phase;

        /// <summary>
        /// 宿主时间距离下一次固定步的分数进度。
        /// </summary>
        public double Alpha => _phase / (double)NanosecondsPerSecond;

        /// <summary>
        /// 消费一次宿主时间，保留不足一步的整数相位并给出补步预算。
        /// </summary>
        public int Consume(long elapsedNs, out long droppedSteps, out long clippedNanoseconds)
        {
            long admitted = System.Math.Min(elapsedNs, NanosecondsPerSecond);
            clippedNanoseconds = elapsedNs - admitted;

            // 精确计算 1 / TickRate 秒的步长，无需把单步近似为整数纳秒。
            long total = _phase + admitted * TickRate;
            long due = System.Math.DivRem(total, NanosecondsPerSecond, out _phase);
            int steps = (int)System.Math.Min(due, MaxStepsPerUpdate);
            droppedSteps = due - steps;
            return steps;
        }

        /// <summary>
        /// 丢弃调试单步前保存的相位。
        /// </summary>
        public void ResetPhase()
        {
            _phase = 0;
        }
    }
}
