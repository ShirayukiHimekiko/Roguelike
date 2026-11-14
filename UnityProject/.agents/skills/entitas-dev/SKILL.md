---
name: entitas-dev
description: Entitas 1.14.1 ECS 开发规则（玩法内核）。触发词：Entitas、ECS、Context、Entity、Component、System、Feature、ReactiveSystem、Jenny、组件生成、系统树、ECS 重构。用于新增或修改 ECS 玩法代码、评审 Entitas 实现、排查 ECS 触发/查询/性能问题。
---

# Entitas 1.14.1 开发规则

> 这份规则是给 AI 自己执行的操作约束，不是教程。写 Entitas 代码前先读完第 0、1 节；评审代码时用第 9、11 节。

## 0. 版本判定与前提

**只写 1.14.1。** 看到下列特征先停，确认版本后再动手：

| 代码特征 | 实际版本 | 处理 |
|----------|----------|------|
| `Pool` / `Pools` / `ISetPools` / `pools.CreateSystem(...)` | ≤ 0.35 | 旧 API，按 `Context` 重写，不照抄 |
| `[Context(typeof(GameContext))]`、`Entitas.Generators`、`GamePositionMatcher`、`partial ContextInitialization` | master / 2.x | 未正式发布，拒绝并说明版本不符 |
| `[Game]`、`Contexts.sharedInstance`、`GameMatcher.Position`、`entity.creationIndex` | 1.x | 正确 |

开始写业务前，先确认这四件事（缺一件就先补）：

1. Unity 目标版本已验证：本仓库 Unity 6000.0.69f1 下，1.14.1 运行时 DLL 可加载、`Context/Entity` 可运行；编辑器 Jenny 窗口与 VisualDebugging 未验证且 2022+ 有已知问题，不要依赖。
2. Entitas 运行时以 DLL 形式被引用；**生成代码与业务系统必须在同一个热更程序集** `GameLogic` 内；Jenny 只存在于 Editor。
3. 项目有**唯一的生成入口**：优先 Jenny CLI（`doctor` 先 dry-run，再 `client gen`），不依赖 Unity 编辑器窗口，也不依赖某个人记住菜单。
4. `Generated/` 已入库，且约定"改组件 → 立刻生成 → 再改业务"。

> 当前仓库还没有安装 Entitas。以上是安装后的编码约束，不代表现在可以在业务代码里引用 Entitas 类型。
>
> 与 `tengine-dev` 冲突时：TEngine 侧（资源、热更、UI、项目命名）以 `tengine-dev` 为准；ECS 侧（组件、系统、生成、查询）以本规则为准。

---

## 1. 绝对红线

违反任意一条，代码直接返工，不讨论"先跑起来再说"。

| # | 禁止 | 必须 | 原因 |
|---|------|------|------|
| 1 | 组件里写业务方法、依赖 Context/System | 只放数据 + 纯计算方法（如 `IsAlive => Current > 0`） | 组件会被池化复用，逻辑会串 |
| 2 | 逻辑组件持有 `UnityEngine.Object` / `GameObject` / `Entity` 引用 | 资源存地址或 ID，实体存 `Id` + `PrimaryEntityIndex` | 对象销毁、实体复用后引用失效 |
| 3 | 直接改字段：`e.health.Current--`、`e.position.Value.x++` | `e.ReplaceHealth(...)`、`e.ReplacePosition(...)` | 不经过 Replace 不触发事件/ReactiveSystem |
| 4 | 业务系统里直接 `entity.Destroy()` | 打 `DeadComponent`，由 `Cleanup(DestroyEntity)` 或清理系统统一销毁 | Destroy 立即生效，后续系统看不到 |
| 5 | 系统之间互相 `new`、静态单例、直接调用 | 构造函数只收 `Contexts` / `IContext`，共享数据放组件 | 顺序和生命周期会失控 |
| 6 | 运行时新建 `Matcher<GameEntity>.AllOf(...)` | 用生成的 `GameMatcher.X`，或在构造函数里缓存 `IGroup` | 每个 Matcher 都会新增一个 Group，监听所有实体变化 |
| 7 | 给每帧变化的组件建 Matcher / EntityIndex | 拉模式、缓存、或只在需要时查询 | Group 更新成本 × 变更频率会炸 |
| 8 | 手改 `Generated/` 下任何文件 | 改组件源文件后重新生成 | 下次生成会被覆盖 |
| 9 | 在 `JobSystem` 里调用 `AddX/ReplaceX/RemoveX` | 只读计算，回主线程再写 | 1.14.1 官方注释明确禁止 |
| 10 | 逻辑层用 `UnityEngine.Random`、`Time.deltaTime`、`Physics`、`Resources.Load` | 自建 `Rand`、固定回合步长、View 层异步加载 | 破坏确定性与可回放性 |
| 11 | 用 `entity.AddX(...)` 写 `[Unique]` 组件 | `context.SetX(...)` / `context.ReplaceX(...)` | Add 绕过唯一性检查，会出现两个单例实体 |
| 12 | 事件系统、清理系统不注册或放在系统树中间 | 永远放系统树末尾 | 事件依赖"所有修改已完成" |
| 13 | 在 `Execute`/`Cleanup` 里 `new List/Dictionary`、拼字符串 | 字段 buffer、缓存、按帧复用 | GC 抖动 |
| 14 | 把 UI、动画、资源加载、存档 IO、网络传输塞进 ECS | 留在 TEngine 对应模块 | 这些不是纯数据模拟 |
| 15 | 序列化 `GameComponentsLookup` 的数字索引 | 存组件名/稳定业务 ID | 加删组件后索引会整体偏移 |

---

## 2. 一个功能的固定开发流程

不要跳步。每一步都有明确产出。

### 第 1 步：定 Context

先回答"这份数据属于哪个世界、生命周期多长"，再决定放哪：

| Context | 放什么 | 不变量 |
|---------|--------|--------|
| `Game` | 地图、单位、物品、战斗状态 | 一局结束就 `Reset()` |
| `Input` | 玩家/UI 指令，一次性实体 | 帧末必须销毁 |
| `Config` | 本局生效的少量可变配置（可选） | 只读；Luban 表本身不进 Context |

默认三个足够。不要按"每个业务名词一个 Context"拆；每多一个 Context，实体就多一份组件数组开销。

### 第 2 步：先列组件清单，再写代码

用表格列出，缺一项就不要开始写：

| 组件 | 类型 | Context | Attribute | 生命周期 |
|------|------|---------|-----------|----------|
| `GridPositionComponent` | 数据 | Game | `[Game]` | 长期 |
| `DeadComponent` | flag | Game | `[Game, Cleanup(DestroyEntity)]` | 帧末销毁 |
| `TurnComponent` | 单例 | Game | `[Game, Unique]` | 一局 |
| `DamagedComponent` | 事件 | Game | `[Game, Event(EventTarget.Any)]` | 长期/由结算移除 |
| `InputComponent` | 指令 | Input | `[Input, Unique, Cleanup(DestroyEntity)]` | 一帧 |

### 第 3 步：编译 → 生成 → 检查

1. 先保证工程能编译（生成器要解析程序集/项目）。
2. 走项目唯一生成入口，不要手写生成代码。
3. 检查 `Generated/<Context>/` 是否出现：`XxxEntity.cs`、`XxxMatcher.cs`、`Components/`、`Contexts.cs`。
4. 生成后立刻编译一次，确认没有残留旧 API。

### 第 4 步：写系统

按第 5 节接口表选型；先写系统骨架，再填逻辑；系统只依赖 `Contexts` 和缓存的 `IGroup`。

### 第 5 步：注册进 Feature

按第 6 节顺序模板插入；插入位置就是执行顺序，必须能说出"为什么在这个位置"。

### 第 6 步：接表现/桥接

逻辑系统不碰 GameObject、不碰 UI。表现走 View 系统或事件桥（第 7 节）。

### 第 7 步：验证

- 编译通过。
- ContextObserver 里能看到实体和组件按预期增删。
- 关键系统打断点或用 `DebugSystems` 确认执行顺序。
- 跑一局，确认无异常、无实体泄漏（`retainedEntitiesCount` 不持续上涨）。

---

## 3. Context 规则

- **3～5 个 Context**。默认 `Game` / `Input` / `Config`；确有必要再加 `Meta`（跨局存档数据）。
- 划分依据优先级：**生命周期 > 更新频率 > 业务名词**。
- 跨 Context **不共享 Entity**。需要引用时传业务 ID，由接收方用自己 Context 的索引查。
- `Input` 组件一律 `[Unique, Cleanup(CleanupMode.DestroyEntity)]`，一帧最多一个；如果一帧可能多条输入，改成普通实体并遍历。
- `Config` Context 只放"本局会被系统统一替换的值"（例如难度系数）。Luban 的只读表直接用服务读取，不要灌进 ECS。
- 新 Context 必须同时更新 `Entitas.CodeGeneration.Plugins.Contexts`，否则 `[Xxx]` 特性不会生成。

---

## 4. Component 规则

### 4.1 命名与字段

- 类名：`XxxComponent`，语义名词，不用 `Data` / `Info` / `Manager`。
- 字段：`public`、PascalCase、业务含义明确；不要用 `value`、`data`、`tmp` 这类泛名。
- 一个组件只表达一个关注点，字段尽量 ≤ 6 个；超过就拆。
- 不继承组件，不做组件接口多态。
- 允许 `enum`、`Vector2Int`、`string`（ID/地址）；不允许 `GameObject`、`Transform`、`ScriptableObject`。
- 表现层例外：只允许一个受控的 `ViewComponent` 持有 `IView` 接口，且只允许 View 系统读写，逻辑系统不得依赖。

### 4.2 形态选择

| 形态 | 写法 | 用在哪 | 生成结果 |
|------|------|--------|----------|
| 数据组件 | `[Game] class HealthComponent : IComponent { public int Current; }` | 有数值/状态 | `AddHealth/ReplaceHealth/RemoveHealth/hasHealth/health` |
| Flag | 零字段 | 布尔状态、可被 Matcher 查询 | `isX` 属性（setter 自动增删） |
| 单例 | `[Game, Unique]` | 一局唯一：回合、棋盘、游戏状态 | `context.SetX/ReplaceX/RemoveX/hasX/x` |
| 事件 | `[Game, Event(EventTarget.Any)]` | 需要 UI/音效/外部感知 | 监听器组件 + 接口 + 事件系统 |
| 索引 | 字段加 `[EntityIndex]` / `[PrimaryEntityIndex]` | 按 key 查实体 | `GetEntitiesWithX` / `GetEntityWithX` |
| 清理 | `[Cleanup(CleanupMode.RemoveComponent)]` | 一次性标记/请求 | 帧末自动移除 |
| 清理 | `[Cleanup(CleanupMode.DestroyEntity)]` | 死亡、消耗品 | 帧末自动销毁实体 |

**选择规则：**

- 能用 flag 就不用 `bool` 字段：flag 能被 Matcher 直接查，`bool` 不能。
- 单例只给"每局唯一"的东西。单例组件用 `context.SetX`，不要 `entity.AddX`。
- `RemoveX()`（Unique）会**销毁实体**，不是移除组件；要移除组件用 `entity.RemoveX()`。
- 事件只给"外部需要知道"的变化。每帧变化的 Position 不要加 `Event(Any)`，用 Self 事件或直接读。
- `[EntityIndex]` 只给查询键；坐标这类高频变化字段建索引要评估更新成本。
- `[Cleanup]` 只给一次性数据；长期数据加了会被帧末清掉。

### 4.3 不要做的事

- 不要在组件里缓存 `Context`、`IGroup`、系统引用。
- 不要把"配置表整行"塞进组件；只放本局需要的字段。
- 不要用组件继承表达"种类"；用 flag 组合（`Enemy` + `Flying` + `FireImmune`）。
- 不要给同一个组件同时加 `Unique` 和普通用法，语义会打架。

---

## 5. System 规则

### 5.1 接口选型

| 需求 | 接口 | 关键点 |
|------|------|--------|
| 启动初始化一次 | `IInitializeSystem` | 建棋盘、生成初始实体 |
| 每帧/每回合推进 | `IExecuteSystem` | 自己控制"没有指令就 return" |
| 响应组件变化 | `ReactiveSystem<TEntity>` | 只处理 Collector 收集到的实体 |
| 同时响应多个 Context | `MultiReactiveSystem<TEntity, TContexts>` | 少见，优先用一个 Context 汇总 |
| 大量实体只读并行计算 | `JobSystem<TEntity>` | **禁止**在内部写组件 |
| 帧末清理 | `ICleanupSystem` | 清一次性组件/实体 |
| 退出释放 | `ITearDownSystem` | 解绑事件、释放 View |

一个系统可以实现多个接口（例如 `ReactiveSystem` + `IInitializeSystem`），`Systems` 会按阶段分别调用。

### 5.2 ReactiveSystem 五条

1. `GetTrigger` 只监听**必要**的组件；触发面越窄越好。
2. `Filter` 必须无副作用、可重复执行。
3. `Execute` 里不要 `new` 集合，用字段 buffer。
4. 不在 `Execute` 里 `Destroy()`；打标记，交给清理。
5. 需要 Removed 事件时用 `context.CreateCollector(GameMatcher.Damaged.Removed())`（`Added()`/`Removed()`/`AddedOrRemoved()` 是 `IMatcher` 的扩展方法），不要监听 `Added` 后自己判断。

### 5.3 系统顺序模板

```
InputSystem → ProcessInputSystem
→ TurnSystem（回合调度）
→ AISystem
→ MovementSystem → CombatSystem
→ StatusEffectSystem → DeathSystem → LootSystem
→ ViewSystem / UiBridgeSystem
→ XxxEventSystems（生成）
→ XxxCleanupSystems（生成）
```

规则：

- 生产者在前，消费者在后。
- 同一份数据"先结算、后表现"。
- 生成的事件系统和清理系统永远在最后。
- 顺序写在唯一根 `Feature` 里，并加注释说明分组。

### 5.4 性能三条

- 缓存 `IGroup`，不要在 `Execute` 里 `GetGroup`。
- 不在循环里 LINQ、字符串拼接、`GetComponent`、`Resources.Load`。
- 控制 Matcher 总数。官方原话：100 个 Group × 每帧 2 万次组件替换 = 200 万次 `Matches`。

### 5.5 多线程

`JobSystem` 只做只读计算：把结果写到局部数组/结构，回主线程再由普通系统写组件。绝不在 job 内调用生成的 `AddX/ReplaceX/RemoveX`。

### 5.6 VisualDebugging（Inspector）

只有同时满足下面两条，Play 模式才会出现可用的 Inspector 节点：

1. 根系统是生成的 `Feature`（原版做法），或直接 `DebugSystems`。
2. Jenny 配置启用了 `ContextObserverGenerator` 和 `FeatureClassGenerator`：

```properties
Jenny.Plugins = ..., Entitas.VisualDebugging.CodeGeneration.Plugins, ...
Jenny.CodeGenerators = ..., Entitas.VisualDebugging.CodeGeneration.Plugins.ContextObserverGenerator, Entitas.VisualDebugging.CodeGeneration.Plugins.FeatureClassGenerator
```

`Feature` 是生成物：编辑器下继承 `DebugSystems`，Player 构建下继承 `Systems`；不要自己手写 `Feature` 基类。

生成的 `Contexts.cs` 会通过 `[PostConstructor] InitializeContextObservers()` 自动创建 `ContextObserver`，**不要在 MonoBehaviour 里手写 `new ContextObserver(...)`**；自动和手动同时存在会出现两个观察节点。

只有生成器被关闭时才手动兜底：

```csharp
#if UNITY_EDITOR
var observer = new ContextObserver(contexts.game);
#endif
```

| 节点 | 看什么 | 用途 |
|------|--------|------|
| `DebugSystemsBehaviour`（如 `Entitas Demo`） | Details / Performance / Systems | 系统数量、平均/最小/最大耗时、阈值标红、暂停/单步、按耗时排序、临时停用系统 |
| `ContextObserverBehaviour`（如 `Game (...)`） | Entities / Reusable / Retained / Groups | 实体泄漏、Retain 未释放、Group 膨胀、手动创建/清空实体 |
| `Entity`（ContextObserver 里点开，或 EntityLink → Show entity） | Components / 字段 / Retained by | 加删组件、改字段、销毁实体、释放 Retain |
| `EntityLink` | Unlink / Show entity | View GameObject 与实体的绑定关系 |

使用规则：

- Inspector 改字段会走 `ReplaceComponent`，会触发 ReactiveSystem/Event；但它是**调试入口**，不是正式数据编辑流程，不要依赖它做玩法配置。
- 修改只存在于当前 Play 实例，停止即丢失；不要把它当作存档或配置来源。
- 排查性能的顺序：`Total Systems` 是否符合预期 → 按平均耗时降序 → 调低 Threshold 找超标系统 → 勾选框临时停用验证 → `Reset now` 重新统计。
- 排查实体问题：看 `Retained entities` 是否非 0；看 Groups 数量是否随功能增长失控；在 Entity 面板确认组件是否真的加上/替换了。
- `Destroy Entity` / `Destroy All Entities` 只用于复现问题，不要在正式流程里点。
- 不要在 Player 构建里依赖 VisualDebugging；构建建议定义 `ENTITAS_DISABLE_VISUAL_DEBUGGING`。

Unity 6 兼容注意：

- 本项目的 `Assets/Plugins/EntitasOfficial/DesperateDevs/Editor/Compat/` 是适配后的 `DesperateDevs.Unity.Editor` 源码，不要删除或覆盖。
- 图标 meta 的 `labels:` 是 Hierarchy 图标能显示的前提，重新导入官方包后要补回。
- 如果 Console 出现 `null texture passed to GUI.DrawTexture`、`SearchTextField` NRE、`Getting control 0's position...`，先检查这两处适配，不要直接停用 VisualDebugging。

---

## 6. Feature 与生命周期

- **唯一根 Feature**：`GameSystems`。子 Feature 按阶段/领域嵌套（`InputSystems`、`BattleSystems`、`ViewSystems`）。
- 命名：`XxxSystems`（复数）；文件与类同名。
- 构造函数只接收 `Contexts`，在内部 `Add(...)`；不要在 Feature 里写业务逻辑。
- `Feature` 在 1.14.1 是**生成物**（`FeatureClassGenerator`）：开 VisualDebugging 时继承 `DebugSystems`，否则继承 `Systems`。生成配置里没有它时，直接用 `Systems`，不要自己造一个 `Feature`。
- 入口 `GameController` 只转发生命周期：

```csharp
public sealed class GameController
{
    readonly Systems _systems;

    public GameController(Contexts contexts)
    {
        _systems = new GameSystems(contexts);
    }

    public void Initialize()
    {
        _systems.Initialize();
    }

    public void Execute()
    {
        _systems.Execute();
        _systems.Cleanup();
    }

    public void TearDown()
    {
        _systems.TearDown();
    }
}
```

- `MonoBehaviour` 只做 Unity 生命周期桥接：`Start → Initialize`、`Update → Execute`、`OnDestroy → TearDown`。
- 暂停/回放：`DeactivateReactiveSystems()` + `ClearReactiveSystems()`；恢复时 `ActivateReactiveSystems()`。
- 重开一局：`Contexts.sharedInstance.Reset()`（销毁所有实体）后重新 `Initialize()`；不要只清一部分。
- 调试：编辑器下 ContextObserver 会自动生成；系统耗时看 `DebugSystems`。

---

## 7. 与 TEngine 的接缝（本项目）

### 7.1 目录与程序集

建议结构（安装 Entitas 后按实际 asmdef 调整）：

```
Assets/GameScripts/HotFix/GameLogic/Entitas/
├── Components/            # 手写组件，按 Context 分子目录
│   ├── Game/
│   └── Input/
├── Systems/               # 手写系统，按领域分
├── Features/              # 系统树
├── Generated/             # 生成物，禁止手改
└── Config/                # Entitas.properties / Jenny.properties
```

- Entitas 以 DLL 形式引用（保持 AOT 可引用即可）；**生成代码 + 业务系统必须在 `GameLogic`（热更）程序集内**，不要把组件和系统拆到不同程序集。
- Jenny 是 Editor 工具，不参与打包。
- 生成器关键配置：`Jenny.Plugins.ProjectPath = GameLogic.csproj`、`Jenny.Plugins.TargetDirectory = Assets/GameScripts/HotFix/GameLogic/Entitas`、`Entitas.CodeGeneration.Plugins.Contexts = Game, Input`。
- 安装后先用真机 IL2CPP + HybridCLR 验证一次：`Context<GameEntity>`、`Matcher<GameEntity>`、生成的 `GameEventSystems` 能正常跑。

### 7.2 资源

- **禁止** `Resources.Load` / 同步 `LoadAsset`。TEngine 资源是异步的（UniTask）。
- View 系统用"请求 → 异步加载 → 完成"三段式：
  1. 实体有 `AssetComponent`、没有 `ViewComponent`、没有 `LoadingComponent` → 加 `LoadingComponent`，发起异步加载。
  2. 加载回调里先校验 `entity.isEnabled && context.HasEntity(entity)`，再 `ReplaceView(...)`、`RemoveLoading()`。
  3. 实体销毁时释放/回收 GameObject。
- 异步回调是生命周期边界，必须重新校验实体存活；否则会往已销毁实体加组件抛异常。

### 7.3 UI

- ECS → UI 走桥接：`UiBridgeSystem`（ReactiveSystem）订阅 ECS 事件，转成 TEngine 的 `GameEvent`。
- UI 层**不引用** Entitas 类型，不实现 `IAnyXxxListener`。
- UI 的布局、动画、Tween、本地化留在 TEngine/UGUI，不进 ECS。

### 7.4 配置表

- Luban 表只读、无生命周期，**不进 Context**；系统直接通过配置服务读取。
- 需要"本局被系统替换"的少量值（难度、倍率）才放 `[Unique]` 组件。

### 7.5 流程

- TEngine 的 Procedure/Fsm 负责"进入战斗 / 退出战斗"。
- 进入：创建 `Contexts`、`GameSystems`，`Initialize()`。
- 退出：`TearDown()`、`Contexts.sharedInstance.Reset()`、销毁 View 根节点。
- 不要在 ECS 系统里切场景、加载大资源、发网络请求。

### 7.6 日志

- 用项目统一日志入口；系统里不要 `Debug.Log` 刷屏。
- 关键状态迁移（回合开始/结束、实体死亡）可以打一条带实体 id 和关键字段的日志。

---

## 8. 代码模板

### 8.1 组件

```csharp
using Entitas;
using Entitas.CodeGeneration.Attributes;

[Game]
public sealed class HealthComponent : IComponent
{
    public int Current;
    public int Max;
}

[Game, Cleanup(CleanupMode.DestroyEntity)]
public sealed class DeadComponent : IComponent
{
}

[Game, Unique]
public sealed class TurnComponent : IComponent
{
    public int Round;
    public TurnState State;
}
```

### 8.2 执行系统

```csharp
using Entitas;
using UnityEngine;
using static GameMatcher;

public sealed class MovementSystem : IExecuteSystem
{
    readonly IGroup<GameEntity> _movable;

    public MovementSystem(GameContext context)
    {
        _movable = context.GetGroup(AllOf(Position, Velocity).NoneOf(Dead));
    }

    public void Execute()
    {
        var entities = _movable.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            var entity = entities[i];
            var next = entity.position.Value + entity.velocity.Value;
            entity.ReplacePosition(next);
        }
    }
}
```

### 8.3 响应系统

```csharp
using System.Collections.Generic;
using Entitas;
using static GameMatcher;

public sealed class DamageSystem : ReactiveSystem<GameEntity>
{
    public DamageSystem(GameContext context) : base(context)
    {
    }

    protected override ICollector<GameEntity> GetTrigger(IContext<GameEntity> context)
    {
        return context.CreateCollector(Damaged);
    }

    protected override bool Filter(GameEntity entity)
    {
        return entity.hasHealth && entity.hasDamaged && !entity.isDead;
    }

    protected override void Execute(List<GameEntity> entities)
    {
        for (var i = 0; i < entities.Count; i++)
        {
            var entity = entities[i];
            var current = entity.health.Current - entity.damaged.Amount;
            entity.ReplaceHealth(current < 0 ? 0 : current, entity.health.Max);
            if (entity.health.Current == 0)
            {
                entity.isDead = true;
            }
        }
    }
}
```

### 8.4 系统树

```csharp
public sealed class GameSystems : Feature
{
    public GameSystems(Contexts contexts)
    {
        // 输入
        Add(new InputSystem(contexts));
        Add(new ProcessInputSystem(contexts));

        // 逻辑
        Add(new TurnSystem(contexts));
        Add(new AISystem(contexts));
        Add(new MovementSystem(contexts.game));
        Add(new DamageSystem(contexts.game));
        Add(new DeathSystem(contexts));

        // 表现
        Add(new AddViewSystem(contexts));

        // 生成：事件与清理必须最后
        Add(new GameEventSystems(contexts));
        Add(new GameCleanupSystems(contexts));
    }
}
```

---

## 9. 反模式速查

| 现象 | 根因 | 修复 |
|------|------|------|
| 改了组件但 ReactiveSystem 不跑 | 直接改字段，没走 Replace | 改成 `ReplaceX` |
| 实体死了但掉落/动画没播 | 系统里直接 `Destroy()` | 打 `Dead` 标记 + Cleanup 销毁 |
| 某个系统查不到实体 | Context 用错 / 组件没加 / 实体已销毁 | 用 ContextObserver 确认实体在哪个 Context |
| `GetSingleEntity()` 抛异常 | 同 Context 出现多个单例 | 用 `context.SetX`，或改普通组件 |
| 单例组件有两个实体 | `entity.AddX` 绕过唯一性 | `context.SetX` / `ReplaceX` |
| 事件不触发 | 事件系统没注册/顺序不对/监听器实体不存在 | 事件系统放末尾；确认 listener 已挂 |
| 索引查不到 | 索引没在 `[PostConstructor]` 注册 / key 重复 | 检查 `InitializeEntityIndices`；Primary 冲突会抛异常 |
| 帧率下降 | Group 太多 / 高频组件建了 Matcher | 减少 Matcher；高频数据改拉模式 |
| 生成后编译错 | 组件改名/删字段，旧生成代码还在 | 先修编译，再按 StreamingAssets 流程重新生成 |
| 真机上泛型报错 | 热更/AOT 程序集边界 | 生成 + 业务放同一热更程序集；运行时 DLL 保持 AOT 可引用 |
| 异步加载后实体已销毁 | 回调没校验生命周期 | `entity.isEnabled && context.HasEntity(entity)` |

---

## 10. 排查顺序

按这个顺序查，不要一上来就猜：

1. **编译是否通过**（生成器依赖编译产物）。
2. **组件是否真的生成了**（`Generated/<Context>/Components/` 有没有对应文件）。
3. **实体在哪个 Context、有哪些组件**（ContextObserver 或 `context.count`）。
4. **Matcher 是否命中**（断点 `Group.ContainsEntity`）。
5. **修改是否走了 Add/Replace/Remove**（看调用栈）。
6. **系统是否注册、顺序是否正确**（读根 Feature）。
7. **是否跨帧持有实体/组件引用**（AERC、池化）。
8. **是否在异步/事件回调里访问了已销毁实体**。

---

## 11. 提交前自检

- [ ] 只用了 1.14.1 API，没有 2.x/0.x 写法。
- [ ] 组件纯数据，没有 `UnityEngine.Object` / Entity 引用。
- [ ] 所有组件修改都走 `AddX/ReplaceX/RemoveX`。
- [ ] 没有在业务系统里直接 `Destroy()`。
- [ ] Matcher 全部用生成属性或构造函数缓存，没有运行时新建。
- [ ] 没有给高频变化组件新增 Matcher/EntityIndex。
- [ ] `Generated/` 没有手改。
- [ ] 系统顺序合理，事件/清理在末尾。
- [ ] 没有在 `Execute` 里 `new` 集合、LINQ、字符串拼接。
- [ ] 逻辑层没有 `UnityEngine.Random` / `Time` / `Physics` / `Resources.Load`。
- [ ] 异步回调校验了实体存活。
- [ ] 新增 Context/组件后重新生成并编译通过。
- [ ] 跑过一局，`retainedEntitiesCount` 没有持续上涨。

---

## 12. 参考

- 本 skill 的 API 速查：[references/api-1.14.1.md](references/api-1.14.1.md)
- 官方 Wiki：<https://github.com/sschmid/Entitas/wiki>
- 官方 FAQ：<https://github.com/sschmid/Entitas/wiki/FAQ>
- 版本源码：<https://github.com/sschmid/Entitas/tree/1.14.1>
- 示例工程：`sschmid/Match-One`（1.x 推荐）、`sschmid/Entitas-Shmup`（旧 API，只看结构）
