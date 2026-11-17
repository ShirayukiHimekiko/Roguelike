using System;
using GameLogic.FixedPoint;
using TEngine;
using UnityEngine;
#if UNITY_EDITOR
using Unity.Profiling;
#endif

namespace GameLogic.Frame
{
    /// <summary>
    /// 在 TEngine 调试器展示共享时钟和独立业务订阅。
    /// </summary>
    internal sealed class ClockProbeWindow : IDebuggerWindow
    {
        public const string Path = "Project B/Frame Probe";

        private const int HISTORY_CAPACITY = 120;
        private const float TEXT_REFRESH_SECONDS = 0.2f;
        private const float REFERENCE_FRAME_MS = 1000f / FrameManager.TickRate;
        private const float CHART_CEILING_MS = REFERENCE_FRAME_MS * FrameManager.MaxStepsPerUpdate;
        private const string CHART_HINT = "指向柱形查看该帧的间隔、步数和丢步。";

        private static readonly Color ChartBackground = new(0.09f, 0.11f, 0.14f);
        private static readonly Color ReferenceLineColor = new(0.38f, 0.43f, 0.49f);
        private static readonly Color NormalBar = new(0.35f, 0.67f, 0.79f);
        private static readonly Color CatchUpBar = new(0.92f, 0.69f, 0.32f);
        private static readonly Color DroppedBar = new(0.93f, 0.38f, 0.32f);
        private static readonly Fixed64 SlowSpeed = Fixed64.Parse("0.5");
        private static readonly Fixed64 FastSpeed = Fixed64.Parse("2.5");
        private static readonly GUILayoutOption ProbeColumn = GUILayout.Width(42f);
        private static readonly GUILayoutOption StateColumn = GUILayout.Width(84f);
        private static readonly GUILayoutOption TickColumn = GUILayout.Width(68f);
        private static readonly GUILayoutOption InputColumn = GUILayout.Width(48f);
#if UNITY_EDITOR
        private static readonly ProfilerMarker DrawMarker = new("ProjectB.FrameProbe.Draw");
#endif

        private readonly FrameManager _frames;
        private readonly FrameUpdateStats[] _history = new FrameUpdateStats[HISTORY_CAPACITY];
        private ClockProbe _primary;
        private ClockProbe _reference;
        private int _nextHistoryIndex;
        private int _historyCount;
        private int _lastRecordedFrame;
        private int _hoveredFrame = -1;
        private long _probeId;
        private long _lastShownFailedTick;
        private float _refreshRemaining;
        private Vector2 _scroll;
        private bool _showDetails;
        private string _summaryText = string.Empty;
        private ProbeRow _primaryRow;
        private ProbeRow _referenceRow;
        private string _hoverText;

        /// <summary>
        /// 通过已有管理器读取帧统计和建立样本订阅。
        /// </summary>
        public ClockProbeWindow(FrameManager frames)
        {
            _frames = frames;
        }

        /// <inheritdoc />
        public void Initialize(params object[] args)
        {
            RefreshText();
        }

        /// <inheritdoc />
        public void OnEnter()
        {
            RefreshText();
        }

        /// <inheritdoc />
        public void OnLeave()
        {
        }

        /// <inheritdoc />
        public void Shutdown()
        {
            Stop();
        }

        /// <inheritdoc />
        public void OnUpdate(float elapseSeconds, float realElapseSeconds)
        {
            if (_primary == null || !Debugger.Instance.ShowFullWindow)
                return;

            FrameUpdateStats latest = _frames.LastUpdate;
            if (latest.FrameNumber != _lastRecordedFrame)
            {
                _history[_nextHistoryIndex] = latest;
                _nextHistoryIndex = (_nextHistoryIndex + 1) % HISTORY_CAPACITY;
                _historyCount = Math.Min(_historyCount + 1, HISTORY_CAPACITY);
                _lastRecordedFrame = latest.FrameNumber;
            }

            _refreshRemaining -= realElapseSeconds;
            if (_refreshRemaining <= 0f || _lastShownFailedTick != _primary.FailedTick)
            {
                RefreshText();
            }
        }

        /// <inheritdoc />
        public void OnDraw()
        {
#if UNITY_EDITOR
            using var sample = DrawMarker.Auto();
#endif
            _scroll = GUILayout.BeginScrollView(_scroll);
            DrawControls();
            GUILayout.Label(_summaryText, GUI.skin.box);
            DrawChart();
            DrawProbeRows();
            GUILayout.EndScrollView();
        }

        /// <summary>
        /// 展示探针启停和全局调试步进控制。
        /// </summary>
        private void DrawControls()
        {
            bool running = _primary != null;
            bool debugPaused = _frames.IsDebugPaused;
            bool globallyPaused = _frames.IsPaused;

            GUILayout.BeginHorizontal();
            GUILayout.Label(running ? $"帧探针 #{_probeId}" : "帧探针");
            using (new DisabledControls(globallyPaused && !running))
            {
                if (GUILayout.Button(running ? "关闭探针" : "启动探针"))
                {
                    if (running)
                    {
                        Stop();
                    }
                    else
                    {
                        Start();
                    }
                }
            }

            using (new DisabledControls(!running))
            {
                if (GUILayout.Button(debugPaused ? "恢复推进" : "调试暂停"))
                {
                    _frames.SetDebugPaused(!debugPaused);
                    RefreshText();
                }
            }

            using (new DisabledControls(!running || !debugPaused || globallyPaused))
            {
                if (GUILayout.Button("单步"))
                {
                    _frames.RequestDebugStep();
                }
            }
            GUILayout.EndHorizontal();

            if (globallyPaused)
            {
                GUILayout.Label("全局暂停");
            }
        }

        /// <summary>
        /// 展示业务进度，保留独立暂停和按需诊断操作。
        /// </summary>
        private void DrawProbeRows()
        {
            DrawProbeRow("样本", new ProbeRow("状态", "业务 Tick", "最近触发", "输入", "位置 X"));
            DrawProbeRow("A", _primaryRow);
            DrawProbeRow("B", _referenceRow);

            ClockProbe primary = _primary;
            bool running = primary != null;
            bool canControlA = running && primary.FailedTick == 0;

            GUILayout.BeginHorizontal();
            using (new DisabledControls(!canControlA))
            {
                if (GUILayout.Button(primary?.IsPaused == true ? "继续 A" : "暂停 A"))
                {
                    primary.SetPaused(!primary.IsPaused);
                    RefreshText();
                }
            }

            _showDetails = GUILayout.Toggle(_showDetails, "输入与故障", GUI.skin.button);
            using (new DisabledControls(!running))
            {
                if (GUILayout.Button("复制 A 诊断"))
                {
                    GUIUtility.systemCopyBuffer = primary.FormatRecord(_probeId);
                }
            }
            GUILayout.EndHorizontal();

            if (!_showDetails)
                return;

            GUILayout.BeginHorizontal();
            using (new DisabledControls(!canControlA || primary.IsPaused || _frames.IsPaused))
            {
                if (GUILayout.Button("A 速度 0.5"))
                    primary.QueueSpeed(SlowSpeed);
                if (GUILayout.Button("A 速度 2.5"))
                    primary.QueueSpeed(FastSpeed);
                if (GUILayout.Button("A 下一步故障"))
                    primary.FaultOnNextTick();
            }
            GUILayout.EndHorizontal();
        }

        /// <summary>
        /// 让表头和各样本的数据按固定列宽对齐。
        /// </summary>
        private static void DrawProbeRow(string name, ProbeRow row)
        {
            GUILayout.BeginHorizontal(GUI.skin.box);
            GUILayout.Label(name, ProbeColumn);
            GUILayout.Label(row.State, StateColumn);
            GUILayout.Label(row.Tick, TickColumn);
            GUILayout.Label(row.TimerTick, TickColumn);
            GUILayout.Label(row.Input, InputColumn);
            GUILayout.Label(row.Position);
            GUILayout.EndHorizontal();
        }

        /// <summary>
        /// 用固定跨度的画布呈现最近宿主帧的间隔及补步状态。
        /// </summary>
        private void DrawChart()
        {
            GUILayout.Label("宿主间隔 / ms · 最近 120 个采样");
            Rect rect = GUILayoutUtility.GetRect(160f, 76f, GUILayout.ExpandWidth(true));
            if (Event.current.type == EventType.Repaint)
            {
                PaintChart(rect);
            }

            DrawFrameDetails(rect);
            GUILayout.Label("参考线 16.67 ms · 黄色补步 · 红色丢步或裁剪");
        }

        /// <summary>
        /// 绘制间隔柱与 60 FPS 参考线，颜色标记补步和丢步。
        /// </summary>
        private void PaintChart(Rect rect)
        {
            Color previous = GUI.color;
            GUI.color = ChartBackground;
            GUI.DrawTexture(rect, Texture2D.whiteTexture);

            float columnWidth = rect.width / HISTORY_CAPACITY;
            for (int i = 0; i < _historyCount; i++)
            {
                FrameUpdateStats frame = GetHistoryFrame(i);
                float milliseconds = frame.ElapsedNanoseconds / 1_000_000f;
                float height = Mathf.Clamp01(milliseconds / CHART_CEILING_MS) * rect.height;
                bool overloaded = frame.DroppedSteps > 0 || frame.ClippedNanoseconds > 0;
                GUI.color = overloaded ? DroppedBar : frame.Steps > 1 ? CatchUpBar : NormalBar;

                float x = rect.x + (_history.Length - _historyCount + i) * columnWidth;
                var bar = new Rect(x, rect.yMax - height, Mathf.Max(1f, columnWidth - 1f), height);
                GUI.DrawTexture(bar, Texture2D.whiteTexture);
            }

            GUI.color = ReferenceLineColor;
            float lineY = rect.yMax - rect.height * REFERENCE_FRAME_MS / CHART_CEILING_MS;
            GUI.DrawTexture(new Rect(rect.x, lineY, rect.width, 1f), Texture2D.whiteTexture);
            GUI.color = previous;
        }

        /// <summary>
        /// 根据鼠标沿时间轴的位置显示单帧数据。
        /// </summary>
        private void DrawFrameDetails(Rect rect)
        {
            Vector2 mouse = Event.current.mousePosition;
            if (rect.Contains(mouse))
            {
                int column = (int)((mouse.x - rect.x) * HISTORY_CAPACITY / rect.width);
                int index = column - (HISTORY_CAPACITY - _historyCount);
                if (index >= 0 && index < _historyCount)
                {
                    FrameUpdateStats frame = GetHistoryFrame(index);
                    if (frame.FrameNumber != _hoveredFrame)
                    {
                        _hoveredFrame = frame.FrameNumber;
                        _hoverText = $"Unity 帧 {frame.FrameNumber} · 间隔 {frame.ElapsedNanoseconds / 1_000_000d:F2} ms" +
                            $" · 步数 {frame.Steps} · 丢步 {frame.DroppedSteps}" +
                            $" · 裁剪 {frame.ClippedNanoseconds / 1_000_000d:F2} ms · Tick {frame.LastTick}";
                    }
                }
                else
                {
                    _hoveredFrame = -1;
                }
            }
            else
            {
                _hoveredFrame = -1;
            }

            GUILayout.Label(_hoveredFrame < 0 ? CHART_HINT : _hoverText);
        }

        /// <summary>
        /// 读取按时间升序排列的样本。
        /// </summary>
        private FrameUpdateStats GetHistoryFrame(int index)
        {
            int first = _nextHistoryIndex - _historyCount + HISTORY_CAPACITY;
            return _history[(first + index) % HISTORY_CAPACITY];
        }

        /// <summary>
        /// 创建两个从业务 Tick 0 开始的订阅者。
        /// </summary>
        private void Start()
        {
            _primary = new ClockProbe(_frames);
            _reference = new ClockProbe(_frames);
            _probeId++;
            _nextHistoryIndex = 0;
            _historyCount = 0;
            _hoveredFrame = -1;
            _lastRecordedFrame = _frames.LastUpdate.FrameNumber;
            RefreshText();
        }

        /// <summary>
        /// 释放样本订阅，并结束面板开启的调试暂停。
        /// </summary>
        private void Stop()
        {
            if (_primary == null)
                return;

            _primary.Dispose();
            _reference.Dispose();
            _primary = null;
            _reference = null;
            _frames.SetDebugPaused(false);
            RefreshText();
        }

        /// <summary>
        /// 缓存数值摘要，避免 IMGUI 为重复绘制事件重新格式化。
        /// </summary>
        private void RefreshText()
        {
            FrameUpdateStats last = _frames.LastUpdate;
            string mode = _frames.IsDebugPaused ? "调试暂停" : "固定步";
            _summaryText = $"{mode} · {_frames.CurrentTick} Tick · {last.Steps}/{FrameManager.MaxStepsPerUpdate} 步" +
                $" · 累计丢步 {_frames.TotalDroppedSteps} · 累计裁剪 {_frames.TotalClippedNanoseconds / 1_000_000d:F2} ms";
            _primaryRow = Describe(_primary);
            _referenceRow = Describe(_reference);
            _lastShownFailedTick = _primary?.FailedTick ?? 0;
            _refreshRemaining = TEXT_REFRESH_SECONDS;
        }

        /// <summary>
        /// 格式化业务计数、定时器及最后输入的可见状态。
        /// </summary>
        private static ProbeRow Describe(ClockProbe probe)
        {
            if (probe == null)
                return new ProbeRow("未开始", "—", "—", "—", "—");

            string state = probe.FailedTick > 0 ? $"故障 {probe.FailedTick}" : probe.IsPaused ? "已退订" : "运行";
            return new ProbeRow(state, probe.Tick.ToString(), probe.LastTimerTick.ToString(),
                $"#{probe.AppliedInputSequence}", $"{probe.DisplayX:F3}");
        }

        private readonly struct ProbeRow
        {
            public readonly string State;
            public readonly string Tick;
            public readonly string TimerTick;
            public readonly string Input;
            public readonly string Position;

            public ProbeRow(string state, string tick, string timerTick, string input, string position)
            {
                State = state;
                Tick = tick;
                TimerTick = timerTick;
                Input = input;
                Position = position;
            }
        }

        private readonly struct DisabledControls : IDisposable
        {
            private readonly bool _previous;

            public DisabledControls(bool disabled)
            {
                _previous = GUI.enabled;
                GUI.enabled = _previous && !disabled;
            }

            public void Dispose()
            {
                GUI.enabled = _previous;
            }
        }
    }
}
