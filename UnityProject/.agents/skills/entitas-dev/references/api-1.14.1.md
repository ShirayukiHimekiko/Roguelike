# Entitas 1.14.1 API 与建模

## 对象关系

一个 `Context<TEntity>` 创建和销毁自己持有的实体，管理组件槽位、组件池、Group 与索引。生成的 `Contexts` 聚合多个 Context。跨局、并发世界、回放或测试需要隔离时，由各自的世界所有者创建 `new Contexts()`，避免隐式共享 `Contexts.sharedInstance`。

组件用类实现 `IComponent`。同一实体的同一槽位最多有一个组件，公开数据成员由生成器转成写入参数。生成的写入 API 会从池取实例、填成员并通知框架。旧实例在通知之后可以被池复用，跨阶段或异步需保存值快照。直接修改附着组件的字段或集合会绕过通知和索引更新。

## 选择数据形态

下表以已配置的 `Game` Context 举例。可用生成的 `[Game]` 或原生 `[Context("Game")]`。1.14.1 Roslyn provider 将未显式归属的 `IComponent` 放入配置列表的第一个 Context。可用多个 Context 特性共享组件定义，实体仍归各自 Context。

| 目的 | 组件形态 | 生成 API |
| --- | --- | --- |
| 属性、数值 | 有公开数据成员的 `HealthComponent` | `entity.health`、`entity.hasHealth`、`AddHealth(...)`、`ReplaceHealth(...)`、`RemoveHealth()`、`GameMatcher.Health` |
| 可查询的开关 | 空的 `DeadComponent` | `entity.isDead`，赋值走增删。可用 `[FlagPrefix("...")]` 自定义前缀 |
| 一局唯一的状态 | 有字段的 `[Game, Unique] RoundComponent` | `context.roundEntity`、`context.round`、`hasRound`、`SetRound(...)`、`ReplaceRound(...)`、`RemoveRound()` |
| 一局唯一的开关 | 空的 `[Game, Unique] PausedComponent` | `context.pausedEntity`、`context.isPaused` |
| 按键查找 | 成员加 `[EntityIndex]` 或 `[PrimaryEntityIndex]` | `context.GetEntitiesWithCell(key)` 或 `context.GetEntityWithUnitId(key)`，以生成签名为准 |

普通实体 `AddX` 已存在时抛异常，`RemoveX` 缺失时抛异常，`ReplaceX` 可以补加。底层 `GetComponent(index)` 在槽位缺失时抛 `EntityDoesNotHaveComponentException`。可选组件先按 `hasX` 判定。

有数据的 Unique 用 Context 的 `SetX` 建立，已存在时 `SetX` 抛异常。`ReplaceX` 可以补加或更新。`RemoveX` 要求持有实体存在，调用后销毁整个持有实体。Unique flag 用 Context 的布尔 setter 创建或销毁持有实体。把同生命周期数据放在该实体，防止移除单例时连带删除其它数据。实体级写入可以绕过唯一性，多个持有实体会导致查询抛 `GroupSingleEntityException`。

`creationIndex` 在 Context 内标识一次创建，`Reset()` 会重置序号。生成的 `GameComponentsLookup` 数字随组件布局变化。跨世界引用和持久化使用稳定业务 ID 与明确的数据格式。

## Group、Matcher 和索引

```csharp
// 在系统构造阶段取得 Group，执行时复用。
var living = context.GetGroup(GameMatcher.AllOf(GameMatcher.Health, GameMatcher.UnitId)
    .NoneOf(GameMatcher.Dead));
```

- Matcher 依据组件存在性匹配。`AllOf` 要求全部，`AnyOf` 要求至少一个，`NoneOf` 排除所有给定项。按具体值查询时在 Group 内筛选，或在查询量足够时建索引。
- 首次查找不同 Matcher 时，Context 用已有实体初始化 Group，并按 Matcher 相等性缓存。取得 Group 后保持 Matcher 定义稳定。组件变化只通知其索引关联的 Group。Add/Remove 重新判定成员资格，Replace 对已在组内的实体发出 Removed → Added → Updated，成员资格保持不变。
- `group.GetEntities()` 返回内部缓存数组，`group.GetEntities(buffer)` 清空并填入调用方的 List。两者都可在循环会改成员资格时作短期快照。数组按只读使用，快照中实体仍可能被其它操作销毁。`GetSingleEntity()` 空组返回 null，多于一个抛异常。
- `EntityIndex` 允许一键多实体。`GetEntities(key)` 返回内部 HashSet，缺失键也可能创建空集合。`PrimaryEntityIndex` 允许一键至多一实体，`GetEntity(key)` 缺失返回 null。重复主键会抛 `EntityIndexException`，可能发生在组件已写入后，因此先在业务写入点保证唯一性。
- 索引构造时订阅 Group，并索引已经匹配的实体。生成的索引通过 `Contexts` 的 `[PostConstructor]` 方法注册。手写扩展查 `[CustomEntityIndex(typeof(GameContext))]` 和 `[EntityIndexGetMethod]`，这里的 `typeof` 属于自定义索引属性。
- 更新索引键时通过 `ReplaceX` 提供新值，让索引收到 Removed 的旧组件和 Added 的新组件。使用哈希等价稳定的键。高频组件是否建 Group 或索引，按候选规模、读写比和实际开销决定。要求稳定顺序时，按业务键显式排序。

