using System;
using TEngine;
using UnityEngine;
#if UNITY_EDITOR
using Unity.Profiling;
#endif

namespace GameLogic.Frame
{
    /// <summary>
    /// 使用普通 IUpdate 推进应用级固定时钟并发布 Tick。
    /// </summary>
    public sealed class FrameManager : Singleton<FrameManager>, IUpdate
    {
        public const int TickRate = FrameClock.TickRate;
        public const int MaxStepsPerUpdate = FrameClock.MaxStepsPerUpdate;

#if UNITY_EDITOR
        private static readonly ProfilerMarker UpdateMarker = new("ProjectB.Frame.Update");
        private static readonly ProfilerMarker TickMarker = new("ProjectB.Frame.Tick");
#endif

        private readonly FrameClock _clock = new();
        private double _subNanosecond;
        private bool _applicationPaused;
        private bool _skipNextSample;
        private bool _stepRequested;

        /// <summary>
        /// 广播当前全局 Tick。各业务在进入和退出时订阅或退订。
        /// </summary>
        public event Action<long> TickAdvanced;

        /// <summary>
        /// 当前应用级 Tick，从 0 开始。
        /// </summary>
        public long CurrentTick { get; private set; }

        /// <summary>
        /// 应用挂起或框架游戏暂停时停止推进。
        /// </summary>
        public bool IsPaused => _applicationPaused || GameModule.Base.IsGamePaused;

        /// <summary>
        /// 是否只消费调试单步请求。
        /// </summary>
        public bool IsDebugPaused { get; private set; }

        /// <summary>
        /// 最近一次固定步余量的分数进度，供表现插值。
        /// </summary>
        public double Alpha => _clock.Alpha;

        internal FrameUpdateStats LastUpdate { get; private set; }
        internal long TotalDroppedSteps { get; private set; }
        internal long TotalClippedNanoseconds { get; private set; }

        /// <summary>
        /// 切换全局调试暂停。解除时清除剩余的单步请求。
        /// </summary>
        public void SetDebugPaused(bool paused)
        {
            IsDebugPaused = paused;
            _stepRequested = false;
        }

        /// <summary>
        /// 调试暂停期间安排一次单步。重复请求合并。
        /// </summary>
        public void RequestDebugStep()
        {
            _stepRequested = IsDebugPaused;
        }

        /// <summary>
        /// 由 SingletonSystem 调用，是唯一实时采样入口。
        /// </summary>
        public void OnUpdate()
        {
            if (IsPaused)
                return;
            if (_skipNextSample)
            {
                _skipNextSample = false;
                return;
            }

#if UNITY_EDITOR
            using var sample = UpdateMarker.Auto();
#endif
            double elapsed = (double)Time.unscaledDeltaTime * FrameClock.NanosecondsPerSecond;
            int steps = 0;
            long droppedSteps = 0;
            long clippedNanoseconds = 0;

            if (!IsDebugPaused)
            {
                double quantized = elapsed + _subNanosecond;
                long elapsedNs = (long)quantized;
                _subNanosecond = quantized - elapsedNs;
                steps = _clock.Consume(elapsedNs, out droppedSteps, out clippedNanoseconds);
            }
            else if (_stepRequested)
            {
                _stepRequested = false;
                _clock.ResetPhase();
                steps = 1;
            }

            for (int i = 0; i < steps; i++)
            {
#if UNITY_EDITOR
                using var tickSample = TickMarker.Auto();
#endif
                CurrentTick++;
                TickAdvanced?.Invoke(CurrentTick);
            }

            TotalDroppedSteps += droppedSteps;
            TotalClippedNanoseconds += clippedNanoseconds;
            LastUpdate = new FrameUpdateStats(Time.frameCount, (long)elapsed, steps,
                droppedSteps, clippedNanoseconds, CurrentTick);
        }

        /// <summary>
        /// 订阅应用挂起和恢复，并注册 TEngine 帧探针。
        /// </summary>
        protected override void OnInit()
        {
            Utility.Unity.AddOnApplicationPauseListener(OnApplicationPause);
            GameModule.Debugger.RegisterDebuggerWindow(ClockProbeWindow.Path, new ClockProbeWindow(this));
        }

        /// <summary>
        /// 解除应用事件、调试窗口及所有 Tick 订阅。
        /// </summary>
        protected override void OnRelease()
        {
            Utility.Unity.RemoveOnApplicationPauseListener(OnApplicationPause);
            IDebuggerModule debugger = GameModule.Debugger;
            // 框架可能先关闭调试器并清空窗口树。
            if (debugger.GetDebuggerWindow(ClockProbeWindow.Path) is ClockProbeWindow)
            {
                debugger.UnregisterDebuggerWindow(ClockProbeWindow.Path);
            }

            TickAdvanced = null;
        }

        /// <summary>
        /// 切断后台间隔。恢复后从下一次正常采样重新量化。
        /// </summary>
        private void OnApplicationPause(bool paused)
        {
            if (_applicationPaused == paused)
                return;

            _applicationPaused = paused;
            _subNanosecond = 0;
            _skipNextSample = !paused;
        }
    }

    /// <summary>
    /// 最近一次完成派发的宿主更新，用于调试窗口展示。
    /// </summary>
    internal readonly struct FrameUpdateStats
    {
        public readonly int FrameNumber;
        public readonly long ElapsedNanoseconds;
        public readonly int Steps;
        public readonly long DroppedSteps;
        public readonly long ClippedNanoseconds;
        public readonly long LastTick;

        public FrameUpdateStats(int frameNumber, long elapsedNanoseconds, int steps,
            long droppedSteps, long clippedNanoseconds, long lastTick)
        {
            FrameNumber = frameNumber;
            ElapsedNanoseconds = elapsedNanoseconds;
            Steps = steps;
            DroppedSteps = droppedSteps;
            ClippedNanoseconds = clippedNanoseconds;
            LastTick = lastTick;
        }
    }
}
