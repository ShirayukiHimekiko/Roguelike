using System;

namespace GameLogic
{
    /// <summary>锁步客户端的本地录像控制和文件入口。</summary>
    public static partial class ClientHelper
    {
        /// <summary>提交回放定位目标，留给下一次回放轮询分批执行。</summary>
        public static bool JumpReplay(this Room room, int targetFrame)
        {
            ReplayUpdater replay = room.ReplayUpdater;
            if (replay == null || room.Clock == null || targetFrame < 0 || targetFrame >= room.Replay.FrameCount)
            {
                return false;
            }

            replay.SeekTargetFrame = targetFrame;
            replay.PrepareSeek = true;
            return true;
        }

        /// <summary>调整回放频率，保留切换锚点的到期时间。</summary>
        public static bool ChangeReplaySpeed(this Room room, int speed)
        {
            ReplayUpdater replay = room.ReplayUpdater;
            if (replay == null || room.Clock == null || (speed != 1 && speed != 2 && speed != 4 && speed != 8))
            {
                return false;
            }

            room.Clock.ChangeInterval(FixedTimeCounter.FRAME_INTERVAL_MS / speed, Math.Max(0, room.AuthorityFrame));
            replay.Speed = speed;
            return true;
        }
    }
}
