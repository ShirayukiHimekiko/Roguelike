namespace GameLogic
{
    /// <summary>单个玩家提交的一帧战斗输入。</summary>
    public readonly struct BattleInput
    {
        /// <summary>已经归一化的定点移动方向。</summary>
        public FixedVector2 Direction { get; }

        /// <summary>当帧按钮值。</summary>
        public int Button { get; }

        /// <summary>保存当帧移动方向和按钮输入。</summary>
        public BattleInput(FixedVector2 direction, int button = 0)
        {
            Direction = direction;
            Button = button;
        }
    }
}
