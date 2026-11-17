using System;

namespace GameLogic.Frame
{
    /// <summary>
    /// 在所属通道的连续 Tick 内同步派发到期任务。
    /// </summary>
    public sealed class FrameTimer : IDisposable
    {
        /// <summary>
        /// 一次任务登记的身份。跨计时器或已结束的句柄不可取消。
        /// </summary>
        public readonly struct Handle
        {
            internal readonly FrameTimer Owner;
            internal readonly long Id;

            internal Handle(FrameTimer owner, long id)
            {
                Owner = owner;
                Id = id;
            }
        }

        private struct Entry
        {
            public long Id;
            public long Due;
            public long Sequence;
            public int Interval;
            public Action Callback;
        }

        private readonly Entry[] _entries;
        private long _sequence;
        private long _tick;
        private bool _disposed;

        /// <summary>
        /// 从 Tick 0 开始，预留固定数量的任务槽位。
        /// </summary>
        public FrameTimer(int capacity)
        {
            if (capacity < 1)
                throw new ArgumentOutOfRangeException(nameof(capacity));

            _entries = new Entry[capacity];
        }

        /// <summary>
        /// 登记一个相对当前 Tick 延迟触发的单次任务。
        /// </summary>
        public Handle Once(int delay, Action callback)
        {
            return Schedule(delay, 0, callback);
        }

        /// <summary>
        /// 以固定 Tick 间隔触发。间隔也用于第一次触发。
        /// </summary>
        public Handle Repeat(int interval, Action callback)
        {
            return Schedule(interval, interval, callback);
        }

        /// <summary>
        /// 取消有效任务。允许回调取消自己或尚未触发的任务。
        /// </summary>
        public bool Cancel(Handle handle)
        {
            if (!ReferenceEquals(handle.Owner, this))
                return false;

            for (int i = 0; i < _entries.Length; i++)
            {
                if (_entries[i].Id == handle.Id)
                {
                    _entries[i] = default;
                    return true;
                }
            }

            return false;
        }

        /// <summary>
        /// 进入下一 Tick，依截止和排入顺序执行所有到期任务。
        /// </summary>
        public void BeginTick(long tick)
        {
            if (tick != checked(_tick + 1))
                throw new InvalidOperationException("定时器要求在外层按连续 Tick 调用。");

            _tick = tick;
            int index;
            while ((index = FindNextDue()) >= 0)
            {
                Entry entry = _entries[index];
                if (entry.Interval == 0)
                {
                    _entries[index] = default;
                }

                entry.Callback();
                // 回调可能已取消重复任务，并把原槽位用于其他任务。
                if (entry.Interval > 0 && _entries[index].Id == entry.Id)
                {
                    entry.Due = checked(entry.Due + entry.Interval);
                    entry.Sequence = checked(++_sequence);
                    _entries[index] = entry;
                }
            }
        }

        /// <summary>
        /// 撤销剩余任务并释放对回调的引用。
        /// </summary>
        public void Dispose()
        {
            _disposed = true;
            Array.Clear(_entries, 0, _entries.Length);
        }

        /// <summary>
        /// 分配一个空槽位并建立稳定的同截止顺序。
        /// </summary>
        private Handle Schedule(int delay, int interval, Action callback)
        {
            if (_disposed)
                throw new ObjectDisposedException(nameof(FrameTimer));
            if (delay < 1)
                throw new ArgumentOutOfRangeException(nameof(delay));
            if (callback == null)
                throw new ArgumentNullException(nameof(callback));

            for (int i = 0; i < _entries.Length; i++)
            {
                if (_entries[i].Id != 0)
                    continue;

                long due = checked(_tick + delay);
                long id = checked(++_sequence);
                _entries[i] = new Entry
                {
                    Id = id,
                    Due = due,
                    Sequence = id,
                    Interval = interval,
                    Callback = callback
                };
                return new Handle(this, id);
            }

            throw new InvalidOperationException("帧定时器容量已满。");
        }

        /// <summary>
        /// 从有界任务表选取最先到期且仍有效的一项。
        /// </summary>
        private int FindNextDue()
        {
            int bestIndex = -1;
            long bestDue = long.MaxValue;
            long bestSequence = long.MaxValue;
            for (int i = 0; i < _entries.Length; i++)
            {
                ref Entry entry = ref _entries[i];
                if (entry.Id == 0 || entry.Due > _tick)
                    continue;

                if (bestIndex == -1 || entry.Due < bestDue ||
                    (entry.Due == bestDue && entry.Sequence < bestSequence))
                {
                    bestIndex = i;
                    bestDue = entry.Due;
                    bestSequence = entry.Sequence;
                }
            }

            return bestIndex;
        }
    }
}
