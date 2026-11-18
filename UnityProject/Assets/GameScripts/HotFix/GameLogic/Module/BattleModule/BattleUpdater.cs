namespace GameLogic
{
    /// <summary>
    /// 负责一局战斗的固定步进。一次宿主更新最多执行一帧。
    /// </summary>
    internal sealed class BattleUpdater
    {
        /// <summary>
        /// 判断下一帧是否到期。到期时确定输入并推进当局。
        /// </summary>
        internal void Update(BattleRoom room, long nowMs)
        {
            int nextFrame = room.AuthorityFrame + 1;
            if (nowMs < room.Clock.FrameTime(nextFrame))
            {
                return;
            }

            BattleFrameInputs inputs = room.FrameBuffer.Seal();
            room.Tick(nextFrame, inputs);
        }
    }
}
