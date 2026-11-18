using System;

namespace GameLogic
{
    /// <summary>
    /// 负责一局战斗的固定步进。一次宿主更新最多执行一帧。
    /// </summary>
    internal sealed class BattleUpdater
    {
        /// <summary>
        /// 当前正在执行或最近一次已推进的帧号。
        /// </summary>
        internal int CurrentFrame { get; private set; } = -1;

        /// <summary>
        /// 判断下一帧是否到期。到期时先更新帧号，再执行该帧。
        /// </summary>
        internal void Update(FixedTimeCounter clock, long nowMs, Action<int> executeTick)
        {
            int nextFrame = CurrentFrame + 1;
            if (nowMs < clock.FrameTime(nextFrame))
            {
                return;
            }

            CurrentFrame = nextFrame;
            executeTick(nextFrame);
        }
    }
}
