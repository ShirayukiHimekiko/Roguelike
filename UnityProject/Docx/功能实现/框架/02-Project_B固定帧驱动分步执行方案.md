# Project B 固定帧驱动分步执行方案

2026-11-17 · 订阅式源码已落地，运行验收待执行

`FrameManager` 通过普通 `IUpdate` 采样，计算应用级固定 Tick 并同步通知订阅者。战斗、样本等业务在自己的生命周期内绑定回调，各自提交业务结果。[第 01 步现状](01-Project_B游戏生命周期分步实现方案.md) · [第 02 步重构调研](02附-帧驱动订阅与Profiler调研方案.md) · [第 03 步接入](03-Project_B战斗模块分步执行方案.md)

## 1. 调用链与源码

```text
GameApp → FrameManager.Instance → SingletonSystem.IUpdate
         → FrameManager.OnUpdate → FrameClock.Consume(elapsedNs)
         → 每步递增 CurrentTick → TickAdvanced 同步通知
```

| 文件 | 实际职责 |
| --- | --- |
| [FrameManager.cs](../../../Assets/GameScripts/HotFix/GameLogic/Module/Frame/FrameManager.cs) | 采样、全局暂停、调试单步、固定 Tick 发布及帧诊断快照。启动时通过 `GameModule.Debugger` 注册探针。 |
| [FrameClock.cs](../../../Assets/GameScripts/HotFix/GameLogic/Module/Frame/FrameClock.cs) | 管理器内部的固定步预算与整数相位，步频为 60 Hz，每次更新最多发布 4 Tick。 |
| [FrameTimer.cs](../../../Assets/GameScripts/HotFix/GameLogic/Module/Frame/FrameTimer.cs) | 按业务传入的连续 Tick 派发可取消的同步到期任务。 |
| [FixedPoint.cs](../../../Assets/GameScripts/HotFix/GameLogic/Module/Frame/FixedPoint.cs) | `Fixed64` 与 `Point2`。成员用只读字段，十进制定标为百万分之一。 |
| [ClockProbeHandler.cs](../../../Assets/GameScripts/HotFix/GameLogic/Module/Frame/Debug/ClockProbeHandler.cs) · [ClockProbeWindow.cs](../../../Assets/GameScripts/HotFix/GameLogic/Module/Frame/Debug/ClockProbeWindow.cs) | `ClockProbe` 消费 Tick；TEngine 窗口展示 A/B、宿主间隔历史和调整输入。 |

## 2. 实施记录

- [x] **把推进集中到管理器。** 热路径使用一次 `Time.unscaledDeltaTime` 采样，保留不足一纳秒的余量。时钟把单次输入限制为一秒，超额时间和预算之外的整步丢弃分别累加。应用挂起、`GameModule.Base.IsGamePaused` 会停止推进，切回前台后跳过首次采样。调试暂停保留相位，单步前清零相位，合并尚未消费的请求。
- [x] **改为业务订阅。** 使用 `TickAdvanced` 同步事件，按进入的订阅顺序调用。回调内退订影响下一次事件调用，包括同一 Unity Update 的下一次补步。业务局部 Tick 从首次收到通知起独立累计。
- [x] **收紧失败处理。** 帧模块移除了旧调度类型和显式 `try/catch/finally`。探针的预期故障记录失败业务 Tick 并退订，B 继续。意外抛出的异常交给 Unity 日志，当前通知可能在中途停止。全局 Tick 先于通知递增，该编号不会重发。定时器保留连续 Tick、按截止顺序派发、取消和重排检查。
- [x] **调试窗口直接走 TEngine。** 使用正常运行时注册与释放，窗口可见性沿用 TEngine 的配置。窗口保存最近 120 个采样，支持柱形逐帧查看、A/B 对照、全局单步、A 退订与继续、输入记录和预期故障注入。完整窗口关闭或未选中该页时，页面暂停记录历史。
- [x] **加入 Editor Profiler 采样点。** `ProjectB.Frame.Update` 覆盖实际推进，`ProjectB.Frame.Tick` 覆盖一次事件通知，`ProjectB.FrameProbe.Draw` 单独记录调试页绘制。具体看法见附文。
- [ ] **Unity 资源整理。** `FrameCore.cs`、`IFrameHandler.cs` 已清空旧类型，脚本资产待 Unity 删除。目标目录 `Module/FrameModule/` 与定点源码移入 `GameLogic/Utility/` 需要 Unity Pipeline。当前项目仍未发现可连接实例，其包路径指向旧的工作区。

## 3. 关键时序

```text
hostNs = Unity 非缩放时间转整数纳秒
admitted = min(hostNs, 一秒)
wholeSteps, phase = DivRem(phase + admitted × 60, 一秒的纳秒数)
steps = min(wholeSteps, 4)

每一固定步
    CurrentTick += 1
    TickAdvanced?.Invoke(CurrentTick)

业务进入 → frames.TickAdvanced += OnTick
业务暂停或退出 → frames.TickAdvanced -= OnTick
```

业务 OnTick 使用本场已提交水位计算候选，业务规则成功才推进本场的提交水位。帧管理器的 `CurrentTick` 表示应用级逻辑时间。应用内的全局暂停与调试操作在固定 Tick 派发之外受理。

## 4. 待运行验收

| 用例 | 预期 |
| --- | --- |
| 整数边界 | 60 Hz 下依次输入 16,666,666 ns 和 1 ns，分别推进 0、1 Tick。 |
| 宿主切分一致 | 同一秒切成 20 × 50 ms 或 50 × 20 ms，均发布 60 Tick，余量为零。 |
| 补步与裁剪 | 新时钟输入 1.2 秒，裁剪 0.2 秒、发布 4 Tick、丢 56 步。 |
| 回调与退订 | 订阅顺序 A、B 时先 A 后 B。A 在回调里退订，下一个 Tick 只通知 B；重新订阅后 A 的业务编号从原进度继续。 |
| 应用暂停与单步 | 全局暂停冻结发布，恢复后无后台补步。调试暂停连点单步只安排一次发布，当前订阅者各收到一次。 |
| 预期失败 | A 指定业务步预期失败时保留上次提交编号并退订。B 继续，关闭并重开样本后 A、B 从业务 Tick 0 开始。 |
| 面板和 Profiler | 从 TEngine 的 **Project B → Frame Probe** 启动样本。对照补步、暂停和面板开关，核对柱形历史、标记层级与调用次数。 |

本次未主动运行 Unity、编译、测试或 Profiler 录制。
