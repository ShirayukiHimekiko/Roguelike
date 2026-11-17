using System;
using System.Collections.Generic;
using System.Text;
using GameLogic.FixedPoint;

namespace GameLogic.Frame
{
    /// <summary>
    /// 订阅固定 Tick，用业务计数、定点位置和帧定时器展示结果。
    /// </summary>
    internal sealed class ClockProbe : IDisposable
    {
        private const int ONCE_TICK = 30;
        private const int REPEAT_INTERVAL = 60;
        private static readonly Fixed64 InitialSpeed = Fixed64.Parse("1.25");

        private readonly struct SpeedInput
        {
            public readonly long Tick;
            public readonly int Sequence;
            public readonly Fixed64 Speed;

            public SpeedInput(long tick, int sequence, Fixed64 speed)
            {
                Tick = tick;
                Sequence = sequence;
                Speed = speed;
            }
        }

        private readonly FrameManager _frames;
        private readonly FrameTimer _timer = new(4);
        private readonly List<SpeedInput> _inputs = new();
        private Fixed64 _speed = InitialSpeed;
        private Point2 _position;
        private long _previousX;
        private long _movementRemainder;
        private long _faultTick;
        private int _nextInput;
        private double _frozenDisplayX;

        /// <summary>
        /// 创建一个从业务 Tick 0 开始的样本并订阅管理器。
        /// </summary>
        public ClockProbe(FrameManager frames)
        {
            _frames = frames;
            _timer.Once(ONCE_TICK, RecordTimer);
            _timer.Repeat(REPEAT_INTERVAL, RecordTimer);
            _frames.TickAdvanced += OnTick;
        }

        public long Tick { get; private set; }
        public long GlobalTick { get; private set; }
        public bool IsPaused { get; private set; }
        public long FailedTick { get; private set; }
        public long TimerCount { get; private set; }
        public long LastTimerTick { get; private set; }
        public int AppliedInputSequence { get; private set; }

        /// <summary>
        /// 用共享相位插值。暂停或单步时显示稳定的值。
        /// </summary>
        public double DisplayX
        {
            get
            {
                if (IsPaused)
                    return _frozenDisplayX;
                if (_frames.IsDebugPaused)
                    return _position.XRaw / (double)Fixed64.Scale;

                double interpolated = _previousX + (_position.XRaw - (double)_previousX) * _frames.Alpha;
                return interpolated / Fixed64.Scale;
            }
        }

        /// <summary>
        /// 独立暂停通过退订实现，继续时订阅后续 Tick。
        /// </summary>
        public void SetPaused(bool paused)
        {
            if (paused)
            {
                _frozenDisplayX = DisplayX;
                _frames.TickAdvanced -= OnTick;
            }
            else
            {
                _previousX = _position.XRaw;
                _frames.TickAdvanced += OnTick;
            }

            IsPaused = paused;
        }

        /// <summary>
        /// 在下一业务 Tick 按受理顺序应用定点速度。
        /// </summary>
        public void QueueSpeed(Fixed64 speed)
        {
            _inputs.Add(new SpeedInput(Tick + 1, _inputs.Count + 1, speed));
        }

        /// <summary>
        /// 在下一业务 Tick 触发预期故障并退订。
        /// </summary>
        public void FaultOnNextTick()
        {
            _faultTick = Tick + 1;
        }

        /// <summary>
        /// 导出已提交位置、计时器摘要和有序输入。
        /// </summary>
        public string FormatRecord(long probeId)
        {
            var record = new StringBuilder();
            record.Append("ProbeId=").Append(probeId)
                .Append(" TickRate=").Append(FrameManager.TickRate)
                .Append(" InitialSpeedRaw=").Append(InitialSpeed.Raw)
                .Append(" GlobalTick=").Append(GlobalTick)
                .Append(" CommittedTick=").Append(Tick)
                .Append(" XRaw=").Append(_position.XRaw)
                .Append(" AppliedSequence=").Append(AppliedInputSequence)
                .Append(" TimerCount=").Append(TimerCount)
                .Append(" LastTimerTick=").Append(LastTimerTick)
                .Append(" FailedTick=").Append(FailedTick).AppendLine();
            record.AppendLine("TargetTick,InputSequence,SpeedRaw");
            foreach (SpeedInput input in _inputs)
            {
                record.Append(input.Tick).Append(',').Append(input.Sequence)
                    .Append(',').Append(input.Speed.Raw).AppendLine();
            }

            return record.ToString();
        }

        /// <summary>
        /// 退订并释放样本的定时任务。
        /// </summary>
        public void Dispose()
        {
            _frames.TickAdvanced -= OnTick;
            _timer.Dispose();
        }

        /// <summary>
        /// 消费一个全局 Tick，并提交这次收到的业务步。
        /// </summary>
        private void OnTick(long globalTick)
        {
            long tick = Tick + 1;
            if (tick == _faultTick)
            {
                FailedTick = tick;
                SetPaused(true);
                _timer.Dispose();
                return;
            }

            while (_nextInput < _inputs.Count && _inputs[_nextInput].Tick == tick)
            {
                SpeedInput input = _inputs[_nextInput++];
                _speed = input.Speed;
                AppliedInputSequence = input.Sequence;
            }

            long delta = Math.DivRem(checked(_speed.Raw + _movementRemainder),
                (long)FrameManager.TickRate, out _movementRemainder);
            long currentX = checked(_position.XRaw + delta);
            _timer.BeginTick(tick);
            _previousX = _position.XRaw;
            _position = new Point2(currentX, _position.YRaw);
            Tick = tick;
            GlobalTick = globalTick;
        }

        /// <summary>
        /// 记录当前业务步触发的同步任务。
        /// </summary>
        private void RecordTimer()
        {
            TimerCount++;
            LastTimerTick = Tick + 1;
        }
    }
}
