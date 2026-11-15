# Project B 三模块 C# 实现代码

2026-11-15 · 首期原型评审稿

本文的 C# 以文件为单位给出。帧驱动、共享数值和 HitResolver 可独立接入。战斗部分用 Entitas 1.14.1 生成的组件 API，把两者组合为「部署 → 自动接近与攻击 → 外塔破损 → 核心暴露 → 核心击破或回合超时」。示例战场沿 X 轴行进，用于展示帧、Entitas 与命中接线。阶段 05 的生产移动接管使用 [现成 RVO2](Project_B战斗与局内系统/19-寻路模块实现代码.md)，下文原型的 X 轴积分和 MoveRemainder 只用于原型示例。普通攻击使用指定目标，HitResolver 同时实现二维圆形范围攻击。正式索敌、八方向暴露、牌组、主动技能、完整 Buff 和伤害公式后续由各自已确认的业务规则接入。

| 文件 | 建议目录 | 依赖 |
| --- | --- | --- |
| `FrameClock.cs`、`FrameCore.cs`、`FrameTimer.cs` | `GameLogic/Module/Frame/` | BCL |
| `FixedPoint.cs` | `GameLogic/Math/FixedPoint/` | BCL |
| `HitResolver.cs` | `GameLogic/Module/HitResolution/` | BCL、FixedPoint |
| `ActorComponent.cs`、`ActorState.cs` | `GameLogic/Battle/Components/` | Entitas 1.14.1、FixedPoint |
| `BattleWorld.cs`、`BattleChannel.cs` | `GameLogic/Battle/Simulation/` | Entitas 1.14.1、Frame、HitResolution |
| `ProjectBFrameHost.cs` | `GameLogic/Battle/Host/` | TEngine、Unity 主线程时间、Battle |

目标是明确可实施的最小闭环。时间参数采用评审默认的 60 Hz、最多补 4 步和超额丢整步。原型公式采用整数生命、固定攻防差和最低伤害 0，合法零伤占段资格。结果批复制为只读快照，原型在这里会产生分配，`0 B/Tick` 仍是后续按模块测量的优化目标。未运行 Unity、Jenny、编译、测试或 Profiler。 [帧驱动方案](01-帧驱动独立模块方案.md) · [战斗方案](02-Project_B-战斗模块方案.md) · [HitResolver 方案](03-HitResolver独立模块方案.md)

- [帧驱动代码](#1-帧驱动模块)
- [定点和命中代码](#2-共享定点值与-hitresolver)
- [Entitas 战斗和 TEngine 接入代码](#3-战斗模块)
- [三种调用示例](#4-调用示例与实施顺序)

## 1. 帧驱动模块

### FrameClock.cs

```csharp
using System;

namespace GameLogic.Frame
{
    /// <summary>业务步成功返回后的控制指令。</summary>
    public enum StepDirective { Continue, StopAfterCommit }

    /// <summary>以整数相位消费宿主时间并提交连续逻辑步。</summary>
    public sealed class FrameClock
    {
        public const long PhaseDenominator = 1_000_000_000_000_000L;
        public const int NormalScaleRaw = 1_000_000;
        private const long MaxElapsedNs = 1_000_000_000L;
        private readonly int _maxSteps;
        private bool _advancing;
        private bool _stepRequested;
        private bool _paused;

        /// <summary>创建固定步长时钟。</summary>
        public FrameClock(int tickRate, int maxSteps)
        {
            if (tickRate < 1 || tickRate > 240 || maxSteps < 1)
                throw new ArgumentOutOfRangeException();
            TickRate = tickRate;
            _maxSteps = maxSteps;
        }

        public int TickRate { get; }
        public long CommittedTick { get; private set; }
        public long Phase { get; private set; }
        public long ClippedNanoseconds { get; private set; }
        public long DroppedSteps { get; private set; }

        /// <summary>切换调试暂停，恢复时清除未消耗的单步请求。</summary>
        public void SetDebugPaused(bool paused)
        {
            _paused = paused;
            if (!paused) _stepRequested = false;
        }

        /// <summary>暂停期间挂起一次单步。</summary>
        public void RequestDebugStep()
        {
            if (!_paused) throw new InvalidOperationException("单步要求时钟处于暂停状态。");
            _stepRequested = true;
        }

        /// <summary>执行最多配置数量的步。回调抛错时保留最后提交编号。</summary>
        public void Advance(long elapsedNs, int scaleRaw, Func<long, StepDirective> executeStep)
        {
            if (_advancing) throw new InvalidOperationException("时钟推进重入。");
            if (elapsedNs < 0 || scaleRaw < 0 || scaleRaw > 4 * NormalScaleRaw)
                throw new ArgumentOutOfRangeException();

            _advancing = true;
            try
            {
                ClippedNanoseconds = 0;
                DroppedSteps = 0;
                if (_paused)
                {
                    if (_stepRequested)
                    {
                        _stepRequested = false;
                        RunStep(executeStep);
                        Phase = 0;
                    }
                    return;
                }

                if (scaleRaw == 0) return;
                long admitted = Math.Min(elapsedNs, MaxElapsedNs);
                ClippedNanoseconds = elapsedNs - admitted;
                long total = Phase + admitted * scaleRaw * TickRate;
                long due = total / PhaseDenominator;
                Phase = total % PhaseDenominator;
                int budget = (int)Math.Min(due, _maxSteps);
                DroppedSteps = due - budget;
                for (int step = 0; step < budget; step++)
                {
                    if (RunStep(executeStep) == StepDirective.StopAfterCommit || _paused)
                        break;
                }
            }
            finally
            {
                _advancing = false;
            }
        }

        /// <summary>成功回调后提交候选编号。</summary>
        private StepDirective RunStep(Func<long, StepDirective> executeStep)
        {
            long candidate = checked(CommittedTick + 1);
            StepDirective directive = executeStep(candidate);
            CommittedTick = candidate;
            return directive;
        }
    }
}
```

显示侧使用 `clock.Phase / (double)FrameClock.PhaseDenominator`。单次采样上限、倍率上限和步频上限共同将相位乘积限制在有符号 `long` 范围内。回调抛错后应由通道所有者结束会话。

### FrameCore.cs

```csharp
using System;
using System.Collections.Generic;

namespace GameLogic.Frame
{
    /// <summary>使用独立时钟的更新入口。</summary>
    public interface ITimeChannel : IDisposable
    {
        int Order { get; }
        void Advance(long elapsedNs);
    }

    /// <summary>按优先级和注册顺序推进时间通道，拥有已注册实例。</summary>
    public sealed class FrameCore : IDisposable
    {
        private sealed class Entry
        {
            public ITimeChannel Channel;
            public int Order;
            public long Sequence;
            public bool Removed;
        }

        private readonly List<Entry> _channels = new List<Entry>();
        private readonly Queue<Exception> _faults = new Queue<Exception>();
        private long _nextSequence;
        private bool _updating;
        private bool _disposing;
        private bool _disposed;
        private bool _sortNeeded;

        /// <summary>注册时接管通道实例。在分发中新增的实例下一轮生效。</summary>
        public void Register(ITimeChannel channel)
        {
            CheckMutable();
            if (channel == null) throw new ArgumentNullException(nameof(channel));
            if (_channels.Exists(entry => ReferenceEquals(entry.Channel, channel)))
                throw new InvalidOperationException("通道已登记。");

            _channels.Add(new Entry
            {
                Channel = channel, Order = channel.Order, Sequence = checked(++_nextSequence)
            });
            _sortNeeded = true;
        }

        /// <summary>取消更新，等安全边界到达后释放该通道。</summary>
        public void Unregister(ITimeChannel channel)
        {
            CheckMutable();
            foreach (Entry entry in _channels)
            {
                if (!ReferenceEquals(entry.Channel, channel)) continue;
                entry.Removed = true;
                break;
            }

            if (!_updating) Sweep();
        }

        /// <summary>推进本轮生效的通道。失败的通道退场并留下异常记录。</summary>
        public void Update(long elapsedNs)
        {
            CheckMutable();
            if (_updating) throw new InvalidOperationException("帧核心分发重入。");
            if (elapsedNs < 0) throw new ArgumentOutOfRangeException(nameof(elapsedNs));

            if (_sortNeeded)
            {
                _channels.Sort(CompareEntries);
                _sortNeeded = false;
            }

            int activeCount = _channels.Count;
            _updating = true;
            try
            {
                for (int i = 0; i < activeCount; i++)
                {
                    Entry entry = _channels[i];
                    if (entry.Removed) continue;
                    try
                    {
                        entry.Channel.Advance(elapsedNs);
                    }
                    catch (Exception exception)
                    {
                        entry.Removed = true;
                        _faults.Enqueue(exception);
                    }
                }
            }
            finally
            {
                _updating = false;
                Sweep();
            }
        }

        /// <summary>供宿主在分发完成后读取异常。</summary>
        public bool TryReadFault(out Exception fault)
        {
            fault = _faults.Count == 0 ? null : _faults.Dequeue();
            return fault != null;
        }

        /// <summary>释放所有登记通道。</summary>
        public void Dispose()
        {
            if (_disposed) return;
            if (_updating || _disposing) throw new InvalidOperationException("分发中释放帧核心。");

            _disposed = true;
            foreach (Entry entry in _channels) entry.Removed = true;
            Sweep();
        }

        /// <summary>释放已注销实例，单个清理失败不阻断其他清理。</summary>
        private void Sweep()
        {
            _disposing = true;
            try
            {
                for (int i = _channels.Count - 1; i >= 0; i--)
                {
                    Entry entry = _channels[i];
                    if (!entry.Removed) continue;
                    _channels.RemoveAt(i);
                    try
                    {
                        entry.Channel.Dispose();
                    }
                    catch (Exception exception)
                    {
                        _faults.Enqueue(exception);
                    }
                }
            }
            finally
            {
                _disposing = false;
            }
        }

        /// <summary>检查该时点是否可操作核心。</summary>
        private void CheckMutable()
        {
            if (_disposed) throw new ObjectDisposedException(nameof(FrameCore));
            if (_disposing) throw new InvalidOperationException("通道释放期间不可操作帧核心。");
        }

        /// <summary>先比较优先级，再比较唯一的注册序号。</summary>
        private static int CompareEntries(Entry left, Entry right)
        {
            int order = left.Order.CompareTo(right.Order);
            return order != 0 ? order : left.Sequence.CompareTo(right.Sequence);
        }
    }
}
```

通道与宿主在同一线程操作。注销发生在回调里时，仅设置退场标记。本轮扫描的长度在调用之前确定，因此注册新通道不会影响在途顺序。

### FrameTimer.cs

```csharp
using System;
using System.Collections.Generic;

namespace GameLogic.Frame
{
    /// <summary>通道内有界的同步到期任务。回放业务状态优先使用显式截止 Tick。</summary>
    public sealed class FrameTimer : IDisposable
    {
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

        private sealed class Entry
        {
            public long Id;
            public long Due;
            public long Sequence;
            public int Interval;
            public Action Callback;
            public bool Cancelled;
        }

        private readonly List<Entry> _entries;
        private readonly int _capacity;
        private long _sequence;
        private long _tick;
        private bool _dispatching;
        private bool _disposed;

        /// <summary>预留任务容器，初始位置为 Tick 0。</summary>
        public FrameTimer(int capacity)
        {
            if (capacity <= 0) throw new ArgumentOutOfRangeException(nameof(capacity));
            _capacity = capacity;
            _entries = new List<Entry>(capacity);
        }

        /// <summary>登记一个单次到期任务。</summary>
        public Handle Once(int delay, Action callback)
        {
            return Schedule(delay, 0, callback);
        }

        /// <summary>登记一个按原截止时间重复执行的任务。</summary>
        public Handle Repeat(int interval, Action callback)
        {
            return Schedule(interval, interval, callback);
        }

        /// <summary>取消当前计时器内的任务，支持执行中自取消。</summary>
        public bool Cancel(Handle handle)
        {
            if (!ReferenceEquals(handle.Owner, this)) return false;
            for (int i = 0; i < _entries.Count; i++)
            {
                Entry entry = _entries[i];
                if (entry.Id != handle.Id) continue;
                entry.Cancelled = true;
                _entries.RemoveAt(i);
                return true;
            }
            return false;
        }

        /// <summary>进入下一步并按截止时间、登记顺序派发。</summary>
        public void BeginTick(long tick)
        {
            if (_disposed) throw new ObjectDisposedException(nameof(FrameTimer));
            if (_dispatching || tick != checked(_tick + 1))
                throw new InvalidOperationException("计时器要求连续步进。");

            _tick = tick;
            _dispatching = true;
            try
            {
                Entry entry;
                while ((entry = FindDue()) != null)
                {
                    if (entry.Interval == 0) _entries.Remove(entry);
                    entry.Callback();
                    if (entry.Interval > 0 && !entry.Cancelled && !_disposed)
                    {
                        entry.Due = checked(entry.Due + entry.Interval);
                        entry.Sequence = checked(++_sequence);
                    }
                }
            }
            finally
            {
                _dispatching = false;
            }
        }

        /// <summary>清除实存任务和对回调的引用。</summary>
        public void Dispose()
        {
            _disposed = true;
            _entries.Clear();
        }

        /// <summary>插入已验证的任务。</summary>
        private Handle Schedule(int delay, int interval, Action callback)
        {
            if (_disposed) throw new ObjectDisposedException(nameof(FrameTimer));
            if (delay < 1) throw new ArgumentOutOfRangeException(nameof(delay));
            if (callback == null) throw new ArgumentNullException(nameof(callback));
            if (_entries.Count == _capacity) throw new InvalidOperationException("计时器容量已满。");

            long id = checked(++_sequence);
            _entries.Add(new Entry
            {
                Id = id, Due = checked(_tick + delay), Sequence = id,
                Interval = interval, Callback = callback
            });
            return new Handle(this, id);
        }

        /// <summary>在有界任务表里选择下一条已到期任务。</summary>
        private Entry FindDue()
        {
            Entry best = null;
            foreach (Entry entry in _entries)
            {
                if (entry.Due > _tick) continue;
                if (best == null || entry.Due < best.Due ||
                    (entry.Due == best.Due && entry.Sequence < best.Sequence))
                    best = entry;
            }
            return best;
        }
    }
}
```

原型用有界列表表达完整取消语义，适合少量同步任务。需要重放的战斗截止条件由 World 持有。到期回调抛错按整场通道故障处理。

## 2. 共享定点值与 HitResolver

### FixedPoint.cs

```csharp
using System;
using System.Globalization;

namespace GameLogic.FixedPoint
{
    /// <summary>百万分之一刻度的定点值，配置文字在入口一次量化。</summary>
    public readonly struct Fixed64
    {
        public const long Scale = 1_000_000;
        public long Raw { get; }

        /// <summary>从已经量化的原始整数创建定点值。</summary>
        public Fixed64(long raw)
        {
            Raw = raw;
        }

        /// <summary>解析固定文化的十进制文字，最多六位小数。</summary>
        public static Fixed64 Parse(string text)
        {
            if (string.IsNullOrEmpty(text)) throw new FormatException();
            int point = text.IndexOf('.');
            if (point >= 0 && text.Length - point - 1 > 6)
                throw new FormatException("定点配置最多六位小数。");
            const NumberStyles style = NumberStyles.AllowLeadingSign | NumberStyles.AllowDecimalPoint;
            decimal value = decimal.Parse(text, style, CultureInfo.InvariantCulture);
            return new Fixed64(checked((long)(value * Scale)));
        }
    }

    /// <summary>二维定点位置，分量使用 Fixed64 原始值。</summary>
    public readonly struct Point2
    {
        public long XRaw { get; }
        public long YRaw { get; }

        /// <summary>从定点原始坐标创建位置。</summary>
        public Point2(long xRaw, long yRaw)
        {
            XRaw = xRaw;
            YRaw = yRaw;
        }
    }
}
```

这里使用的运算为原始值移动积分、合法域内的减法与几何平方、秒转 Tick；因此本原型只提供构造与解析。以后引入通用定点乘除时，应先保证中间精度，再按原方案向零舍入并检查结果范围。帧时钟使用自己的整数比例类型。

### HitResolver.cs

两个主调用是 `Resolve(...)` 和 `HitLedger.Apply(...)`。`Resolve` 的结果缓冲借用期到同一 Resolver 的下一次 Resolve，账本在调用端明确提交。关闭段发生在该段最后一批之后。首期受击快照每目标一盒，支持同段多个攻击形状。候选排序最后比较攻击形状 ID，受击形状 ID 在此版本恒为主体 ID。

```csharp
using System;
using System.Collections.Generic;
using GameLogic.FixedPoint;

namespace GameLogic.HitResolution
{
    /// <summary>攻击圆和轴对齐受击盒共享的数值范围。</summary>
    public static class HitGeometry
    {
        public const long LimitRaw = 1_000 * Fixed64.Scale;

        /// <summary>保证后续坐标差值和平方和均在 long 范围。</summary>
        public static void CheckAxis(long raw)
        {
            if (raw < -LimitRaw || raw > LimitRaw)
                throw new ArgumentOutOfRangeException(nameof(raw));
        }

        /// <summary>判断闭区间圆盒是否重叠，使用原始整数的平方。</summary>
        public static bool Overlaps(Circle circle, HurtBox box)
        {
            long closestX = Math.Max(box.Min.XRaw, Math.Min(circle.Center.XRaw, box.Max.XRaw));
            long closestY = Math.Max(box.Min.YRaw, Math.Min(circle.Center.YRaw, box.Max.YRaw));
            long dx = circle.Center.XRaw - closestX;
            long dy = circle.Center.YRaw - closestY;
            return dx * dx + dy * dy <= circle.RadiusRaw * circle.RadiusRaw;
        }
    }

    /// <summary>闭区间的攻击圆。</summary>
    public readonly struct Circle
    {
        public readonly Point2 Center;
        public readonly long RadiusRaw;

        /// <summary>验证圆心和半径后创建攻击形状。</summary>
        public Circle(Point2 center, long radiusRaw)
        {
            HitGeometry.CheckAxis(center.XRaw);
            HitGeometry.CheckAxis(center.YRaw);
            if (radiusRaw < 0 || radiusRaw > HitGeometry.LimitRaw)
                throw new ArgumentOutOfRangeException(nameof(radiusRaw));
            Center = center;
            RadiusRaw = radiusRaw;
        }
    }

    /// <summary>由两个定点角构成的主体受击盒。</summary>
    public readonly struct HurtBox
    {
        public readonly Point2 Min;
        public readonly Point2 Max;

        /// <summary>验证闭区间端点后创建受击盒。</summary>
        public HurtBox(Point2 min, Point2 max)
        {
            HitGeometry.CheckAxis(min.XRaw);
            HitGeometry.CheckAxis(min.YRaw);
            HitGeometry.CheckAxis(max.XRaw);
            HitGeometry.CheckAxis(max.YRaw);
            if (min.XRaw > max.XRaw || min.YRaw > max.YRaw)
                throw new ArgumentException("受击盒端点倒置。");
            Min = min;
            Max = max;
        }
    }

    /// <summary>一次攻击的显式值输入。DirectTargetId 为 0 时使用圆形查询。</summary>
    public readonly struct AttackRequest
    {
        public readonly long AttackId;
        public readonly int SegmentId;
        public readonly long SourceId;
        public readonly int Team;
        public readonly int DefinitionId;
        public readonly int Power;
        public readonly long DirectTargetId;
        public readonly int ShapeId;
        public readonly Circle Area;

        /// <summary>创建带进攻数值快照的攻击请求。</summary>
        public AttackRequest(long attackId, int segmentId, long sourceId, int team,
            int definitionId, int power, long directTargetId, int shapeId, Circle area)
        {
            if (attackId <= 0 || sourceId <= 0 || segmentId < 0 || power < 0 ||
                directTargetId < 0 || (directTargetId == 0 ? shapeId <= 0 : shapeId != 0))
                throw new ArgumentException("攻击身份或形状不合法。");

            AttackId = attackId;
            SegmentId = segmentId;
            SourceId = sourceId;
            Team = team;
            DefinitionId = definitionId;
            Power = power;
            DirectTargetId = directTargetId;
            ShapeId = shapeId;
            Area = area;
        }
    }

    /// <summary>当批冻结的目标数据。</summary>
    public readonly struct TargetSnapshot
    {
        public readonly long Id;
        public readonly int Team;
        public readonly int Hp;
        public readonly int Defense;
        public readonly bool Protected;
        public readonly HurtBox Box;

        /// <summary>创建供资格和伤害公式读取的目标快照。</summary>
        public TargetSnapshot(long id, int team, int hp, int defense, bool protectedFromHit, HurtBox box)
        {
            if (id <= 0 || hp < 0 || defense < 0) throw new ArgumentException("目标快照不合法。");
            Id = id;
            Team = team;
            Hp = hp;
            Defense = defense;
            Protected = protectedFromHit;
            Box = box;
        }
    }

    /// <summary>只读取传入快照的资格与计算伤害规则。</summary>
    public interface IHitRule
    {
        bool IsEligible(AttackRequest attack, TargetSnapshot target);
        long Calculate(AttackRequest attack, TargetSnapshot target);
    }

    /// <summary>一次确认命中。序号由命中列表位置给出。</summary>
    public readonly struct ResolvedHit
    {
        public readonly long AttackId;
        public readonly int SegmentId;
        public readonly long SourceId;
        public readonly long TargetId;
        public readonly int CalculatedDamage;
        public readonly int AppliedDamage;
        public readonly int HpBefore;
        public readonly int HpAfter;

        public bool Defeated { get { return HpBefore > 0 && HpAfter == 0; } }

        /// <summary>保留计算伤害、实际扣血及生命变化。</summary>
        internal ResolvedHit(AttackRequest attack, long targetId, int damage, int before)
        {
            AttackId = attack.AttackId;
            SegmentId = attack.SegmentId;
            SourceId = attack.SourceId;
            TargetId = targetId;
            CalculatedDamage = damage;
            HpBefore = before;
            AppliedDamage = Math.Min(damage, before);
            HpAfter = before - AppliedDamage;
        }
    }

    /// <summary>单场持有的命中记录，结算读取，场景提交方写入。</summary>
    public sealed class HitLedger
    {
        private readonly HashSet<(long Attack, int Segment, long Target)> _keys;
        private readonly List<(long Attack, int Segment, long Target)> _retired;
        private readonly int _capacity;

        /// <summary>预留活跃命中上限。</summary>
        public HitLedger(int capacity)
        {
            if (capacity < 1) throw new ArgumentOutOfRangeException(nameof(capacity));
            _capacity = capacity;
            _keys = new HashSet<(long, int, long)>(capacity);
            _retired = new List<(long, int, long)>(capacity);
        }

        /// <summary>读取旧批已确认的命中资格。</summary>
        public bool Contains(long attack, int segment, long target)
        {
            return _keys.Contains((attack, segment, target));
        }

        /// <summary>按关闭段回收前的临时峰值预检容量。</summary>
        public void EnsureCapacityFor(int additional)
        {
            if (additional < 0 || additional > _capacity - _keys.Count)
                throw new InvalidOperationException("命中账本容量不足。");
        }

        /// <summary>提交本批增量后清理刚关闭的段。</summary>
        public void Apply(IReadOnlyList<ResolvedHit> hits, ISet<(long Attack, int Segment)> closed)
        {
            EnsureCapacityFor(hits.Count);
            foreach (ResolvedHit hit in hits)
                _keys.Add((hit.AttackId, hit.SegmentId, hit.TargetId));

            if (closed.Count == 0) return;
            foreach (var key in _keys)
            {
                if (closed.Contains((key.Attack, key.Segment))) _retired.Add(key);
            }
            foreach (var key in _retired) _keys.Remove(key);
            _retired.Clear();
        }
    }

    /// <summary>独立的几何候选、段内去重和生命结算。</summary>
    public sealed class HitResolver
    {
        private readonly struct Candidate
        {
            public readonly AttackRequest Attack;
            public readonly long TargetId;
            public readonly int TargetIndex;

            public Candidate(AttackRequest attack, long targetId, int targetIndex)
            {
                Attack = attack;
                TargetId = targetId;
                TargetIndex = targetIndex;
            }
        }

        private readonly Dictionary<long, int> _targetIndex;
        private readonly Dictionary<long, AttackRequest> _instances;
        private readonly Dictionary<(long, int, long, int), AttackRequest> _requests;
        private readonly List<Candidate> _candidates;
        private readonly List<ResolvedHit> _hits;
        private readonly IReadOnlyList<ResolvedHit> _result;
        private readonly int[] _workingHp;
        private readonly int _maxRequests;
        private readonly int _maxCandidates;

        /// <summary>按调用场景的容量预分配工作缓冲。</summary>
        public HitResolver(int maxTargets, int maxRequests, int maxCandidates)
        {
            if (maxTargets < 1 || maxRequests < 1 || maxCandidates < 1)
                throw new ArgumentOutOfRangeException();

            _maxRequests = maxRequests;
            _maxCandidates = maxCandidates;
            _targetIndex = new Dictionary<long, int>(maxTargets);
            _instances = new Dictionary<long, AttackRequest>(maxRequests);
            _requests = new Dictionary<(long, int, long, int), AttackRequest>(maxRequests);
            _candidates = new List<Candidate>(maxCandidates);
            _hits = new List<ResolvedHit>(maxCandidates);
            _result = _hits.AsReadOnly();
            _workingHp = new int[maxTargets];
        }

        /// <summary>结算完整批次。失败时调用端不取得部分结果，也不改写账本。</summary>
        public IReadOnlyList<ResolvedHit> Resolve(IReadOnlyList<AttackRequest> attacks,
            IReadOnlyList<TargetSnapshot> targets, HitLedger ledger, IHitRule rule)
        {
            if (attacks.Count > _maxRequests || targets.Count > _workingHp.Length)
                throw new InvalidOperationException("命中输入容量不足。");

            _targetIndex.Clear();
            _instances.Clear();
            _requests.Clear();
            _candidates.Clear();
            _hits.Clear();
            for (int i = 0; i < targets.Count; i++)
            {
                if (targets[i].Id <= 0) throw new ArgumentException("未初始化的受击快照。");
                _targetIndex.Add(targets[i].Id, i);
                _workingHp[i] = targets[i].Hp;
            }

            for (int i = 0; i < attacks.Count; i++)
            {
                AttackRequest attack = attacks[i];
                if (!AcceptRequest(attack)) continue;

                if (attack.DirectTargetId != 0)
                {
                    if (_targetIndex.TryGetValue(attack.DirectTargetId, out int index))
                        AddCandidate(attack, targets[index].Id, index);
                    continue;
                }

                for (int j = 0; j < targets.Count; j++)
                {
                    if (HitGeometry.Overlaps(attack.Area, targets[j].Box))
                        AddCandidate(attack, targets[j].Id, j);
                }
            }

            _candidates.Sort(CompareCandidates);
            SettleGroups(targets, ledger, rule);
            return _result;
        }

        /// <summary>校验实例元数据和重复请求的身份，完全重复只收一次。</summary>
        private bool AcceptRequest(AttackRequest attack)
        {
            if (attack.AttackId <= 0) throw new ArgumentException("未初始化的攻击请求。");
            if (_instances.TryGetValue(attack.AttackId, out AttackRequest first))
            {
                if (first.SourceId != attack.SourceId || first.Team != attack.Team ||
                    first.DefinitionId != attack.DefinitionId)
                    throw new InvalidOperationException("攻击实例元数据冲突。");
            }
            else
            {
                _instances.Add(attack.AttackId, attack);
            }

            var key = (attack.AttackId, attack.SegmentId, attack.DirectTargetId, attack.ShapeId);
            if (_requests.TryGetValue(key, out AttackRequest previous))
            {
                if (previous.Power != attack.Power ||
                    (attack.DirectTargetId == 0 &&
                     (previous.Area.Center.XRaw != attack.Area.Center.XRaw ||
                      previous.Area.Center.YRaw != attack.Area.Center.YRaw ||
                      previous.Area.RadiusRaw != attack.Area.RadiusRaw)))
                    throw new InvalidOperationException("同身份请求载荷冲突。");
                return false;
            }

            _requests.Add(key, attack);
            return true;
        }

        /// <summary>候选全量收集，容量不足即中止本批。</summary>
        private void AddCandidate(AttackRequest attack, long targetId, int index)
        {
            if (_candidates.Count == _maxCandidates)
                throw new InvalidOperationException("命中候选容量不足。");
            _candidates.Add(new Candidate(attack, targetId, index));
        }

        /// <summary>对每个实例、段和目标取第一个合法候选。</summary>
        private void SettleGroups(IReadOnlyList<TargetSnapshot> targets, HitLedger ledger, IHitRule rule)
        {
            int first = 0;
            while (first < _candidates.Count)
            {
                Candidate head = _candidates[first];
                int end = first + 1;
                while (end < _candidates.Count && CompareKeys(head, _candidates[end]) == 0) end++;

                if (_workingHp[head.TargetIndex] > 0 &&
                    !ledger.Contains(head.Attack.AttackId, head.Attack.SegmentId, head.TargetId))
                {
                    TargetSnapshot target = targets[head.TargetIndex];
                    for (int i = first; i < end; i++)
                    {
                        AttackRequest attack = _candidates[i].Attack;
                        if (!rule.IsEligible(attack, target)) continue;

                        long damage = rule.Calculate(attack, target);
                        if (damage < 0 || damage > int.MaxValue)
                            throw new InvalidOperationException("非法计算伤害。");
                        var hit = new ResolvedHit(attack, target.Id, (int)damage, _workingHp[head.TargetIndex]);
                        _workingHp[head.TargetIndex] = hit.HpAfter;
                        _hits.Add(hit);
                        break;
                    }
                }
                first = end;
            }
        }

        /// <summary>生成独立于输入枚举顺序的候选排序。</summary>
        private static int CompareCandidates(Candidate left, Candidate right)
        {
            int key = CompareKeys(left, right);
            if (key != 0) return key;

            bool leftIsArea = left.Attack.DirectTargetId == 0;
            bool rightIsArea = right.Attack.DirectTargetId == 0;
            int kind = leftIsArea.CompareTo(rightIsArea);
            return kind != 0 ? kind : left.Attack.ShapeId.CompareTo(right.Attack.ShapeId);
        }

        /// <summary>命中资格跨形状和批次共享同一个键。</summary>
        private static int CompareKeys(Candidate left, Candidate right)
        {
            int attack = left.Attack.AttackId.CompareTo(right.Attack.AttackId);
            if (attack != 0) return attack;
            int segment = left.Attack.SegmentId.CompareTo(right.Attack.SegmentId);
            return segment != 0 ? segment : left.TargetId.CompareTo(right.TargetId);
        }
    }
}
```

`ResolvedHit.HpAfter` 按笔递推，最后一条即该目标在本批的最终生命，`Defeated` 只在第一次从正值归零时成立。调用方应用生命前可先归并为最终生命写入，逐笔伤害事实继续按 Resolver 的返回顺序保存。用于跨批攻击的实例身份和段关闭由调用方维护。

## 3. 战斗模块

### 3.1 Jenny 生成接缝

现有 `Jenny.properties` 的输入工程为仓库根下 `Tools/Entitas/EntitasGen/EntitasGen.csproj`，组件扫描和输出指向已删除的 EntitasDemo。正式接入时将 Context 改为 `Battle`，将输出改为 `Assets/GameScripts/HotFix/GameLogic/Battle/Generated`。在解析工程中只纳入正式组件、它们使用的 `ActorState.cs`、`FixedPoint.cs` 和必要引用。`CleanTargetDirectoryPostProcessor` 开启时，输出目录只存生成文件。

以下 `ActorComponent` 沿用 1.14.1 的 `[Context("Battle")]`，工具项目依赖 `Entitas.CodeGeneration.Attributes`。生成后由 Jenny 提供 `Contexts.battle`、`BattleEntity.AddActor(ActorState)`、`BattleEntity.ReplaceActor(ActorState)` 和 `BattleEntity.actor.Value`。原 `Assets/Editor/EntitasDemoTest.cs` 仍引用旧 Demo API，正式迁移时一并处置。原型关闭对应的 `ContextObserverGenerator` 接入，避免每场自动创建全局 Editor 观察对象。 [当前 Jenny 配置](../../Jenny.properties) · [当前生成项目](../../../Tools/Entitas/EntitasGen/EntitasGen.csproj) · [Entitas 生成规则](../../.agents/skills/entitas-dev/references/jenny-and-integration.md)

```properties
Jenny.Plugins.ProjectPath = ../Tools/Entitas/EntitasGen/EntitasGen.csproj
Jenny.Plugins.TargetDirectory = Assets/GameScripts/HotFix/GameLogic/Battle/Generated
Entitas.CodeGeneration.Plugins.Contexts = Battle
```

解析项目的 `Compile` 项由下面两行替换旧 Demo 输入，原 Entitas DLL 的 `Reference` 项继续供 Roslyn 解析。若有别的组件使用 `Game`，需按实际 Context 和扫描范围同时保留它们。

```xml
<ItemGroup>
  <Compile Include="../../../UnityProject/Assets/GameScripts/HotFix/GameLogic/Battle/Components/*.cs" />
  <Compile Include="../../../UnityProject/Assets/GameScripts/HotFix/GameLogic/Math/FixedPoint/FixedPoint.cs" />
</ItemGroup>
```

### ActorState.cs

```csharp
using GameLogic.FixedPoint;

namespace GameLogic.ProjectB
{
    /// <summary>原型中支持的战场对象。</summary>
    public enum ActorKind { Unit, Tower, Core }

    /// <summary>实体组件保存的值。修改时复制并通过生成 API 替换。</summary>
    public struct ActorState
    {
        public long Id;
        public int Team;
        public ActorKind Kind;
        public Point2 Position;
        public long SpeedRaw;
        public long MoveRemainder;
        public long RangeRaw;
        public int Hp;
        public int Power;
        public int Defense;
        public int AttackIntervalTicks;
        public long NextAttackTick;
        public long ExpireTick;
    }
}
```

### ActorComponent.cs

```csharp
using Entitas;
using Entitas.CodeGeneration.Attributes;
using GameLogic.ProjectB;

/// <summary>首期战场数据组件。生成的 Context 为 Battle。</summary>
[Context("Battle")]
public sealed class ActorComponent : IComponent
{
    public ActorState Value;
}
```

原型使用一个值组件缩短完整示例。正式拆分单位和建筑写入方时，保留同一笔命中结果，由各所有者的系统提交自己的组件。

### BattleWorld.cs

```csharp
using System;
using System.Collections.Generic;
using Entitas;
using GameLogic.FixedPoint;
using GameLogic.HitResolution;

namespace GameLogic.ProjectB
{
    public enum DepartureReason { Defeated, CoreCascade, Expired, RoundRecovery }

    /// <summary>对象离场事实。仅直接击破的 HitOrdinal 为非负值。</summary>
    public readonly struct Departure
    {
        public readonly long ActorId;
        public readonly ActorKind Kind;
        public readonly DepartureReason Reason;
        public readonly int HitOrdinal;

        /// <summary>保存离场原因和可选来源命中。</summary>
        public Departure(ActorState actor, DepartureReason reason, int hitOrdinal = -1)
        {
            ActorId = actor.Id;
            Kind = actor.Kind;
            Reason = reason;
            HitOrdinal = hitOrdinal;
        }
    }

    /// <summary>可以跨 World 释放边界持有的单步值结果。</summary>
    public sealed class BattleTickResult
    {
        public long BattleId { get; }
        public long Tick { get; }
        public bool CoreExposed { get; }
        public bool CoreDestroyed { get; }
        public bool TimedOut { get; }
        public bool Ended { get { return CoreDestroyed || TimedOut; } }
        public IReadOnlyList<ResolvedHit> Hits { get; }
        public IReadOnlyList<Departure> Departures { get; }
        public IReadOnlyList<ActorState> Actors { get; }

        /// <summary>复制工作区数据，后续步进不能改变已提交结果。</summary>
        internal BattleTickResult(long battleId, long tick, bool coreExposed, bool coreDestroyed,
            bool timedOut, IReadOnlyList<ResolvedHit> hits, List<Departure> departures, List<ActorState> actors)
        {
            BattleId = battleId;
            Tick = tick;
            CoreExposed = coreExposed;
            CoreDestroyed = coreDestroyed;
            TimedOut = timedOut;
            var hitCopy = new ResolvedHit[hits.Count];
            for (int i = 0; i < hitCopy.Length; i++) hitCopy[i] = hits[i];
            Hits = Array.AsReadOnly(hitCopy);
            Departures = Array.AsReadOnly(departures.ToArray());
            Actors = Array.AsReadOnly(actors.ToArray());
        }
    }

    /// <summary>每回合独占 Entitas 世界、攻击编号和命中账本。</summary>
    public sealed class BattleWorld : IDisposable
    {
        private const int MaxActors = 64;
        private const int MaxCommands = 32;
        private const int Player = 1;
        private const int Enemy = 2;
        private const long HalfSizeRaw = Fixed64.Scale / 4;

        private readonly struct Summon
        {
            public readonly long Tick;
            public readonly long XRaw;

            public Summon(long tick, long xRaw)
            {
                Tick = tick;
                XRaw = xRaw;
            }
        }

        private sealed class Stage : IExecuteSystem
        {
            private readonly Action _execute;

            /// <summary>存储由根树装配的一段战场逻辑。</summary>
            public Stage(Action execute) { _execute = execute; }

            /// <summary>在当前步的装配顺序中执行。</summary>
            public void Execute() { _execute(); }
        }

        private sealed class RemovalStage : ICleanupSystem
        {
            private readonly BattleWorld _world;

            /// <summary>指定需要清理的 World。</summary>
            public RemovalStage(BattleWorld world) { _world = world; }

            /// <summary>在本步事实完成后统一清理。</summary>
            public void Cleanup() { _world.RemoveDeparted(); }
        }

        private sealed class PrototypeHitRule : IHitRule
        {
            /// <summary>合法目标必须属于对方并且可受击。</summary>
            public bool IsEligible(AttackRequest attack, TargetSnapshot target)
            {
                return attack.Team != target.Team && !target.Protected;
            }

            /// <summary>原型整数攻防差，最小伤害为零。</summary>
            public long Calculate(AttackRequest attack, TargetSnapshot target)
            {
                return Math.Max(0L, (long)attack.Power - target.Defense);
            }
        }

        private readonly Contexts _contexts = new Contexts();
        private readonly Systems _systems = new Systems();
        private readonly SortedDictionary<long, BattleEntity> _actors = new SortedDictionary<long, BattleEntity>();
        private readonly Queue<Summon> _commands = new Queue<Summon>(MaxCommands);
        private readonly Dictionary<long, long> _targetsByActor = new Dictionary<long, long>(MaxActors);
        private readonly Dictionary<long, int> _finalHp = new Dictionary<long, int>(MaxActors);
        private readonly List<AttackRequest> _attacks = new List<AttackRequest>(MaxActors);
        private readonly List<TargetSnapshot> _targets = new List<TargetSnapshot>(MaxActors);
        private readonly List<ActorState> _snapshot = new List<ActorState>(MaxActors);
        private readonly List<Departure> _departures = new List<Departure>(MaxActors);
        private readonly HashSet<(long Attack, int Segment)> _closed =
            new HashSet<(long, int)>(MaxActors);
        private readonly HitLedger _ledger = new HitLedger(MaxActors);
        private readonly HitResolver _resolver = new HitResolver(MaxActors, MaxActors, MaxActors);
        private readonly IHitRule _rule = new PrototypeHitRule();
        private readonly long _deadline;
        private long _actorSequence;
        private long _attackSequence;
        private long _tick;
        private int _tickRate;
        private bool _disposed;
        private bool _coreExposed;
        private bool _coreDestroyed;
        private bool _timedOut;
        private IReadOnlyList<ResolvedHit> _hits = Array.Empty<ResolvedHit>();

        public long BattleId { get; }

        /// <summary>创建一个外塔和一个核心的最小战场。</summary>
        public BattleWorld(long battleId, long deadline)
        {
            if (battleId < 1 || deadline < 1) throw new ArgumentOutOfRangeException();
            BattleId = battleId;
            _deadline = deadline;

            Spawn(Enemy, ActorKind.Tower, 2 * Fixed64.Scale, 3, 1, 0);
            Spawn(Enemy, ActorKind.Core, 4 * Fixed64.Scale, 6, 1, 0);

            _systems.Add(new Stage(ApplyCommands));
            _systems.Add(new Stage(SelectTargetsAndMove));
            _systems.Add(new Stage(CollectAndResolveHits));
            _systems.Add(new Stage(DeriveExitAndDepartures));
            _systems.Add(new RemovalStage(this));
            _systems.Initialize();
        }

        /// <summary>生成供开战发布的 Tick 0 快照。</summary>
        public BattleTickResult InitialResult()
        {
            return CaptureResult();
        }

        /// <summary>将已分配到下一步的原型召唤指令登记到本场。</summary>
        public bool TryQueueSummon(long tick, long xRaw)
        {
            if (_disposed || _coreDestroyed || _timedOut ||
                tick != _tick + 1 || tick > _deadline || _commands.Count == MaxCommands ||
                _commands.Count >= MaxActors - _actors.Count)
                return false;
            if (xRaw < -HitGeometry.LimitRaw + HalfSizeRaw ||
                xRaw > HitGeometry.LimitRaw - HalfSizeRaw)
                return false;

            _commands.Enqueue(new Summon(tick, xRaw));
            return true;
        }

        /// <summary>执行一个候选 Tick 并生成待提交的值批次。</summary>
        public BattleTickResult RunTick(long tick, int tickRate)
        {
            if (_disposed || _coreDestroyed || _timedOut || tick != checked(_tick + 1))
                throw new InvalidOperationException("战场无法执行该 Tick。");
            if (tickRate < 1 || tickRate > 240) throw new ArgumentOutOfRangeException(nameof(tickRate));

            _tick = tick;
            _tickRate = tickRate;
            _departures.Clear();
            _systems.Execute();
            _systems.Cleanup();
            return CaptureResult();
        }

        /// <summary>停止系统后清空本场 Context。</summary>
        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            _commands.Clear();
            _systems.DeactivateReactiveSystems();
            try
            {
                _systems.TearDown();
            }
            finally
            {
                _actors.Clear();
                _contexts.Reset();
            }
        }

        /// <summary>使用生成方法登记新战场对象。</summary>
        private void Spawn(int team, ActorKind kind, long xRaw, int hp, int power, long speedRaw)
        {
            long id = checked(++_actorSequence);
            BattleEntity actor = _contexts.battle.CreateEntity();
            actor.AddActor(new ActorState
            {
                Id = id, Team = team, Kind = kind, Position = new Point2(xRaw, 0),
                Hp = hp, Power = power, SpeedRaw = speedRaw, RangeRaw = Fixed64.Scale,
                AttackIntervalTicks = 1, NextAttackTick = _tick
            });
            _actors.Add(id, actor);
        }

        /// <summary>按队列接收顺序消费本步测试指令。</summary>
        private void ApplyCommands()
        {
            while (_commands.Count > 0 && _commands.Peek().Tick == _tick)
            {
                Summon command = _commands.Dequeue();
                Spawn(Player, ActorKind.Unit, command.XRaw, 10, 3, 60 * Fixed64.Scale);
            }
        }

        /// <summary>从同一个移动前快照选择最近合法对手，再更新移动。</summary>
        private void SelectTargetsAndMove()
        {
            _targetsByActor.Clear();
            foreach (BattleEntity entity in _actors.Values)
            {
                ActorState source = entity.actor.Value;
                if (!CanInteract(source)) continue;

                long bestId = 0;
                long bestDistance = long.MaxValue;
                foreach (BattleEntity candidate in _actors.Values)
                {
                    ActorState target = candidate.actor.Value;
                    if (target.Team == source.Team || !CanInteract(target)) continue;
                    long distance = Math.Abs(target.Position.XRaw - source.Position.XRaw);
                    // SortedDictionary 保证等距时保留业务 ID 较小的一方。
                    if (distance >= bestDistance) continue;
                    bestDistance = distance;
                    bestId = target.Id;
                }

                if (bestId != 0) _targetsByActor.Add(source.Id, bestId);
            }

            // 先固定全部目标位置，再逐个写回，防止移动先后改变同一步输入。
            CopyActors();
            foreach (ActorState source in _snapshot)
            {
                if (source.SpeedRaw == 0 || !CanInteract(source)) continue;
                ActorState moved = source;
                if (_targetsByActor.TryGetValue(source.Id, out long targetId))
                {
                    long targetX = FindSnapshot(targetId).Position.XRaw;
                    IntegrateToward(ref moved, targetX, _tickRate);
                }
                else
                {
                    moved.MoveRemainder = 0;
                }

                if (moved.Position.XRaw != source.Position.XRaw || moved.MoveRemainder != source.MoveRemainder)
                    _actors[moved.Id].ReplaceActor(moved);
            }
        }

        /// <summary>收集攻击和受击数据，统一结算并通过生成方法写回。</summary>
        private void CollectAndResolveHits()
        {
            _attacks.Clear();
            _targets.Clear();
            _closed.Clear();
            _finalHp.Clear();

            foreach (BattleEntity entity in _actors.Values)
            {
                ActorState source = entity.actor.Value;
                if (!IsPresent(source)) continue;
                long x = source.Position.XRaw;
                var box = new HurtBox(new Point2(x - HalfSizeRaw, -HalfSizeRaw),
                    new Point2(x + HalfSizeRaw, HalfSizeRaw));
                _targets.Add(new TargetSnapshot(source.Id, source.Team, source.Hp, source.Defense,
                    source.Kind == ActorKind.Core && !_coreExposed, box));

                if (!CanInteract(source) || _tick < source.NextAttackTick ||
                    !_targetsByActor.TryGetValue(source.Id, out long targetId))
                    continue;
                ActorState target = _actors[targetId].actor.Value;
                if (Math.Abs(target.Position.XRaw - x) > source.RangeRaw) continue;

                long attack = checked(++_attackSequence);
                _attacks.Add(new AttackRequest(attack, 0, source.Id, source.Team, 1, source.Power,
                    targetId, 0, default));
                _closed.Add((attack, 0));
                source.NextAttackTick = checked(_tick + source.AttackIntervalTicks);
                entity.ReplaceActor(source);
            }

            _hits = _resolver.Resolve(_attacks, _targets, _ledger, _rule);
            _ledger.EnsureCapacityFor(_hits.Count);
            foreach (ResolvedHit hit in _hits)
            {
                if (!_actors.ContainsKey(hit.TargetId))
                    throw new InvalidOperationException("命中批次的目标已离场。");
                _finalHp[hit.TargetId] = hit.HpAfter;
            }

            foreach (BattleEntity entity in _actors.Values)
            {
                ActorState actor = entity.actor.Value;
                if (!_finalHp.TryGetValue(actor.Id, out int hp) || actor.Hp == hp) continue;
                actor.Hp = hp;
                entity.ReplaceActor(actor);
            }
            _ledger.Apply(_hits, _closed);
        }

        /// <summary>从命中事实派生核心暴露、连带破损和回合终止。</summary>
        private void DeriveExitAndDepartures()
        {
            for (int i = 0; i < _hits.Count; i++)
            {
                ResolvedHit hit = _hits[i];
                if (!hit.Defeated) continue;
                ActorState actor = _actors[hit.TargetId].actor.Value;
                _departures.Add(new Departure(actor, DepartureReason.Defeated, i));
                if (actor.Kind == ActorKind.Core) _coreDestroyed = true;
            }

            _timedOut = _tick == _deadline;
            bool outerAlive = false;
            foreach (BattleEntity entity in _actors.Values)
            {
                ActorState actor = entity.actor.Value;
                if (actor.Hp == 0) continue;
                if (_coreDestroyed && actor.Kind == ActorKind.Tower && actor.Team == Enemy)
                {
                    actor.Hp = 0;
                    entity.ReplaceActor(actor);
                    _departures.Add(new Departure(actor, DepartureReason.CoreCascade));
                }
                else if (actor.ExpireTick != 0 && _tick >= actor.ExpireTick)
                {
                    _departures.Add(new Departure(actor, DepartureReason.Expired));
                }
                else if ((_coreDestroyed || _timedOut) && actor.Kind == ActorKind.Unit && actor.Team == Player)
                {
                    _departures.Add(new Departure(actor, DepartureReason.RoundRecovery));
                }
                else if (actor.Kind == ActorKind.Tower && actor.Team == Enemy)
                {
                    outerAlive = true;
                }
            }

            // 放在命中步骤之后，新的暴露状态从下一步开始生效。
            _coreExposed = !outerAlive;
        }

        /// <summary>派生阶段完成后，统一销毁已记录离场的实体。</summary>
        private void RemoveDeparted()
        {
            foreach (Departure departure in _departures)
            {
                _actors[departure.ActorId].Destroy();
                _actors.Remove(departure.ActorId);
            }
        }

        /// <summary>判断存续区间 [Spawn, Expire) 中的存活实体。</summary>
        private bool IsPresent(ActorState actor)
        {
            return actor.Hp > 0 && (actor.ExpireTick == 0 || _tick < actor.ExpireTick);
        }

        /// <summary>第一版以一座外塔作为核心暴露条件。</summary>
        private bool CanInteract(ActorState actor)
        {
            return IsPresent(actor) && (actor.Kind != ActorKind.Core || _coreExposed);
        }

        /// <summary>复制按 ID 排列的当前实体值。</summary>
        private void CopyActors()
        {
            _snapshot.Clear();
            foreach (BattleEntity entity in _actors.Values) _snapshot.Add(entity.actor.Value);
        }

        /// <summary>读取移动前目标值。</summary>
        private ActorState FindSnapshot(long id)
        {
            foreach (ActorState actor in _snapshot)
            {
                if (actor.Id == id) return actor;
            }
            throw new InvalidOperationException("目标不在移动前快照中。");
        }

        /// <summary>固定步积分，并限制移动到目标攻击半径边缘。</summary>
        private static void IntegrateToward(ref ActorState source, long targetX, int tickRate)
        {
            long gap = targetX - source.Position.XRaw;
            long remaining = Math.Abs(gap) - source.RangeRaw;
            if (remaining <= 0)
            {
                source.MoveRemainder = 0;
                return;
            }

            int direction = Math.Sign(gap);
            long sample = checked(direction * source.SpeedRaw + source.MoveRemainder);
            long step = sample / tickRate;
            source.MoveRemainder = sample % tickRate;
            if (Math.Abs(step) >= remaining)
            {
                step = direction * remaining;
                source.MoveRemainder = 0;
            }
            source.Position = new Point2(source.Position.XRaw + step, 0);
        }

        /// <summary>在 Cleanup 后构建可交付的结果。</summary>
        private BattleTickResult CaptureResult()
        {
            CopyActors();
            return new BattleTickResult(BattleId, _tick, _coreExposed, _coreDestroyed, _timedOut,
                _hits, _departures, _snapshot);
        }
    }
}
```

这里的命中批只接受同一步产生的瞬时普攻，因此每个段当步关闭，账本临时容量等于当步可攻击实体数。持续攻击和圆形技能可复用 HitResolver，战斗侧需按实际活跃段持久化身份并设定独立容量。技能能量等会影响下一步的状态在 `DeriveExitAndDepartures` 之前或其所属的当步阶段提交，外部表现消费只读结果。

### BattleChannel.cs

业务结果队列由应用侧持有，World 只负责生成值结果。每个候选步开工前检查容量。时钟成功提交后，该步才进入可读水位。一次补步中第 N 步成功、第 N+1 步抛错时，队列仍能读出 N，故障场通过独立状态上报。

```csharp
using System;
using System.Collections.Generic;
using GameLogic.Frame;

namespace GameLogic.ProjectB
{
    public enum BattleStatus { Pending, Running, Completed, Faulted, Closed }

    /// <summary>会话的只读出站入口，生命周期长于战场。</summary>
    public sealed class BattleFeed
    {
        private readonly Queue<BattleTickResult> _pending;
        private readonly int _capacity;

        public long BattleId { get; }
        public long CommittedThrough { get; private set; } = -1;
        public BattleStatus Status { get; internal set; }
        public Exception Fault { get; internal set; }

        /// <summary>为会话的未消费批次预留空间。</summary>
        internal BattleFeed(long battleId, int capacity)
        {
            BattleId = battleId;
            _capacity = capacity;
            _pending = new Queue<BattleTickResult>(capacity);
        }

        /// <summary>开始修改 World 之前预检查结果出口。</summary>
        internal void EnsureRoom()
        {
            if (_pending.Count >= _capacity) throw new InvalidOperationException("战果队列已满。");
        }

        /// <summary>暂存完整候选步的结果。</summary>
        internal void Stage(BattleTickResult batch)
        {
            _pending.Enqueue(batch);
        }

        /// <summary>将已完成的步暴露给外部消费者。</summary>
        internal void CommitThrough(long tick)
        {
            CommittedThrough = tick;
        }

        /// <summary>按顺序取一个成功提交的只读批次。</summary>
        public bool TryRead(out BattleTickResult batch)
        {
            if (_pending.Count > 0 && _pending.Peek().Tick <= CommittedThrough)
            {
                batch = _pending.Dequeue();
                return true;
            }
            batch = null;
            return false;
        }
    }

    /// <summary>将一条通用时间流接到本场 World 和出站队列。</summary>
    internal sealed class BattleChannel : ITimeChannel
    {
        private readonly FrameCore _core;
        private readonly BattleWorld _world;
        private readonly FrameClock _clock = new FrameClock(60, 4);
        private readonly Func<long, StepDirective> _step;
        private bool _finishRequested;

        public int Order { get { return 0; } }
        public BattleFeed Feed { get; }

        /// <summary>组合纯帧接口、战场和结果队列。</summary>
        internal BattleChannel(FrameCore core, BattleWorld world, BattleFeed feed)
        {
            _core = core;
            _world = world;
            Feed = feed;
            _step = RunCandidate;
        }

        /// <summary>在宿主采样边界发布初态。</summary>
        internal void Activate()
        {
            Feed.EnsureRoom();
            Feed.Stage(_world.InitialResult());
            Feed.CommitThrough(0);
            Feed.Status = BattleStatus.Running;
        }

        /// <summary>从一个当前会话提交测试召唤，目标 Tick 由时钟决定。</summary>
        internal bool TrySummon(long battleId, long xRaw)
        {
            return Feed.Status == BattleStatus.Running && battleId == Feed.BattleId &&
                   _world.TryQueueSummon(checked(_clock.CommittedTick + 1), xRaw);
        }

        /// <summary>处理零到多步，成功水位在退场前转存到宿主队列。</summary>
        public void Advance(long elapsedNs)
        {
            try
            {
                _clock.Advance(elapsedNs, FrameClock.NormalScaleRaw, _step);
            }
            catch (Exception exception)
            {
                MarkFault(exception);
                throw;
            }
            finally
            {
                Feed.CommitThrough(_clock.CommittedTick);
            }

            if (_finishRequested)
            {
                Feed.Status = BattleStatus.Completed;
                _core.Unregister(this);
            }
        }

        /// <summary>保留错误供消费端区别正常战果与会话故障。</summary>
        internal void MarkFault(Exception cause)
        {
            Feed.Status = BattleStatus.Faulted;
            Feed.Fault = cause;
        }

        /// <summary>释放 World。已提交的值批次仍由 BattleFeed 持有。</summary>
        public void Dispose()
        {
            if (Feed.Status == BattleStatus.Pending || Feed.Status == BattleStatus.Running)
                Feed.Status = BattleStatus.Closed;
            _world.Dispose();
        }

        /// <summary>执行一个候选步，完成后将值结果交给帧核心提交。</summary>
        private StepDirective RunCandidate(long tick)
        {
            Feed.EnsureRoom();
            BattleTickResult result = _world.RunTick(tick, _clock.TickRate);
            Feed.Stage(result);
            _finishRequested = result.Ended;
            return _finishRequested ? StepDirective.StopAfterCommit : StepDirective.Continue;
        }
    }
}
```

### ProjectBFrameHost.cs

应用级宿主复用现有 `Singleton<T>` 和 `IUpdate`。战斗开始请求先进入待激活状态，下一次宿主更新在采样后发布 Tick 0。激活当次采样的时间由此前的通道消耗，本场从后续时间段开始。独立消费方通过 `BattleFeed.TryRead` 读取值结果，可放在表现层已有的独立消费阶段。 [GameApp](../../Assets/GameScripts/HotFix/GameLogic/GameApp.cs) · [SingletonSystem](../../Assets/GameScripts/HotFix/GameLogic/SingletonSystem/SingletonSystem.cs) · [Unity 未缩放采样 API](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Time-unscaledTimeAsDouble.html)

```csharp
using System;
using GameLogic.Frame;
using UnityEngine;

namespace GameLogic.ProjectB
{
    /// <summary>在 TEngine 主线程把 Unity 时间喂给帧核心。</summary>
    public sealed class ProjectBFrameHost : Singleton<ProjectBFrameHost>, IUpdate
    {
        private readonly FrameCore _core = new FrameCore();
        private BattleChannel _pending;
        private BattleChannel _active;
        private long _nextBattleId;
        private bool _focused;
        private bool _hasOrigin;
        private double _originSeconds;
        private long _lastElapsedNs;

        /// <summary>绑定前后台状态并准备首次采样。</summary>
        protected override void OnInit()
        {
            _focused = Application.isFocused;
            Application.focusChanged += OnFocusChanged;
        }

        /// <summary>请求在下一采样边界开战，返回本场的结果读取入口。</summary>
        public BattleFeed QueuePrototype(long deadlineTick)
        {
            if (_active != null || _pending != null)
                throw new InvalidOperationException("已有战斗或待启动请求。");

            long battleId = checked(++_nextBattleId);
            var feed = new BattleFeed(battleId, 128);
            _pending = new BattleChannel(_core, new BattleWorld(battleId, deadlineTick), feed);
            return feed;
        }

        /// <summary>在当前会话提交测试部署指令。</summary>
        public bool TrySummon(long battleId, long xRaw)
        {
            return _active != null && _active.TrySummon(battleId, xRaw);
        }

        /// <summary>由局流程主动关闭同一会话，已提交结果仍可读取。</summary>
        public bool TryCloseBattle(long battleId)
        {
            if (_pending != null && _pending.Feed.BattleId == battleId)
            {
                BattleChannel pending = _pending;
                _pending = null;
                pending.Dispose();
                return true;
            }
            if (_active == null || _active.Feed.BattleId != battleId) return false;

            BattleChannel active = _active;
            _active = null;
            _core.Unregister(active);
            return true;
        }

        /// <summary>先推进既有通道，之后再登记等待开战的通道。</summary>
        public void OnUpdate()
        {
            if (!_focused) return;

            _core.Update(SampleElapsed());
            while (_core.TryReadFault(out Exception fault)) Debug.LogException(fault);

            if (_active != null && _active.Feed.Status != BattleStatus.Running)
                _active = null;

            if (_pending == null) return;
            BattleChannel channel = _pending;
            _pending = null;
            try
            {
                channel.Activate();
                _core.Register(channel);
                _active = channel;
            }
            catch (Exception exception)
            {
                channel.MarkFault(exception);
                channel.Dispose();
                Debug.LogException(exception);
            }
        }

        /// <summary>应用退出时解绑宿主并清理尚在场的 World。</summary>
        protected override void OnRelease()
        {
            Application.focusChanged -= OnFocusChanged;
            _core.Dispose();
            while (_core.TryReadFault(out Exception fault)) Debug.LogException(fault);
            _pending?.Dispose();
            _pending = null;
            _active = null;
        }

        /// <summary>焦点变化后重新取采样基准，避免后台时长变成补步。</summary>
        private void OnFocusChanged(bool focused)
        {
            _focused = focused;
            _hasOrigin = false;
        }

        /// <summary>用累计量化后求差保留跨次采样的舍入余量。</summary>
        private long SampleElapsed()
        {
            double now = Time.unscaledTimeAsDouble;
            if (!_hasOrigin)
            {
                _originSeconds = now;
                _lastElapsedNs = 0;
                _hasOrigin = true;
                return 0;
            }

            long elapsedNs = checked((long)Math.Floor((now - _originSeconds) * 1_000_000_000.0));
            long delta = elapsedNs - _lastElapsedNs;
            _lastElapsedNs = elapsedNs;
            return delta;
        }
    }
}
```

以下是对既有宿主的两处精确接线，保留其余成员。使用项目的 Singleton 释放机制。原型由应用主动维持消费节奏，结果队列超容量时退出该场，避免悄悄丢失命中或破损事件。

```csharp
// GameModule.cs，添加到既有 GameModule 类
/// <summary>应用级固定帧宿主。</summary>
public static GameLogic.ProjectB.ProjectBFrameHost Frame
{
    get { return GameLogic.ProjectB.ProjectBFrameHost.Instance; }
}

// GameApp.cs，在既有 StartGameLogic() 内激活一次
GameModule.Frame.Active();
```

## 4. 调用示例与实施顺序

### 只使用帧驱动

```csharp
var clock = new GameLogic.Frame.FrameClock(60, 4);
var observed = new System.Collections.Generic.List<long>();
System.Func<long, GameLogic.Frame.StepDirective> onStep = tick =>
{
    observed.Add(tick);
    return GameLogic.Frame.StepDirective.Continue;
};
clock.Advance(8_000_000, GameLogic.Frame.FrameClock.NormalScaleRaw, onStep);
clock.Advance(9_000_000, GameLogic.Frame.FrameClock.NormalScaleRaw, onStep);
clock.Advance(200_000_000, GameLogic.Frame.FrameClock.NormalScaleRaw, onStep);
// 预期 observed 为 1, 2, 3, 4, 5，DroppedSteps 为 8，Phase 为 20_000_000_000_000。
```

### 只使用 HitResolver

以下可放在独立 .NET 控制台的 `Program.cs`，与 `FixedPoint.cs`、`HitResolver.cs` 一起使用。两批共用一个账本，第二批使用第一次提交后的生命快照。

```csharp
using System;
using System.Collections.Generic;
using GameLogic.FixedPoint;
using GameLogic.HitResolution;

var resolver = new HitResolver(8, 8, 32);
var ledger = new HitLedger(32);
var rule = new ExampleHitRule();
var closed = new HashSet<(long Attack, int Segment)>();
var box = new HurtBox(new Point2(1_000_000, -100_000), new Point2(1_100_000, 100_000));
var shape = new Circle(new Point2(0, 0), 1_000_000);
var targets = new[] { new TargetSnapshot(2, 2, 5, 0, false, box) };
var attacks = new[]
{
    new AttackRequest(1, 0, 1, 1, 1, 3, 0, 1, shape),
    new AttackRequest(1, 0, 1, 1, 1, 3, 0, 2, shape),
    new AttackRequest(2, 0, 1, 1, 1, 4, 2, 0, default)
};
var first = resolver.Resolve(new[] { attacks[0], attacks[1] }, targets, ledger, rule);
int hpAfterFirst = first[0].HpAfter;
ledger.Apply(first, closed);
Console.WriteLine($"首批命中 {first.Count} 次，剩余生命 {hpAfterFirst}。");

var nextTargets = new[] { new TargetSnapshot(2, 2, hpAfterFirst, 0, false, box) };
var second = resolver.Resolve(attacks, nextTargets, ledger, rule);
closed.Add((1, 0));
closed.Add((2, 0));
ledger.Apply(second, closed);
Console.WriteLine($"次批命中 {second.Count} 次，实际扣血 {second[0].AppliedDamage}。");
// 预期：第一批同段双盒只命中一次，扣血 3。第二批同段重叠跳过，
// 只结算实例 2，实际扣血 2，产生唯一的归零事实。

sealed class ExampleHitRule : IHitRule
{
    /// <summary>例程的受击资格。</summary>
    public bool IsEligible(AttackRequest attack, TargetSnapshot target)
    {
        return attack.Team != target.Team && !target.Protected;
    }

    /// <summary>例程的计算伤害。</summary>
    public long Calculate(AttackRequest attack, TargetSnapshot target)
    {
        return Math.Max(0L, (long)attack.Power - target.Defense);
    }
}
```

### 通过 TEngine 走完整战斗

配置用秒表示时，在创建回合前向上量化。对大数先拆整秒与余数，再 checked 加法，避免中间乘法提前溢出。`secondsRaw` 来自已解析的 `Fixed64`，原型默认 60 Hz。

```csharp
/// <summary>将正时长换算为不早于给定秒数的最小截止 Tick。</summary>
public static long ToDurationTicks(GameLogic.FixedPoint.Fixed64 duration, int tickRate)
{
    const long scale = GameLogic.FixedPoint.Fixed64.Scale;
    if (duration.Raw <= 0 || tickRate <= 0) throw new System.ArgumentOutOfRangeException();

    long wholeTicks = checked((duration.Raw / scale) * tickRate);
    long numerator = (duration.Raw % scale) * tickRate;
    long partialTicks = (numerator + scale - 1) / scale;
    return checked(wholeTicks + partialTicks);
}
```

```csharp
// 入口逻辑请求开战，后续表现层保存 feed。
GameLogic.ProjectB.BattleFeed feed = GameModule.Frame.QueuePrototype(deadlineTick: 120);

// 在已接收到 Tick 0 后，由表现输入处提交一次。
bool accepted = GameModule.Frame.TrySummon(feed.BattleId, xRaw: 0);

// 在表现的结果消费阶段。
while (feed.TryRead(out GameLogic.ProjectB.BattleTickResult result))
{
    UnityEngine.Debug.Log($"tick={result.Tick}, hits={result.Hits.Count}, ended={result.Ended}");
}
```

初始塔在 X=2，核心在 X=4，召唤单位攻击范围 1，每 Tick 最多前进 1。按 Tick 1 接收该召唤的演示口径，预期 Tick 1 击破外塔，Tick 2 起核心允许参与战斗，Tick 3/4 先后命中并在 Tick 4 击破核心。该序列是代码推导，用于后续验收。若不提交召唤，回合在截止 Tick 完整执行后终止。

- [ ] **先接 Frame。** 以纯 C# 可控纳秒验证时钟、分发顺序、注销和到期取消。
- [ ] **并行接定点与 HitResolver。** 测相切、反向原始值、同段重复、多个目标、跨批账本、容量不足及旧账本保持。
- [ ] **生成 Entitas 并接 World。** 先直接喂连续候选 Tick 验证命中与 Cleanup，再装配 TEngine 宿主。
- [ ] **接项目正式规则。** 按确定的索敌、地形、牌组、技能及结算口径替换原型逻辑。补步下以相同已分 Tick 的命令比较结果，有需求再测目标规模性能。
