# 系统、事件与生命周期

## 调度的选择

| 需求 | 用法 |
| --- | --- |
| 初始化世界和实体 | `IInitializeSystem.Initialize()` |
| 持续演算或批量处理请求 | `IExecuteSystem.Execute()`，读取缓存 Group 或业务队列 |
| 根据变化刷新状态 | `ReactiveSystem<TEntity>`，实现 `GetTrigger(IContext<TEntity>)`、`Filter(TEntity)`、`Execute(List<TEntity>)` |
| 同一消费者接多个 Context 的变化 | `MultiReactiveSystem<TEntity, TContexts>`，先确认各实体的公共类型和跨 Context 条件 |
| 消费完释放临时状态 | `ICleanupSystem.Cleanup()` |
| 退出解绑并释放持有 | `ITearDownSystem.TearDown()` |
| 批量只读计算 | `JobSystem<TEntity>` 接受 Group。工作线程计算，回世界所属线程使用生成 API 提交结果 |

`Systems.Add` 按接口注册到各阶段列表，阶段内按加入顺序运行。宿主显式调用 `Initialize → (Execute → Cleanup) × N → TearDown`；推进周期由项目的帧、回合或固定 tick 调度决定。典型的 Execute 依赖为输入 → 逻辑 → 表现绑定 → 事件派发。Cleanup 阶段再清除已消费的请求、死亡实体等。按实际读写依赖放置系统，绑定后要读一次初始状态或等待明确的首次投递。只调用 Execute 时清理系统不会运行。动态移除系统时要处理该系统的订阅，`Systems.Remove` 只改阶段列表。

## Collector 消费时点

```csharp
protected override ICollector<GameEntity> GetTrigger(IContext<GameEntity> context)
{
    return context.CreateCollector(GameMatcher.Health.Added());
}

protected override bool Filter(GameEntity entity)
{
    return entity.isEnabled && entity.hasHealth;
}
```

- Collector 构造即订阅，已有 Group 成员不会自动补发。它按实体去重并 Retain。Group 的 `Added()`、`Removed()` 和 `AddedOrRemoved()` 都可能由 Replace 触发。复合 Group 中任一关联槽位的 Replace 可能重触发监听，使用单组件 Matcher 可缩小触发面。
- Reactive 执行时用当前实体状态筛选，清空 Collector 后调用业务 `Execute(List<TEntity>)`。保持 `Filter` 为纯判断，只在回调期间使用传入列表。回调内产生的新变化，当前系统下次执行时再消费。后续系统可以在当前周期消费自己的 Collector。
- 需要“处理时已无组件”可用单组件 `.Removed()` 并在 Filter 检查 `!hasX`。需要真实的历史变更、旧值或顺序时，在写入处保存所需数据，或在同步通知中复制所需值。

| 需求 | 输入序列 | 预期与接法 |
| --- | --- | --- |
| 刷新血量条 | 同一实体在派发前写入 80、65 | 刷新一次至 65。订阅 Health Added，绑定时先读初始值 |
| 同一单位一个 tick 接受两笔伤害 | 独立请求 A=20、B=15，目标 ID 相同 | 每笔请求保留自己的实体或队列项。生命周期明确时按序号处理并写入每笔输出，消费成功后清理 |

逐笔模型要明确同 tick 晚到请求、无效目标和重试怎么处理。如果生产可能晚于消费者，Cleanup 只销毁已处理的请求，或明确将晚到请求排入下一周期。把两次 `ReplaceDamageRequest` 都写到目标单位上会合并变化，并只保留最后一次数据。

## 生成事件和清理

- `[Event(EventTarget.Self)]` 的监听器组件挂在发出变化的实体，`[Event(EventTarget.Any)]` 的监听器组件挂在同一 Context 内的监听实体。用生成方法绑定，例如 `source.AddHealthListener(listener)` 或 `listenerEntity.AddAnyHealthListener(listener)`。解绑时使用对应 Remove API。
- Jenny 生成监听接口、监听器组件、实体监听 API、Reactive 事件系统及 Context 事件组。事件组按 priority 升序，再按组件名称排序。默认 Added 回调读取当前组件数据，`EventType.Removed` 回调只带实体、方法名带 `Removed`，并判断组件现已不存在。
- Self Removed 派发时要求监听器组件仍在。销毁会移除所有组件，所以死亡表现需要先读取死亡状态或稳定载荷，再走清理。
- `[Cleanup(CleanupMode.RemoveComponent)]` 移除组件，`[Cleanup(CleanupMode.DestroyEntity)]` 销毁整个实体。产物实现 `ICleanupSystem`。根系统需注册生成的清理组或等效组，宿主需调用 Cleanup。清理触发的 Removed 通知可能在下一次 Execute 消费。

## 最小接线示例

下面的示例以 `Game` Context 和已启用事件生成为前提。先定义组件并用 Jenny 生成，再写监听与宿主接线。Unity 表现侧可以让监听器更新现有 UI 适配器。

```csharp
using Entitas;
using Entitas.CodeGeneration.Attributes;

[Game, Event(EventTarget.Self)]
public sealed class HealthComponent : IComponent
{
    public int Current;
}
```

监听器实现生成的 `IHealthListener`，具体方法签名以产物为准。挂载、更新和执行的顺序如下。

```csharp
var contexts = new Contexts();
var systems = new Systems()
    .Add(new GameEventSystems(contexts));

systems.Initialize();
var unit = contexts.game.CreateEntity();
unit.AddHealth(100);
unit.AddHealthListener(listener);
systems.Execute(); // listener.OnHealth(unit, 100)

unit.ReplaceHealth(80);
unit.ReplaceHealth(65);
systems.Execute(); // listener.OnHealth(unit, 65)，只派发一次
systems.Cleanup();

systems.DeactivateReactiveSystems();
unit.RemoveHealthListener(listener);
systems.TearDown();
contexts.Reset();
```

构造事件组时 Collector 已生效，因此能收集后续的 Add。若监听生效时状态已经被派发过，绑定端主动读一次当前值。若两笔伤害各自影响护盾或结算统计，采用前述逐笔请求模型，最终血量显示仍可用 Self 事件合并刷新。


## 退出、重开与异步

1. 停止推进和输入，取消或作废该世界的异步任务。
2. 通过 `systems.DeactivateReactiveSystems()` 停用系统树的收集器。停用同时清理收集结果。手工建立的 Collector 也要停用。
3. 调用 `systems.TearDown()` 解绑视图、监听和外部 Retain owner。处理清理阶段的销毁回调，避免再次产生未释放持有。
4. 世界所有者执行销毁或 `contexts.Reset()`。Reset 销毁活跃实体并重置创建序号，组、索引注册、池和订阅仍属于原世界。重开时可显式构造独立世界，或复位原有系统状态后还原有意保留的订阅。

`Destroy()` 立即退出活跃集合并移除组件。Retain 阻止对象提前回池，销毁仍然发生。跨阶段直接持有时定义 owner，保证 `Retain(owner)` 和 `Release(owner)` 成对。`retainedEntitiesCount` 统计已销毁且尚被持有的实体。Reset 抛 `ContextStillHasRetainedEntitiesException` 时追销毁期间的订阅与 owner。

异步完成时回到世界所属线程，用**世界代次、业务 ID 和请求代次**重新解析目标。需要防止同一世界内业务 ID 重用时，还要区分实体实例的逻辑代次。实体对象可能已被池分配给另一实体，仅检查 `isEnabled && context.HasEntity(entity)` 会放过旧引用。过期结果按资源 API 释放，避免旧请求覆盖新绑定。

