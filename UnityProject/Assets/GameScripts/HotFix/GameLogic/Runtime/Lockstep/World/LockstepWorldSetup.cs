using System;
using System.Collections.Generic;
using Entitas;

namespace GameLogic
{
    /// <summary>定义玩法如何接入战斗世界。实时与回放使用一致的组件和系统配置。</summary>
    public sealed class LockstepWorldSetup
    {
        internal Func<Context<BattleEntity>> CreateContext { get; }
        internal Action<SnapshotComponentCodecs> RegisterComponents { get; }
        internal Action<LockstepWorld, IReadOnlyList<long>> InitializeWorld { get; }
        internal Func<LockstepWorld, Systems> CreateSystems { get; }
        internal Action<LockstepWorld, OneFrameInputs> ApplyInputs { get; }

        /// <summary>配置当局的组件布局、开局、系统和输入入口。</summary>
        /// <param name="createContext">为每次创建或恢复提供独立 Context。省略时使用正式 Battle Context。</param>
        /// <param name="registerComponents">登记当前 Context 中需要随快照恢复的组件。</param>
        /// <param name="initializeWorld">仅实时开局调用，建立初始状态及玩家与实体的绑定。</param>
        /// <param name="createSystems">在初始实体或恢复实体就绪后装配系统。</param>
        /// <param name="applyInputs">在帧前快照前投递输入。只写当前值，演算由系统处理。</param>
        public LockstepWorldSetup(Func<Context<BattleEntity>> createContext = null,
            Action<SnapshotComponentCodecs> registerComponents = null,
            Action<LockstepWorld, IReadOnlyList<long>> initializeWorld = null,
            Func<LockstepWorld, Systems> createSystems = null,
            Action<LockstepWorld, OneFrameInputs> applyInputs = null)
        {
            CreateContext = createContext;
            RegisterComponents = registerComponents;
            InitializeWorld = initializeWorld;
            CreateSystems = createSystems;
            ApplyInputs = applyInputs;
        }
    }
}
