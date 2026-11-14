# Entitas 1.14.1 API 速查

> 基于 `sschmid/Entitas` tag `1.14.1` 源码与 `Readme/Readme/Generated`、`src/Entitas.CodeGeneration.Plugins`、`src/Entitas.Roslyn.CodeGeneration.Plugins` 核对。
> 1.14.1 的属性命名是**小驼峰**（`entity.creationIndex`、`context.count`），2.x 才改成大驼峰。

## 1. 核心类型

### 1.1 Context

`Entitas.Context<TEntity> : IContext<TEntity> where TEntity : class, IEntity`

| 成员 | 说明 |
|------|------|
| `TEntity CreateEntity()` | 从池里取实体并加入 Context |
| `void DestroyAllEntities()` | 销毁全部实体 |
| `bool HasEntity(TEntity entity)` | 是否属于该 Context |
| `TEntity[] GetEntities()` | 全部实体 |
| `IGroup<TEntity> GetGroup(IMatcher<TEntity> matcher)` | 取/建 Group（按 Matcher 缓存） |
| `TEntity[] GetEntities(IMatcher<TEntity>)` | 扩展方法，等价 `GetGroup(...).GetEntities()` |
| `void AddEntityIndex(IEntityIndex)` | 注册索引，必须早于实体创建 |
| `IEntityIndex GetEntityIndex(string)` | 取索引 |
| `void Reset()` | 销毁所有实体并重置 |
| `void ResetCreationIndex()` | 重置实体编号 |
| `void ClearComponentPool(int)` / `ClearComponentPools()` | 清组件池 |
| `int count` / `totalComponents` | 实体数 / 组件数 |
| `int reusableEntitiesCount` / `retainedEntitiesCount` | 池中实体数 / 被引用实体数 |
| `ContextInfo contextInfo` | 组件名与类型表 |
| `event ContextEntityChanged OnEntityCreated` | `(IContext, IEntity)` |
| `event ContextEntityChanged OnEntityWillBeDestroyed` | 销毁前 |
| `event ContextEntityChanged OnEntityDestroyed` | 销毁后 |
| `event ContextGroupChanged OnGroupCreated` | `(IContext, IGroup)` |
| `TEntity CloneEntity(IEntity, bool replaceExisting = false, params int[] indices)` | 扩展方法 |

### 1.2 Entity / IEntity

| 成员 | 说明 |
|------|------|
| `int creationIndex` | 实体在本 Context 内的唯一编号 |
| `bool isEnabled` | 是否有效（销毁后为 false） |
| `int totalComponents` | 组件槽位数 |
| `void AddComponent(int index, IComponent)` | 已有同索引组件会抛异常 |
| `void ReplaceComponent(int index, IComponent)` | 不存在时会 Add |
| `void RemoveComponent(int index)` | 不存在会抛异常 |
| `IComponent GetComponent(int index)` | 不存在返回 null |
| `bool HasComponent(int index)` / `HasComponents(int[])` / `HasAnyComponent(int[])` | 判断 |
| `void RemoveAllComponents()` | 清空组件（不销毁实体） |
| `void Destroy()` | 立即销毁（通知 Context） |
| `void Retain(object owner)` / `Release(object owner)` | 手动引用计数，必须成对 |
| `Stack<IComponent> GetComponentPool(int)` | 组件池 |
| 事件 | `OnComponentAdded` / `OnComponentRemoved` / `OnComponentReplaced` / `OnEntityReleased` / `OnDestroyEntity` |

### 1.3 Group / Matcher

`IGroup<TEntity>`：

| 成员 | 说明 |
|------|------|
| `TEntity[] GetEntities()` | 返回内部缓存数组，**不要修改** |
| `List<TEntity> GetEntities(List<TEntity> buffer)` | 复用 buffer |
| `TEntity GetSingleEntity()` | 0 个返回 null，>1 抛 `GroupSingleEntityException` |
| `bool ContainsEntity(TEntity)` | 是否在组内 |
| `int count` / `IMatcher<TEntity> matcher` | |
| `event GroupChanged<TEntity> OnEntityAdded` | `(group, entity, index, component)` |
| `event GroupChanged<TEntity> OnEntityRemoved` | 同上 |
| `event GroupUpdated<TEntity> OnEntityUpdated` | `(group, entity, index, previous, current)` |

`Matcher<TEntity>` 静态方法：`AllOf(params int[])`、`AllOf(params IMatcher[])`、`AnyOf(...)`；`NoneOf(...)` 在 `IAllOfMatcher` / `IAnyOfMatcher` 上。

### 1.4 Collector

| 成员 | 说明 |
|------|------|
| `Collector(IGroup<TEntity>, GroupEvent)` | 单组 |
| `Collector(IGroup<TEntity>[], GroupEvent[])` | 多组，数量必须一致 |
| `HashSet<TEntity> collectedEntities` | 收集结果 |
| `int count` | 数量 |
| `void Activate()` / `Deactivate()` | 启停监听 |
| `void ClearCollectedEntities()` | 清空 |
| `IEnumerable<TCast> GetCollectedEntities<TCast>()` | 类型转换 |

`GroupEvent`：`Added`、`Removed`、`AddedOrRemoved`。

### 1.5 Systems

| 成员 | 说明 |
|------|------|
| `virtual Systems Add(ISystem)` | 按接口分派到 4 个阶段列表，返回自身可链式 |
| `void Remove(ISystem)` | |
| `virtual void Initialize()` / `Execute()` / `Cleanup()` / `TearDown()` | 按加入顺序调用 |
| `void ActivateReactiveSystems()` / `DeactivateReactiveSystems()` / `ClearReactiveSystems()` | 暂停/恢复/清空响应系统 |
| `protected List<IInitializeSystem> _initializeSystems` 等 | 4 个阶段列表 |

### 1.6 ReactiveSystem / MultiReactiveSystem / JobSystem

```csharp
public abstract class ReactiveSystem<TEntity> : IReactiveSystem
{
    protected ReactiveSystem(IContext<TEntity> context);
    protected ReactiveSystem(ICollector<TEntity> collector);
    protected abstract ICollector<TEntity> GetTrigger(IContext<TEntity> context);
    protected abstract bool Filter(TEntity entity);
    protected abstract void Execute(List<TEntity> entities);
    public void Activate();
    public void Deactivate();
    public void Clear();
    public void Execute(); // 有收集才执行
}
```

```csharp
public abstract class MultiReactiveSystem<TEntity, TContexts> : IReactiveSystem
    where TContexts : class, IContexts
{
    protected MultiReactiveSystem(TContexts contexts);
    protected MultiReactiveSystem(ICollector[] collectors);
    protected abstract ICollector[] GetTrigger(TContexts contexts);
    protected abstract bool Filter(TEntity entity);
    protected abstract void Execute(List<TEntity> entities);
}
```

```csharp
public abstract class JobSystem<TEntity> : IExecuteSystem
{
    protected JobSystem(IGroup<TEntity> group);
    protected JobSystem(IGroup<TEntity> group, int threads);
    protected abstract void Execute(TEntity entity); // 多线程调用
}
```

> 源码注释：多线程代码里不要用生成的 `AddXyz()` / `ReplaceXyz()`。

### 1.7 EntityIndex

```csharp
new EntityIndex<TEntity, TKey>(name, group, (e, c) => key);
new PrimaryEntityIndex<TEntity, TKey>(name, group, (e, c) => key);
```

- `EntityIndex.GetEntities(key)` → `HashSet<TEntity>`，允许一键多实体。
- `PrimaryEntityIndex.GetEntity(key)` → `TEntity`，**重复 key 抛 `EntityIndexException`**。
- 索引在构造时 `Activate()`，会立即索引 Group 现有实体。

### 1.8 EntityLink（Unity）

```csharp
gameObject.Link(entity);      // 添加 EntityLink 并绑定
gameObject.Unlink();          // 解绑并销毁 EntityLink
gameObject.GetEntityLink();   // 取 EntityLink
```

---

## 2. 生成物与命名规则

组件 `PositionComponent` → 名称 `Position`（去掉 `Component` 后缀）；`[ComponentName("X")]` 可覆盖。

### 2.1 每个 Context

| 文件 | 内容 |
|------|------|
| `{Context}Attribute.cs` | `[Game]` 特性，继承 `ContextAttribute` |
| `{Context}ComponentsLookup.cs` | 组件索引常量、`TotalComponents`、`componentNames`、`componentTypes` |
| `{Context}Entity.cs` | `partial class GameEntity : Entitas.Entity` |
| `{Context}Matcher.cs` | `AllOf/AnyOf` + 每个组件的静态 Matcher |
| `{Context}Context.cs` | `partial class GameContext : Entitas.Context<GameEntity>` |
| `Contexts.cs` | `sharedInstance`、`allContexts`、各 Context 属性、`Reset()`、编辑器下的 ContextObserver |
| `Feature.cs` | 由 VisualDebugging 生成，三种条件编译分支 |

### 2.2 组件 API（普通）

```csharp
public partial class GameEntity
{
    public HealthComponent health { get; }
    public bool hasHealth { get; }
    public void AddHealth(int newValue);
    public void ReplaceHealth(int newValue);
    public void RemoveHealth();
}
```

多字段按组件的公开成员生成参数（顺序以生成结果为准，不要依赖手写顺序）。

### 2.3 Flag 组件

```csharp
public bool isMovable { get; set; } // setter 内部 Add/Remove，并从组件池取
```

支持 `[FlagPrefix("flag")]` 改前缀（生成 `flagX`）。

### 2.4 Unique 组件（Context API）

```csharp
public GameEntity turnEntity { get; }
public TurnComponent turn { get; }
public bool hasTurn { get; }
public GameEntity SetTurn(int round, TurnState state); // 已存在会抛异常
public void ReplaceTurn(int round, TurnState state);   // 不存在则 Set
public void RemoveTurn();                              // 注意：销毁实体
```

### 2.5 Event

`[Event(EventTarget.Any)]` 生成：

- `AnyDamagedListenerComponent`：`List<IAnyDamagedListener> value`
- `IAnyDamagedListener`：`void OnAnyDamaged(GameEntity entity, int amount)`
- `AnyDamagedEventSystem : ReactiveSystem<GameEntity>`
- `GameEventSystems : Feature`（汇总所有事件系统，按 priority 排序）

`[Event(EventTarget.Self)]` 生成 `DamagedListenerComponent`、`IDamagedListener`、`DamagedEventSystem`，监听器挂在实体自身。

Removed 事件方法名带 `Removed` 后缀。

### 2.6 EntityIndex

生成到 `Contexts` + `ContextsExtensions`：

```csharp
public const string Health = "Health";
[PostConstructor] public void InitializeEntityIndices();

public static HashSet<GameEntity> GetEntitiesWithHealth(this GameContext context, int value);
public static GameEntity GetEntityWithHealth(this GameContext context, int value); // Primary
```

`[CustomEntityIndex(typeof(GameContext))]` + `[EntityIndexGetMethod]` 生成自定义查询方法。

### 2.7 Cleanup

| 模式 | 生成系统 | 行为 |
|------|----------|------|
| `RemoveComponent` | `Remove{Component}{Context}System` | `entity.RemoveX()`；flag 组件则 `isX = false` |
| `DestroyEntity` | `Destroy{Component}{Context}System` | `entity.Destroy()` |

汇总为 `{Context}CleanupSystems : Feature`。

### 2.8 Feature（生成物）

- 编辑器 + 开启 VisualDebugging：`Feature : DebugSystems`。
- `DEVELOPMENT_BUILD` + 开启 DeepProfiling：`Feature : Systems`，带 Profiler 采样。
- 其他：`Feature : Systems`，构造函数只记名字。

生成器没启用时**没有** `Feature` 类，直接用 `Systems`。

---

## 3. Attributes（`Entitas.CodeGeneration.Attributes`）

| 特性 | 目标 | 参数 | 作用 |
|------|------|------|------|
| `[Context]` | 类 | `string contextName` | 手写 Context 归属（一般用生成的 `[Game]`） |
| `[Unique]` | 类 | — | 每个 Context 单例 |
| `[Event]` | 类，可多个 | `EventTarget target, EventType type = Added, int priority = 0` | 生成监听器与事件系统 |
| `[Cleanup]` | 类，可多个 | `CleanupMode mode` | 帧末清理 |
| `[EntityIndex]` | 字段/属性 | — | 普通索引 |
| `[PrimaryEntityIndex]` | 字段/属性 | — | 唯一索引 |
| `[CustomEntityIndex]` | 类 | `Type contextType` | 自定义索引类 |
| `[EntityIndexGetMethod]` | 方法 | — | 标记自定义索引查询方法 |
| `[FlagPrefix]` | 类 | `string prefix` | flag 属性前缀，默认 `is` |
| `[DontGenerate]` | 类 | `bool generateIndex = true` | 不生成组件 API |
| `[ComponentName]` | 类 | `params string[]` | 覆盖组件名（多 Context 可分别指定） |
| `[PostConstructor]` | 方法 | — | `Contexts` 构造后调用（索引注册） |

`EventTarget`：`Any` / `Self`；`EventType`：`Added` / `Removed`；`CleanupMode`：`RemoveComponent` / `DestroyEntity`。

---

## 4. 代码生成配置

`Entitas.properties` / `Jenny.properties` 关键键：

```properties
Entitas.CodeGeneration.Plugins.Contexts = Game, Input
Entitas.CodeGeneration.Plugins.IgnoreNamespaces = false

Jenny.Plugins.ProjectPath = GameLogic.csproj
Jenny.Plugins.TargetDirectory = Assets/GameScripts/HotFix/GameLogic/Entitas
Jenny.SearchPaths = Assets/Entitas
```

- `Contexts` 的顺序有意义：第一个是默认 Context（未标注 `[Xxx]` 的组件归它）。
- `ProjectPath` 必须指向包含组件源码的 csproj；asmdef 工程对应 `GameLogic.csproj`。
- 生成入口：`Jenny.CodeGenerator.Unity.Editor.UnityCodeGenerator.Generate()`；或 Jenny CLI。
- 1.14.1 **没有** `Tools/Entitas/Generate` 主菜单（只有 Preferences / Blueprints / Migrate / Stats / Feedback 等），不要照抄旧文章里的生成步骤。

已启用的生成器（1.14.1 默认）：

```
ComponentContextApiGenerator, ComponentEntityApiGenerator,
ComponentEntityApiInterfaceGenerator, ComponentGenerator,
ComponentLookupGenerator, ComponentMatcherApiGenerator,
ContextAttributeGenerator, ContextGenerator, ContextMatcherGenerator,
ContextsGenerator, EntityGenerator, EntityIndexGenerator,
EventEntityApiGenerator, EventListenerComponentGenerator,
EventListenerInterfaceGenerator, EventSystemGenerator, EventSystemsGenerator,
ContextObserverGenerator, FeatureClassGenerator,
CleanupSystemGenerator, CleanupSystemsGenerator
```

---

## 5. 编译宏

| 宏 | 作用 |
|----|------|
| `ENTITAS_DISABLE_VISUAL_DEBUGGING` | 关闭 ContextObserver / DebugSystems |
| `ENTITAS_DISABLE_DEEP_PROFILING` | 关闭 Feature 的 Profiler 采样 |
| `ENTITAS_FAST_AND_UNSAFE` | 使用 `UnsafeAERC`（更快，但泄漏风险更高） |

---

## 6. 常见异常

| 异常 | 触发 |
|------|------|
| `EntityAlreadyHasComponentException` | 对已有组件 `AddX` |
| `EntityDoesNotHaveComponentException` | 对不存在的组件 `RemoveX` |
| `EntityIsNotEnabledException` | 对已销毁实体增删组件 |
| `GroupSingleEntityException` | `GetSingleEntity()` 时同组实体 > 1 |
| `EntityIndexException` | `PrimaryEntityIndex` 重复 key |
| `ContextDoesNotContainEntityException` | 销毁不属于该 Context 的实体 |
| `ContextStillHasRetainedEntitiesException` | 销毁时仍有对象 Retain |
| `ContextEntityIndexDoesAlreadyExistException` | 重复注册同名索引 |
| `CollectorException` | groups 与 groupEvents 数量不一致 |

---

## 7. 1.14.1 与 master(2.x) 的差异（避免混写）

| 1.14.1 | master / 2.x |
|--------|--------------|
| `[Game]`（生成的 ContextAttribute） | `[Context(typeof(GameContext))]` |
| `Contexts.sharedInstance` | 手动 `new GameContext()` + `ContextInitialization` |
| `GameMatcher.Position` | `GamePositionMatcher.Position` |
| `GameComponentsLookup.Position` | `GamePositionComponentIndex.Index.Value` |
| `entity.creationIndex` | `entity.Id` |
| 属性小驼峰 | 属性大驼峰 |
| Jenny（反射 + Roslyn 数据源） | `Entitas.Generators`（Roslyn 源生成器） |
| `Feature` 生成物 | `Feature` 内置在 `Entitas.Unity` |
