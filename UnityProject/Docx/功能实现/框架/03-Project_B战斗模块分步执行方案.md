# Project B 战斗模块分步执行方案

2026-11-17 · 订阅接口接入稿，源码待实施

第 03 步建立一场可完成或退出的空战。战斗实例接收第 02 步的固定 Tick 通知，管理待执行命令、场内提交水位和战果。第 04 步沿用该入口接正式 Entitas 战场。[整游实现流程 §3.03](../../架构设计/Project_B整游实现流程.md) · [第 02 步实际帧接口](02-Project_B固定帧驱动分步执行方案.md)

## 1. 入口和职责

当前第 01 步的业务宿主是 `GameAppManager`，其 `StartUI` 开始按钮只输出日志。首期建议由该宿主持有活动 `BattleModule`，在既有运行态与暂停态处理场次控制。加 TEngine `Project B / Empty Battle` 调试页作为按钮与结果的入口。将来整局会话落地后可以接管场次持有、准备和结果消费。[第 01 步源码现状](01-Project_B游戏生命周期分步实现方案.md) · [现有 GameAppManager](../../../Assets/GameScripts/HotFix/GameLogic/Module/GameAppModule/GameAppManager.cs)

```text
调试按钮 → GameAppManager 控制 Update → BattleModule
FrameManager.IUpdate → TickAdvanced(globalTick) → BattleModule.OnTick
BattleModule.OnTick → EmptyBattleSimulation → 提交场内批次或封存退出意图
下次控制 Update → 消费终局或失败 → 释放场次 → 保留值结果
```

| 对象 | 职责 |
| --- | --- |
| `GameAppManager` | 分配应用期递增的 `BattleId`，持有一个活动场。受理开始、暂停、继续、退出和重试，读取场次的已提交结果。 |
| `BattleModule` | 一场一个实例，持有场地准备值、命令队列、模拟对象、可读结果和固定步订阅。 |
| `FrameManager` | 发布共享的 `CurrentTick` 与 `TickAdvanced`，统一步频。 |
| `EmptyBattleSimulation` | 消费一个场内候选步和该步命令，返回样本批次或预期失败。 |
| `EmptyBattleWindow` | 提交带 `BattleId` 的操作，读取只读状态。调试器选中状态不影响正在运行的战斗。 |

## 2. 场次合同

| 数据 | 首期约定 |
| --- | --- |
| `BattleSetup` | 场地地址、种子和正整数 `DeadlineTick`。步频取当前帧管理器，重试复用准备值并分配新的 `BattleId`。 |
| `BattleCommand` | `BattleId`、场内 `TargetTick`、递增 `InputSequence`、样本标记。相同目标步按序应用。 |
| `BattleTickResult` | `BattleId`、本场 `Tick`、可选 `GlobalTick` 诊断值、已应用输入、样本值和剩余步数。 |
| `BattleResult` / `BattleExit` | 生命周期只发布一次。自然终局取最后成功步已封存的结果。取消、装配失败、预期推进故障取 `Cancelled`、`SetupFailed`、`Faulted`，附最后成功 Tick。 |

**时间口径。** 全局 Tick 在应用里递增。战斗初态提交为本场 Tick 0，每收到一次通知才尝试 `LastCommittedTick + 1`。例如某场在全局 420 激活，首个通知为 421，对应本场 Tick 1。暂停期间退订，继续后收到的下一个全局 Tick 仍只推进一个本场 Tick。倒计时按 `max(0, DeadlineTick - LastCommittedTick)` 计算。全局暂停会停止发布，开发者触发全局单步时，当前订阅中的本场收到一次通知。

## 3. 分步执行清单

### 3.1 建立宿主入口和装配

- [ ] **新增 `Module/BattleModule/Flow/BattleModule.cs`、`BattleContracts.cs`。** 用 `StartBattle`、`EndBattle`、`ExitBattle` 表达场次状态。开始阶段先装配，开战后消费 Tick。两种退场都走一次性封口。
- [ ] **基于现有 `GameAppManager` 接控制入口。** 利用运行态和暂停态的 FSM 更新处理待提交请求。运行态可接受开始，暂停态仍可接受当前场退出。每次控制更新先消费场次已封存的终止结果，再受理新请求。先按当前宿主实现，未来由 `RunSession` 接管时沿用战斗模块入口。
- [ ] **新增 `BattleSetupLoader` 和 `ProjectBEmptyArena.json`。** 通过 `GameModule.Resource` 异步读取最小场地数据，引用已有 Configs 收集规则。加载记录持有自己的 `BattleId` 与 YooAsset 句柄。完成或失败由加载方归还原句柄。只有仍处于装配中的同一场可接纳结果。 [资源接口](../../../Assets/TEngine/Runtime/Module/ResourceModule/IResourceModule.cs) · [收集配置](../../../Assets/Editor/AssetBundleCollector/AssetBundleCollectorSetting.asset)

```text
请求开始 → 分配 BattleId → BeginLoad(setup, battleId)
装配结果 → 原请求归还加载句柄 → 按当前 BattleId 交接
运行态控制 Update → 创建 World → 提交 Tick 0
                  → frames.TickAdvanced += OnTick → 允许输入
```

激活与继续以实际订阅为界。如果控制 Update 发生在帧管理器这次派发之前，本场可能在同一个 Unity 帧收到首个 Tick。加载和暂停时没有订阅，所以只消费激活后的通知。控制流程不依赖两个 Unity Update 的固定顺序。

### 3.2 消费命令并提交场内 Tick

- [ ] **新增 `BattleCommandQueue`。** 受理时核对场次身份与输入开关，把实时输入写到下一个场内 Tick，并分配序号。每步消费同目标输入，按序应用。回放入口投递已分配步号的记录，拒绝旧场身份、重复序号或已经提交的步。
- [ ] **新增 `IBattleSimulation` 与 `EmptyBattleSimulation`。** 提供 Tick 0 初态与逐步执行。样本仅修改标记及剩余步数，到达截止步提交 `Timeout`。预期失败返回错误值，调试注入用同一分支。
- [ ] **在 `BattleModule` 实现 `OnTick(long globalTick)`。** 执行成功后提交局部水位和结果。终局与预期失败在回调内封口并退订，场次归还由控制更新完成，同一个宿主 Update 的剩余补步也不会再进入本场。

```text
OnTick(globalTick)
    candidate = LastCommittedTick + 1
    commands = queue.TakeForTick(candidate)
    outcome = simulation.Step(candidate, commands)
    成功 → 提交结果批次和 LastCommittedTick
        若是自然终局 → 封存成功结果 → 关输入 → 退订
    预期失败 → 记录 candidate 与原因，保留上一个提交水位 → 关输入 → 退订
```

帧管理器在调用订阅前已推进全局编号。本场业务提交点位于成功的回调内部。预期失败退出并保留先前批次。意外抛出的实现异常由 Unity 记录，当前全局 Tick 不重发。

### 3.3 暂停、结算与回收

- [ ] **实现局部暂停与继续。** 暂停关输入后解除订阅，保留已受理的命令和值快照。继续时对当前场恢复订阅与输入。重复或过期控制请求由实际宿主状态裁决。
- [ ] **实现正常、主动和失败退出。** 终止已封存时保留该结果。主动退出先撤销装配资格、关输入和退订，再释放 World、队列、场内订阅和视图绑定。装配迟到的结果只做原句柄收尾。返回给宿主只读值，已释放的 World 无需继续持有。
- [ ] **加入 TEngine 空战调试页。** 按钮支持开始、暂停、继续、退出、样本标记和装配失败重试。显示场号、状态、全局 Tick、场内提交 Tick、剩余步数和最近结果。场内订阅归 `BattleModule`，页面启闭独立于战场。

```text
暂停 → 关输入 → frames.TickAdvanced -= OnTick
继续 → frames.TickAdvanced += OnTick → 开输入
退出 → 停止交接与输入 → 退订 → 释放 World → 宿主保存一次值结果
```

## 4. 待实施验收

| 用例 | 预期 |
| --- | --- |
| 装配和 Tick 0 | 当前场成功装配后提交一次初态。场内第一步对应实际订阅后收到的首个全局 Tick。 |
| 超时和补步 | 场内截止为 3，同一宿主 Update 发布四个全局 Tick 时，该场只提交 1、2、3，其他订阅仍可接收第四个。 |
| 局部暂停 | 场内 Tick 2 暂停，其他订阅继续。恢复后首次回调提交场内 Tick 3。同一调试宿主的下一场使用新的 `BattleId`。 |
| 正常与故障结果 | 候选步 3 预期失败，只保留之前的成功结果，失败步为 3，最后提交位为 2。同一次更新中其余订阅照常得到通知。 |
| 汇合的控制请求 | 首次已提交终局后到达退出请求，产出一次自然战果。若退出先被受理，则退订并返回一次取消。 |
| 装配失败或迟到 | A 在加载时退出并打开 B。A 原句柄正常归还，B 沿自己的场次号装配。失败后可原准备值重试。 |
| 面板关闭 | 调试器关闭或换页，活动战斗在宿主控制和固定步回调中正常运行。再次打开能读到当前提交进度。 |

本稿完成接口和阶段边界的调整。第 03 步的源码、运行和性能验收待实施。
