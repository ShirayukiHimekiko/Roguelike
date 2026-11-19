namespace GameLogic
{
    /// <summary>按回放时钟播放，或按预算重演到明确的定位目标。</summary>
    internal static class ReplayUpdaterSystem
    {
        private const int POLL_BUDGET_MS = 5;

        /// <summary>执行到期的录像帧，在定位、分歧或录像尾部按各自边界停止。</summary>
        internal static void Update(Room room, long nowMs)
        {
            ReplayUpdater state = room.ReplayUpdater;
            int target = state.SeekTargetFrame;
            bool seeking = target >= 0;
            if (state.PrepareSeek)
            {
                PrepareSeek(room, state, target);
            }

            int lastFrame = room.Replay.FrameCount - 1;
            while (state.DivergedFrame < 0 && room.AuthorityFrame < (seeking ? target : lastFrame))
            {
                int frame = room.AuthorityFrame + 1;
                if (!seeking && nowMs < room.Clock.FrameTime(frame))
                {
                    return;
                }

                var inputs = new OneFrameInputs(room.Replay.Frames[frame].Inputs, 0, room.PlayerSlots);
                if (!room.Tick(frame, inputs))
                {
                    SetDivergence(state, frame, ReplayPlaybackStatus.FrameDiverged);
                    return;
                }

                if (frame == lastFrame && !CompletePlayback(room, state, frame))
                {
                    return;
                }

                if (FixedTimeCounter.ReadMilliseconds() - nowMs > POLL_BUDGET_MS)
                {
                    break;
                }
            }

            if (seeking && room.AuthorityFrame == target && state.DivergedFrame < 0)
            {
                state.SeekTargetFrame = -1;
                room.Clock.Reset(FixedTimeCounter.ReadMilliseconds(), room.AuthorityFrame);
            }
        }

        /// <summary>只有退跳、跨区间或分歧恢复才替换世界。</summary>
        private static void PrepareSeek(Room room, ReplayUpdater state, int target)
        {
            int checkpointIndex = target / Replay.CHECKPOINT_INTERVAL;
            if (state.DivergedFrame >= 0 || target < room.AuthorityFrame ||
                checkpointIndex != room.AuthorityFrame / Replay.CHECKPOINT_INTERVAL)
            {
                room.RestoreCheckpoint(room.Replay.Checkpoints[checkpointIndex]);
                state.DivergedFrame = -1;
                state.Status = ReplayPlaybackStatus.Playing;
            }

            state.PrepareSeek = false;
        }

        /// <summary>普通播放和定位都在末帧实际执行后检查终局指纹。</summary>
        private static bool CompletePlayback(Room room, ReplayUpdater state, int frame)
        {
            ulong? expected = room.Replay.TerminalHash;
            if (expected.HasValue && room.World.CaptureSnapshot().Hash != expected.Value)
            {
                SetDivergence(state, frame, ReplayPlaybackStatus.TerminalDiverged);
                return false;
            }

            state.Status = ReplayPlaybackStatus.Completed;
            return true;
        }

        /// <summary>记录分歧并终止当前定位，等待明确的后续定位请求。</summary>
        private static void SetDivergence(ReplayUpdater state, int frame, ReplayPlaybackStatus status)
        {
            state.DivergedFrame = frame;
            state.Status = status;
            state.SeekTargetFrame = -1;
        }
    }
}
