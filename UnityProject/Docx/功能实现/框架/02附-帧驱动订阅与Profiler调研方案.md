# Project B 帧驱动订阅、调试面板与 Profiler 方案

2026-11-17 · 方案与实施记录

本稿修订第 02 步的推进边界。帧管理器维护应用的固定帧时钟和全局 Tick，业务通过订阅收到当前 Tick 后执行自己的逻辑。探针使用项目已有的 TEngine 调试窗口。Unity Editor 的采样标记归 Unity Profiler 展示。[第 02 步现状](02-Project_B固定帧驱动分步执行方案.md)

## 1. 调度方案

现有 `FrameManager` 把纳秒交给 `FrameCore`，`FrameCore` 再交给 `IFrameHandler.Advance`。样本处理器还各自建立时钟。由此，业务开始前必须实现采样间隔、追帧、暂停、提交四套约定。项目今后的战斗接入只需要一个稳定的业务回调入口。[FrameManager](../../../Assets/GameScripts/HotFix/GameLogic/Module/Frame/FrameManager.cs) · [FrameCore](../../../Assets/GameScripts/HotFix/GameLogic/Module/Frame/FrameCore.cs) · [ClockProbeHandler](../../../Assets/GameScripts/HotFix/GameLogic/Module/Frame/Debug/ClockProbeHandler.cs)

```text
SingletonSystem.IUpdate → FrameManager.OnUpdate
    应用挂起或 GameModule.Base.IsGamePaused → 返回
    后台恢复的首次采样 → 跳过
    量化 unscaledDeltaTime → 用同一个整数相位计算本次应推进几 Tick
    每推进一 Tick
        ++CurrentTick
        TickAdvanced?.Invoke(CurrentTick)

进入运行 → frameManager.TickAdvanced += OnTick
退出运行 → frameManager.TickAdvanced -= OnTick

OnTick(globalTick) → 更新本通道的业务数值、倒计时或结果
```

- **固定步由管理器归口。** 普通 `IUpdate` 每宿主帧采样一次，默认 60 Hz、最多推进 4 个 Tick。保留整数相位、超时裁剪和丢步计量。`FrameClock` 收成供管理器使用的整数步数计算，`FrameCore`、`FrameFault` 和 `IFrameHandler` 退出调度接口。订阅方拿到的是 Tick 编号。
- **用事件表达订阅。** `event Action<long> TickAdvanced` 按订阅顺序同步调用。每次派发读取当时的订阅列表，因此回调内增删订阅从下一次 Tick 派发起生效，即使同一 Unity 帧正在补步。调用方只在进入、退出时各绑定或解绑一次。
- **全局 Tick 先递增，业务自己提交结果。** Tick 表示管理器已发布的逻辑时间。战斗场次倒计时和局内计数可以在每次实际收到回调时加一，并传给现有 `FrameTimer`。这样中途开始、单独退订、重新订阅都可以沿用自己的业务进度。探针 A 单独暂停通过退订，探针 B 继续。调试单步属于管理器，对当时所有订阅方发布同一个 Tick。
- **收紧失败边界。** 预期业务失败由回调记录原因并主动退订。探针故障按钮走这条路径，便于确认 B 继续。`FrameTimer` 保留连续 Tick、可取消任务等直接影响结果的判断。删除热路径里重复判空、重入防御、故障队列和手写异常兜底。意外抛出的异常由 Unity 记录，当前派发可能在中途停止，已发布的全局 Tick 不重发。任意异常后的自动隔离属于现有实现的一项语义变化。

## 2. TEngine 调试面板

`GameModule.Debugger` 已缓存模块引用，TEngine 的窗口树持有注册的 `IDebuggerWindow`。建议在 `FrameManager.OnInit` 使用 `GameModule.Debugger.RegisterDebuggerWindow` 注册 `ClockProbeWindow`，省去管理器里的 `_debugger` 和 `_probe` 两个字段。注册及释放使用普通运行时代码，窗口可见性沿用项目的 TEngine Debugger 配置。释放时核对路径仍登记了这个页面再卸载，因为 TEngine 先关机时会先清空窗口树，现有卸载实现会对查到的窗口调用 `Shutdown`。这是实际的释放顺序边界。[GameModule 缓存](../../../Assets/GameScripts/HotFix/GameLogic/GameModule.cs) · [DebuggerModule](../../../Assets/TEngine/Runtime/Module/DebugerModule/DebuggerModule.cs) · [窗口树与释放](../../../Assets/TEngine/Runtime/Module/DebugerModule/DebuggerManager.DebuggerWindowGroup.cs)

```text
Project B / Frame Probe
运行中                          [启动 / 关闭] [调试暂停] [单步]
全局 Tick  804    本帧推进  1 / 4    累计丢步  2    裁剪  0 ms

最近 120 个 Unity 更新 · 宿主间隔 ms
33.3 ┤                         ▆
16.7 ┤ ▂▂▂▃▂▂▂▂▂▂▂▂▂▂▂▂▂▆▂▂▂▂▂▂▂▂ ▂▂▂▂▃▂▂▂
     └──────────────────────────────────────────
指向一帧时显示间隔、推进步数、丢步、裁剪和最后 Tick

来源   状态     业务 Tick   最近触发 Tick    最新输入
A      已退订       766            720             #3
B      运行中       804            780              —
[继续 A]  [输入与故障 ▸]  [复制诊断]
```

上图数值仅用于示意。窗口以状态和当前指标开头，第二层呈现最近帧趋势，底部把 A/B 对照与诊断操作放在同一处。常态柱用中性色，补步或过载使用强调色。状态附文字，颜色负责扫视。数值列对齐，丢步为整数，裁剪与间隔以 ms 显示。图和文字沿用 TEngine 当前 GUISkin，保留窄窗口滚动。

管理器每次推进写入一份小的只读值快照，包含 Unity 帧号、原始间隔、步数、丢步、裁剪与最后 Tick。窗口只在完整调试器打开、当前页可用时把新帧放入预分配的 120 项环形缓存。每个 Unity 帧号最多入列一次，避免两个普通更新入口前后顺序导致重复采样。窗口只在 `Repaint` 绘制柱，文本低频刷新，按钮与失败状态即时刷新。通用 FPS 和内存继续从 TEngine 已有的 `Information/Other/Time` 与 `Profiler/Summary` 查看。[TEngine 现有窗口注册](../../../Assets/TEngine/Runtime/Module/DebugerModule/Debugger.cs) · [现有 Profiler 概览](../../../Assets/TEngine/Runtime/Module/DebugerModule/Component/DebuggerModule.ProfilerInformationWindow.cs)

## 3. Editor Profiler

用静态的 `Unity.Profiling.ProfilerMarker`，开发源码只给实际采样点加 `UNITY_EDITOR`，调试器注册代码走正常运行时路径。采样作用域由 `ProfilerMarker.Auto()` 管理。第一版三个标记足够覆盖调度、回调与面板开销。[Unity 6000.0 ProfilerMarker](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Unity.Profiling.ProfilerMarker.html)

| 标记 | 包含范围 | 在 Profiler 看什么 |
| --- | --- | --- |
| `ProjectB.Frame.Update` | 管理器实际推进入口，包含时钟计算及发布 | `Total ms` 看一次宿主更新处理帧逻辑的总耗时，`Self ms` 帮助区分调度自身和子项耗时。 |
| `ProjectB.Frame.Tick` | 每次发布一个固定 Tick，含订阅回调 | 看 `Calls` 和耗时，空闲、正常补步、预算满、暂停与单步分别对照。后续业务需要细分时在自己的关键回调内打点。 |
| `ProjectB.FrameProbe.Draw` | 可见探针的 IMGUI 绘制 | 面板开、关使用同样负载对照，单独看绘制和分配开销。 |

分析时先录制同场景、同一输入脚本、相近帧区间。关闭 Deep Profile 开始，以 CPU Timeline 选尖峰，再用 Hierarchy 的 `Calls`、`Total ms`、`Self ms` 和 `GC Alloc` 收敛范围。分别录制常态、补步上限、暂停以及面板开关。比较多段样本时可用 Profile Analyzer 的单组和双组视图。面板上的宿主间隔是 Unity 更新之间的时间，CPU Marker 是对应代码块耗时，比较时各用各的单位和口径。编辑器运行记录属于开发定位数据，目标 Player 性能需要单独采样。[Unity CPU Profiler](https://docs.unity3d.com/6000.0/Documentation/Manual/ProfilerCPU.html) · [Unity Profile Analyzer](https://docs.unity3d.com/Packages/com.unity.performance.profile-analyzer@1.2/manual/index.html)

## 4. 分步实施记录

- [x] **合并推进与订阅。** `FrameManager` 持有整数相位时钟并发布 `TickAdvanced`。两个探针通过回调提交自身业务步，定时器去除重入状态和显式异常兜底。旧调度类型定义已清空。
- [x] **落地探针页面。** 直接注册 TEngine 窗口，增加逐帧柱形历史、帧详情、对齐的 A/B 数据列以及全局单步。调试页关闭期间跳过采集。
- [x] **加入编辑器采样。** 三个 Marker 分别覆盖推进、Tick 和面板绘制。录制、调用次数、实际耗时和分配仍待运行验收。
- [x] **同步实施文档。** 第 02 步记录实际 API，第 03 步说明战斗的订阅、提交和退订。
- [ ] **整理 Unity 资产路径。** 目录目标为 `Module/FrameModule/`，定点值源码目标为 `GameLogic/Utility/`。Pipeline 恢复后移动资源、保留 GUID、删除两个旧脚本占位文件并更新链接。

## 5. GitHub 参考（10 项）

星标为调研时仓库页面的近似值。实现建议以项目现有源码和 Unity 6000.0 官方 API 为依据。

| 项目 | 约星标 | 对本项目的参考 |
| --- | ---: | --- |
| TEngine | 2.4k | 框架已有分组注册的调试窗口。直接从项目内 `IDebuggerModule`、窗口树和 `DrawItem` 继承使用习惯。 [仓库](https://github.com/Alex-Rachel/TEngine) |
| UnityGameFramework | 2.6k | Debugger 组件按组导航，详情面板单独处理各类指标。支持同一框架入口承载专门的帧页。 [仓库](https://github.com/EllanJiang/UnityGameFramework) · [Debugger 源码目录](https://github.com/EllanJiang/UnityGameFramework/tree/master/Scripts/Runtime/Debugger) |
| Graphy | 2.9k | 实时图、数字和简要模式可同时服务趋势定位与快速扫视。帧页采用简要数字、短历史、逐帧详情。 [功能与界面](https://github.com/Tayx94/graphy) |
| Unity In-game Debug Console | 2.8k | 日志入口、检索和控制项共处一处，列表虚拟化服务长日志。对应本项目的短故障摘要和按需复制。 [仓库](https://github.com/yasirkula/UnityIngameDebugConsole) |
| Unity Runtime Inspector | 2.2k | 层级与详情分开，可切换提示。对应 A/B 表保留核心列，次要数据放在可展开区。 [仓库](https://github.com/yasirkula/UnityRuntimeInspector) |
| Dear ImGui | 77.1k | 示例将即时统计、图形控件、工具提示组合在同一个开发工具。参考其信息布局，项目绘制沿用 TEngine IMGUI。 [仓库](https://github.com/ocornut/imgui) · [示例源码](https://github.com/ocornut/imgui/blob/master/imgui_demo.cpp) |
| Unity C# Reference | 13.1k | `ProfilerMarker` 创建、开始、结束与采样作用域的实现依据。用于核对 Editor Marker 的作用范围。 [仓库](https://github.com/Unity-Technologies/UnityCsReference) · [ProfilerMarker 源码](https://github.com/Unity-Technologies/UnityCsReference/blob/master/Runtime/Profiler/ScriptBindings/ProfilerMarker.bindings.cs) |
| Unity Graphics | 3.0k | Rendering Debugger 以单位明确的行展示 CPU 和渲染时间，支持收起无数据项。帧探针分清宿主间隔和计时范围，异常信息可展开。 [仓库](https://github.com/Unity-Technologies/Graphics) · [Rendering Debugger 说明](https://github.com/Unity-Technologies/Graphics/blob/master/Packages/com.unity.render-pipelines.high-definition/Documentation~/rendering-debugger-window-reference.md) |
| XCharts | 3.8k | Unity 图表库提供多种系列、坐标轴和标注。用于校对图例、刻度与图表交互的可读性。 [仓库](https://github.com/XCharts-Team/XCharts) |
| Godot | 120.3k | 编辑器 Profiler 按帧存指标，可从图上选帧查看详情。参考它的历史图与单帧详情对应方式。 [仓库](https://github.com/godotengine/godot) · [编辑器 Profiler 源码](https://github.com/godotengine/godot/blob/master/editor/debugger/editor_profiler.cpp) |

## 6. CSDN 参考（10 篇）

文章正文已打开核读。可见互动来自站内搜索快照，记为「点赞 / 收藏」。选取优先考虑相关性和能核对的内容，个别实践互动数较低。作者示例用来比较呈现和排查流程，API 和性能口径以 Unity 官方资料为准。

| 文章 | 点赞 / 收藏 | 用于本项目 |
| --- | ---: | --- |
| 深入剖析 Unity Profiler.BeginSample | 27 / 15 | 示例拆分嵌套采样区段；落实为管理器总标记与每 Tick 子标记。 [原文](https://blog.csdn.net/qq_33060405/article/details/144178187) |
| Unity Profiler 使用详解 | 9 / 20 | 作者样例展示先找异常帧，再在层级中按耗时展开，对应本项目的分析步骤。 [原文](https://blog.csdn.net/qq395280705/article/details/155538541) |
| Unity Profiler 终极性能优化指南 | 24 / 17 | 示例把耗时峰值和自定义段关联，适用于补步与卡顿对照。 [原文](https://blog.csdn.net/qq_33060405/article/details/148595606) |
| Unity Profiler 内存分配追踪原理深度解析 | 10 / 5 | 使用带标记的逻辑段定位分配；本项目据此在 CPU Hierarchy 单独观察帧推进与探针绘制。 [原文](https://blog.csdn.net/qq_33060405/article/details/148597408) |
| Unity Profiler 实战解读 | 2 / 0 | Timeline、Hierarchy 与 Raw Hierarchy 对照；先找慢帧再区分调用占比与分配。 [原文](https://blog.csdn.net/qq_33060405/article/details/146245379) |
| Unity 运行时显示调试信息 | 0 / 3 | 作者以 `ProfilerRecorder` 配固定字段做运行时面板。借鉴简明字段排版，探针业务计数从管理器快照直接取。 [原文](https://blog.csdn.net/u010799737/article/details/134435138) |
| UGUI 性能优化 | 未记录 | 文章的同负载 UI 开关对照流程可用于探针自身开销的验收，具体 UI 机制限于原文环境。 [原文](https://blog.csdn.net/m0_63330263/article/details/165728877) |
| 从零到一，用 Unity 和 XCharts 打造动态数据可视化游戏界面 | 23 / 18 | 示例把实时刷新频率与图形表达分开，用于决定文章中趋势图与数值摘要的更新节奏。 [原文](https://blog.csdn.net/moss5/article/details/155509197) |
| Unity 中画 2D 图表，用 XChart 包绘制折线图 | 5 / 34 | 作者的两系列示例给出 X 轴刻度与单位，参考其明确轴语义的做法。 [原文](https://blog.csdn.net/dzj2021/article/details/129005856) |
| 基于 XChart 的 Unity 实时刷新可视化自定义图表 | 6 / 20 | 动态图表控制示例支持把输入、数据刷新与图表显示分开，本项目用一份值快照和固定长度历史。 [原文](https://blog.csdn.net/dire_wolf_/article/details/137654632) |

已落地内容见 [第 02 步实施记录](02-Project_B固定帧驱动分步执行方案.md)。本轮未主动运行编译、测试或 Profiler 录制。
