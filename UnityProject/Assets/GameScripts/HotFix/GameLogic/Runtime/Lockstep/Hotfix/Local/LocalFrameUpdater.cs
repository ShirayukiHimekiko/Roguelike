namespace GameLogic
{
    /// <summary>本地权威推进，一次宿主轮询最多处理一帧。</summary>
    internal static class LocalFrameUpdater
    {
        /// <summary>下一帧到期后封存本地输入并执行共同单帧入口。</summary>
        internal static void Update(Room room, long nowMs)
        {
            int frame = room.AuthorityFrame + 1;
            if (nowMs >= room.Clock.FrameTime(frame))
            {
                room.Tick(frame, room.FrameBuffer.Seal(frame));
            }
        }
    }
}
