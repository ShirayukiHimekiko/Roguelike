# Entitas 1.14.1 使用指南

> 适用版本：`sschmid/Entitas` **1.14.1**（最后一个打了 tag 的稳定版；CHANGELOG 里的 1.14.2 没有对应 tag）
>
> 写作依据：1.14.1 tag 源码、Release 包实际内容（`Entitas.zip` / `Jenny.zip`）、官方 Wiki、`Readme/Readme/Generated` 生成结果
>
> 配套文档：项目内的 AI 执行规则见 [entitas-dev](../UnityProject/.agents/skills/entitas-dev/SKILL.md)；框架调研见 [Entitas-框架调研与实战指南.md](Entitas-框架调研与实战指南.md)

---

## 目录

- [1. 安装（1.14.1 特有）](#1-安装1141-特有)
- [2. 五分钟跑通第一个 ECS](#2-五分钟跑通第一个-ecs)
- [3. 核心模型](#3-核心模型)
- [4. 模块使用手册](#4-模块使用手册)
- [5. 代码生成手册](#5-代码生成手册)
- [6. 实战：回合制 Roguelike 切片](#6-实战回合制-roguelike-切片)
- [7. 常见错误与排查](#7-常见错误与排查)
- [8. 性能建议](#8-性能建议)
- [9. 接入 TEngine 的建议](#9-接入-tengine-的建议)
- [10. 速查表](#10-速查表)
- [11. FAQ](#11-faq)

---

## 1. 安装（1.14.1 特有）

### 1.1 先纠正一个常见误解

网上大量 2018～2020 年的教程会让你在菜单里点 `Tools > Entitas > Generate`。**1.14.1 没有这个菜单。**

1.14.1 的实际结构是：

| 包 | 内容 | 放哪 |
|----|------|------|
| `Entitas.zip`（685 KB） | `Entitas/`、`DesperateDevs/`、`Jenny/Editor/`、`Sherlog/`、`TCPeasy/` 的 DLL 与编辑器资源 | 解压到 `Assets/Plugins/`（Unity 6 实测；直接放 `Assets/` 时 asmdef 可能不自动引用） |
| `Jenny.zip`（5.05 MB） | Jenny 代码生成器（server + CLI + Roslyn/Entitas 插件） | 解压到 **Unity 工程根目录**（与 `Assets/` 同级） |

下载地址：

- <https://github.com/sschmid/Entitas/releases/tag/1.14.1>
- 直接文件：`.../releases/download/1.14.1/Entitas.zip`、`.../releases/download/1.14.1/Jenny.zip`

> 1.14.1 的代码生成是"客户端/服务端"结构：Unity 里的 Jenny 客户端把生成请求发给本机的 Jenny server（默认端口 3333），server 用 Roslyn 解析你的 csproj 并生成代码，Unity 侧写入 `Assets`。所以 **server 要先跑起来**。
>
> Jenny 的 `SearchPaths` 必须能找到 `Entitas.dll`。如果只指向 `Jenny/Plugins`，会报 `FileNotFoundException: Could not load file or assembly 'Entitas'`。最稳的做法：把 `Entitas.dll`、`Entitas.CodeGeneration.Attributes.dll`、`DesperateDevs.Caching/Reflection.dll` 复制到 `Jenny/Plugins/Entitas` 旁边。

### 1.2 环境要求

| 项 | 要求 | 说明 |
|----|------|------|
| Unity | 2021.3 LTS 或 Unity 6（本仓库为 6000.0.69f1） | 运行时 DLL 是 `netstandard2.1`；Unity 6 实测可加载并运行，见 1.6 |
| .NET（生成机） | **.NET 6 SDK**（不是只装 Runtime） | Jenny 的 Roslyn 数据源要加载 MSBuild。只装 Runtime 会卡在 `No instances of MSBuild could be detected` |
| 操作系统 | Windows / macOS | `Jenny-Server.bat` 是 Windows 启动脚本 |

如果机器只有 .NET 8，有两个选择：

1. 安装 .NET 6 SDK（推荐，最稳）。
2. 临时用 roll-forward 启动：设置 `DOTNET_ROLL_FORWARD=LatestMajor`（不保证 Roslyn/MSBuild 能识别，实测不如直接装 SDK 6）。

### 1.3 安装步骤

**Step 1：导入 Entitas.zip**

把 `Entitas.zip` 里的 5 个顶层目录整体拷到 `Assets/Plugins/` 下，得到：

```
Assets/Plugins/
├── Entitas/                 # 运行时 DLL + Editor DLL + Images
├── DesperateDevs/           # 配置/序列化/反射基础库
├── Jenny/Editor/            # Unity 侧 Jenny 客户端
├── Sherlog/                 # 日志
└── TCPeasy/                 # 客户端与 server 通信
```

> Unity 6 实测：DLL 放在 `Assets/Entitas` 时，`GameLogic` 这类 asmdef 可能不会自动引用（报 `CS0246: Entitas`）；放在 `Assets/Plugins` 下才稳定。保持 `Assets/Plugins/Entitas/Entitas.dll` 这一层。

**Step 2：解压 Jenny.zip 到工程根目录**

```
UnityProject/
├── Assets/
├── Jenny/                  # server + CLI + Plugins
├── Jenny-Server.bat
└── Jenny-Auto-Import.bat
```

**Step 3：启动 Jenny server**

双击工程根目录的 `Jenny-Server.bat`，保持窗口开着。脚本内容等价于：

```bat
.\Jenny\Jenny server
```

如果 bat 提示找不到 `Jenny`（该包只提供 DLL，启动器可能缺失），直接用 CLI：

```bat
cd /d <UnityProject>
dotnet Jenny\Jenny.Generator.Cli.dll server
```

> `server` 子命令来自随包 bat；若你的包版本不同，先跑 `--help` 确认。

启动成功时窗口会显示监听端口（默认 3333）。

**Step 4：Unity 里配置**

1. 打开 `Tools > Entitas > Preferences...`（快捷键 `Ctrl+Shift+E`；Jenny 的相关项也可能在同一个窗口或 Jenny 自己的设置页）。
2. 设置：
   - **Contexts**：`Game, Input`（先用两个，够跑示例；顺序有意义，第一个是默认 Context）
   - **Target Directory**：`Assets/Generated`
   - **Project Path**：`Assembly-CSharp.csproj`（有 asmdef 时填对应的 `GameLogic.csproj`）
3. 关掉窗口，配置会写入工程根目录的 `Jenny.properties` / `Entitas.properties`。

典型的 `Jenny.properties`（路径按你的实际位置改）：

```properties
Entitas.CodeGeneration.Plugins.Contexts = Game, Input
Entitas.CodeGeneration.Plugins.IgnoreNamespaces = false

Jenny.Plugins.ProjectPath = Assembly-CSharp.csproj
Jenny.Plugins.TargetDirectory = Assets/Generated

# 一般不用手动填；只有报 Jenny.SearchPaths 时才补，指向 Jenny 的插件目录
# Jenny.SearchPaths = D:/Tools/Entitas-1.14.1/Jenny/Plugins/Entitas, D:/Tools/Entitas-1.14.1/Jenny/Plugins/Jenny
```

> 如果生成时报 `Jenny.SearchPaths` 相关错误，说明插件目录没配对上：指向你解压的 Jenny 目录下的 `Plugins/Entitas` 与 `Plugins/Jenny`（上面注释里的路径按实际改）。

**Step 5：生成一次，验证安装**

菜单 `Tools > Jenny > Generate`（快捷键 `Ctrl+Shift+G`）。

成功时 Console 会打印类似：

```
Generated N files (xxx sloc, xxx loc)
```

并生成：

```
Assets/Generated/
├── Contexts.cs
├── Feature.cs
├── Game/
│   ├── GameAttribute.cs
│   ├── GameComponentsLookup.cs
│   ├── GameContext.cs
│   ├── GameEntity.cs
│   └── GameMatcher.cs
└── Input/
    └── ...
```

看到 `Contexts.cs` 就说明装好了。此时还没有任何组件，生成物只有 Context 骨架。

### 1.4 安装后的目录约定

建议把手写代码和生成代码分开：

```
Assets/
├── Entitas/                 # 框架（只读）
├── Generated/               # 生成物（禁止手改，入库）
├── Sources/
│   ├── Components/
│   │   ├── Game/
│   │   └── Input/
│   ├── Systems/
│   ├── Features/
│   └── GameController.cs
└── ...
```

**生成目录一定要入库。** 否则每个人本地生成顺序不同，代码 diff 会互相打架；CI 也没有可比对的基线。

### 1.6 Unity 6 兼容性（本仓库实测）

测试环境：Unity **6000.0.69f1**、Windows；临时空工程 + 本仓库 `GameLogic` 实际编译。

| 项 | 结果 | 说明 |
|----|------|------|
| DLL 加载 | ✅ | 全部 `netstandard2.1`；Unity API Updater 处理 0/3 个程序集，无报错 |
| 运行时 ECS | ✅ | 本仓库 `EntitasDemo` 编译通过，`ENTITAS_DEMO:OK pos=(2,3)` |
| Jenny CLI 解析 `GameLogic.csproj` | ✅ | 识别 `Game` Context，规划 9 个文件，`No problems detected`（需 .NET 6 SDK） |
| VisualDebugging（DebugSystems/ContextObserver） | ✅ | 完整包下可实例化；Play 时 Hierarchy 出现 `Entitas Demo` 与 `Contexts` 节点 |
| 编辑器 Jenny 窗口 | ⚠️ 未验证 | Unity 2022+ 有已知问题（#1072），生成仍建议走 server/CLI |
| HybridCLR 真机 | ⚠️ 未验证 | 需要打包到设备验证泛型实例化 |

**结论**：完整包可以装；DLL 放 `Assets/Plugins` 下，生成走 CLI，VisualDebugging 可用。Unity 6 下如果 DLL 放在 `Assets/` 根目录，asmdef 可能不自动引用，会报 `CS0246: Entitas`。

---

## 2. 五分钟跑通第一个 ECS

目标：屏幕上有一个实体，每帧按速度移动。

### 2.1 写两个组件

`Assets/Sources/Components/Game/PositionComponent.cs`：

```csharp
using Entitas;
using UnityEngine;

[Game]
public sealed class PositionComponent : IComponent
{
    public Vector2 Value;
}
```

`Assets/Sources/Components/Game/VelocityComponent.cs`：

```csharp
using Entitas;
using UnityEngine;

[Game]
public sealed class VelocityComponent : IComponent
{
    public Vector2 Value;
}
```

`Assets/Sources/Components/Game/MovableComponent.cs`：

```csharp
using Entitas;

[Game]
public sealed class MovableComponent : IComponent
{
}
```

> `[Game]` 这个特性是 Step 5 生成出来的（在 `Assets/Generated/Game/GameAttribute.cs`）。所以**第一次必须先空生成一次**，否则这三个文件编译不过。

### 2.2 再生成一次

`Ctrl+Shift+G`。生成后你会得到（可以点开对照）：

```csharp
// GameEntity 的扩展（自动生成，不要手写）
public PositionComponent position { get; }
public bool hasPosition { get; }
public void AddPosition(Vector2 value);
public void ReplacePosition(Vector2 value);
public void RemovePosition();

// flag 组件
public bool isMovable { get; set; }

// Matcher
GameMatcher.Position
GameMatcher.Velocity
GameMatcher.Movable

// Context
public sealed partial class GameContext : Entitas.Context<GameEntity>
```

### 2.3 写系统

```csharp
using Entitas;
using static GameMatcher;

public sealed class MoveSystem : IExecuteSystem
{
    readonly IGroup<GameEntity> _movable;

    public MoveSystem(GameContext context)
    {
        _movable = context.GetGroup(AllOf(Position, Velocity, Movable));
    }

    public void Execute()
    {
        var entities = _movable.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            var entity = entities[i];
            entity.ReplacePosition(entity.position.Value + entity.velocity.Value);
        }
    }
}
```

### 2.4 组系统树 + 驱动

```csharp
using Entitas;

public sealed class GameSystems : Feature
{
    public GameSystems(Contexts contexts)
    {
        Add(new MoveSystem(contexts.game));
    }
}
```

```csharp
using Entitas;
using UnityEngine;

public sealed class GameControllerBehaviour : MonoBehaviour
{
    Systems _systems;

    void Start()
    {
        var contexts = Contexts.sharedInstance;
        _systems = new GameSystems(contexts);
        _systems.Initialize();

        var entity = contexts.game.CreateEntity();
        entity.AddPosition(Vector2.zero);
        entity.AddVelocity(new Vector2(1f, 0f));
        entity.isMovable = true;
    }

    void Update()
    {
        _systems.Execute();
        _systems.Cleanup();
    }

    void OnDestroy()
    {
        _systems.TearDown();
    }
}
```

### 2.5 运行与观察

把 `GameControllerBehaviour` 挂到场景空物体上，运行。

- 打开 Hierarchy，会看到编辑器自动创建的 `Contexts` / `Game` 节点（`ContextObserver`）。
- 点开实体，能看到 `Position`、`Velocity`、`Movable` 三个组件实时变化。
- 在 Inspector 里删掉 `Movable` 组件，实体立刻停止移动——因为 `AllOf(Position, Velocity, Movable)` 不再命中。

这就是 Entitas 的全部基本盘：**改组件 → Group 自动更新 → 系统只处理命中的实体**。

---

## 3. 核心模型

```
Context（世界/工厂）
  ├── 管理 N 个 Entity
  ├── 缓存 N 个 Group（按 Matcher）
  └── 维护 EntityIndex

Entity（id + 组件数组）
  └── 组件增删改 → 触发 Group 更新

Group（满足 Matcher 的实体子集）
  └── 事件：Added / Removed / Updated

Collector（订阅 Group 事件，攒变化）
  └── ReactiveSystem（每帧处理攒到的实体）
```

四个关键词：

| 概念 | 一句话 |
|------|--------|
| **Context** | 实体的"世界"，负责创建/销毁/查询 |
| **Entity** | 只有 id 和组件数组，没有业务字段 |
| **Component** | 纯数据，实现空接口 `IComponent` |
| **System** | 纯逻辑，按阶段被 `Systems` 调用 |

System 的五种生命周期：

| 接口 | 调用时机 | 典型用途 |
|------|----------|----------|
| `IInitializeSystem` | 启动一次 | 建地图、生成初始实体 |
| `IExecuteSystem` | 每帧/每回合 | 移动、AI、回合推进 |
| `IReactiveSystem` | 有变化时 | 伤害结算、UI 刷新、View 同步 |
| `ICleanupSystem` | `Execute` 之后 | 清一次性组件/实体 |
| `ITearDownSystem` | 退出时 | 解绑、释放 |

一帧的流程：

```
Initialize()  → 一次
Execute()     → 每帧（IExecuteSystem + ReactiveSystem）
Cleanup()     → 每帧末尾
TearDown()    → 退出
```

---

## 4. 模块使用手册

### 4.1 Component

**四种形态：**

```csharp
// 1) 普通数据
[Game]
public sealed class HealthComponent : IComponent
{
    public int Current;
    public int Max;
}

// 2) Flag（零字段）
[Game]
public sealed class DeadComponent : IComponent
{
}

// 3) 单例（每个 Context 一份）
[Game, Unique]
public sealed class TurnComponent : IComponent
{
    public int Round;
}

// 4) 事件（变化时通知监听者）
[Game, Event(EventTarget.Any)]
public sealed class DamagedComponent : IComponent
{
    public int Amount;
}
```

**规则：**

- 类必须 `public`，字段必须 `public`（生成器反射/解析需要）。
- 一个组件一个关注点；字段太多就拆。
- 不继承、不放 `Context`/系统引用、不放 `GameObject`。
- 枚举、`Vector2Int`、`string`（ID/路径）都可以。
- flag 组件能被 Matcher 直接查；`bool` 字段不能。所以"状态"优先用 flag。

### 4.2 Entity

```csharp
var e = context.CreateEntity();

e.AddPosition(Vector2.zero);
e.ReplacePosition(new Vector2(1, 0));
e.RemovePosition();

var has = e.hasPosition;
var pos = e.position;          // 组件引用
var index = e.creationIndex;   // 实体编号
e.isMovable = true;            // flag
e.Destroy();                   // 立即销毁
```

| API | 说明 |
|-----|------|
| `AddX` | 已有同组件会抛异常 |
| `ReplaceX` | 不存在时自动 Add；**改值必须用它** |
| `RemoveX` | 不存在会抛异常 |
| `hasX` / `x` | 判断 / 取组件 |
| `isX` | flag 组件 |
| `Retain/Release` | 手动引用计数，成对使用 |
| `Destroy()` | 立即从 Context 和所有 Group 移除 |

**三个坑：**

1. **直接改字段不触发事件**：`e.position.Value.x++` 不会触发 ReactiveSystem，必须 `ReplacePosition(...)`。
2. **`Destroy()` 立即生效**：后面的系统看不到这个实体。用 `DeadComponent` 打标记，帧末统一销毁。
3. **组件会被池化**：`RemoveX` 之后组件对象可能被别的实体复用，不能长期持有引用。

### 4.3 Context

```csharp
var context = Contexts.sharedInstance.game;

var e = context.CreateEntity();
var group = context.GetGroup(GameMatcher.Position);
var entities = context.GetEntities(GameMatcher.AllOf(Position, Velocity));

context.OnEntityCreated += (ctx, entity) => { /* 统一初始化 */ };
```

| API | 说明 |
|-----|------|
| `CreateEntity()` | 从池里创建 |
| `DestroyAllEntities()` | 清空 |
| `Reset()` | 清空并重置（`Contexts.Reset()` 遍历全部） |
| `GetGroup(matcher)` | 取/建 Group |
| `GetEntities(matcher)` | 等价于 `GetGroup(...).GetEntities()` |
| `AddEntityIndex(...)` | 注册索引，必须早于实体创建 |
| `count` / `retainedEntitiesCount` | 实体数 / 被引用数（查泄漏） |

### 4.4 Matcher 与 Group

```csharp
using static GameMatcher;

var all = context.GetGroup(AllOf(Position, Velocity));
var any = context.GetGroup(AnyOf(Player, Enemy));
var none = context.GetGroup(AllOf(Position).NoneOf(Dead));

var single = context.GetGroup(Turn).GetSingleEntity(); // 0 个 null，多个抛异常
```

**Group 事件：**

```csharp
group.OnEntityAdded += (g, e, index, component) => { };
group.OnEntityRemoved += (g, e, index, component) => { };
group.OnEntityUpdated += (g, e, index, previous, current) => { };
```

**注意：**

- `GetSingleEntity()` **0 个返回 null，多个抛 `GroupSingleEntityException`**。
- 每个新 Matcher 都会新增一个 Group，Group 会监听所有实体的组件变化。**Matcher 必须复用**（用生成的 `GameMatcher.X`）。
- `GetEntities()` 返回内部缓存数组，不要修改它。

### 4.5 Collector 与 ReactiveSystem

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

**要点：**

- 只有 `Add/Replace/Remove` 才会触发；直接改字段不触发。
- 触发条件越窄越好，不要监听每帧变化的组件。
- 需要"移除时触发"：`context.CreateCollector(GameMatcher.Damaged.Removed())`。
- `Execute` 只会在收集到实体时调用；没有变化时零开销。
- `Deactivate()` 可以暂停响应（暂停/回放用）。

### 4.6 Systems 与 Feature

```csharp
public sealed class GameSystems : Feature
{
    public GameSystems(Contexts contexts)
    {
        Add(new InputSystem(contexts));
        Add(new TurnSystem(contexts));
        Add(new AISystem(contexts));
        Add(new MoveSystem(contexts.game));

        Add(new GameEventSystems(contexts));    // 生成
        Add(new GameCleanupSystems(contexts));  // 生成
    }
}
```

- `Feature` 是**生成物**：开 VisualDebugging 时继承 `DebugSystems`，否则继承 `Systems`；没有生成它就直接用 `Systems`。
- 一个系统可以实现多个接口（`ReactiveSystem` + `IInitializeSystem`），`Systems` 会按阶段分别调用。
- 顺序 = `Add` 顺序，没有隐式排序。

### 4.7 Event

```csharp
[Game, Event(EventTarget.Any)]
public sealed class ScoreChangedComponent : IComponent
{
    public int Value;
}
```

生成：

```csharp
public interface IAnyScoreChangedListener
{
    void OnAnyScoreChanged(GameEntity entity, int value);
}

public sealed class AnyScoreChangedListenerComponent : IComponent
{
    public List<IAnyScoreChangedListener> value;
}
```

用法：

```csharp
public sealed class ScoreView : MonoBehaviour, IAnyScoreChangedListener
{
    public void OnAnyScoreChanged(GameEntity entity, int value)
    {
        // 更新 UI
    }
}

// 注册：创建一个监听器实体
var listener = Contexts.sharedInstance.game.CreateEntity();
listener.AddAnyScoreChangedListener(scoreView);
```

`Self` 与 `Any`：

| | Self | Any |
|---|------|-----|
| 监听器挂哪 | 产生事件的实体上 | 任意监听器实体 |
| 接口 | `IDamagedListener.OnDamaged` | `IAnyDamagedListener.OnAnyDamaged` |
| 适合 | 实体自己的表现 | 全局 UI/音效 |

### 4.8 EntityIndex

```csharp
[Game]
public sealed class IdComponent : IComponent
{
    [PrimaryEntityIndex]
    public int Value;
}
```

生成：

```csharp
context.GetEntityWithId(42);
```

普通索引（允许一键多实体）：

```csharp
[Game]
public sealed class CellComponent : IComponent
{
    [EntityIndex]
    public Vector2Int Value;
}
// 生成：context.GetEntitiesWithCell(cell)
```

索引在 `Contexts` 的 `[PostConstructor]` 里注册，**必须早于实体创建**。`PrimaryEntityIndex` 遇到重复 key 会抛 `EntityIndexException`。

### 4.9 Cleanup

```csharp
[Game, Cleanup(CleanupMode.RemoveComponent)]
public sealed class SelectedComponent : IComponent
{
}

[Game, Cleanup(CleanupMode.DestroyEntity)]
public sealed class DeadComponent : IComponent
{
}
```

生成的系统在 `Cleanup()` 阶段执行：

- `RemoveComponent` → `entity.RemoveSelected()`（flag 则 `isSelected = false`）
- `DestroyEntity` → `entity.Destroy()`

必须把 `XxxCleanupSystems` 加到系统树末尾。

### 4.10 VisualDebugging：Inspector 与 Hierarchy 使用说明

这一节只对**编辑器 + Play 模式**有效。VisualDebugging 不参与打包，运行时实体仍然是纯 C# 对象。

#### 4.10.1 先让节点出现（推荐自动创建）

需要两个东西：

1. 根系统用生成的 `Feature`（原版 `Match-One` 的做法），或直接 `DebugSystems`。
2. 在 Jenny 配置里启用 `ContextObserverGenerator` 和 `FeatureClassGenerator`：

```properties
Jenny.Plugins = Entitas.CodeGeneration.Plugins, Entitas.Roslyn.CodeGeneration.Plugins, Entitas.VisualDebugging.CodeGeneration.Plugins, Jenny.Plugins, Jenny.Plugins.Unity
Jenny.CodeGenerators = ..., Entitas.VisualDebugging.CodeGeneration.Plugins.ContextObserverGenerator, Entitas.VisualDebugging.CodeGeneration.Plugins.FeatureClassGenerator
```

本项目对应写法：

```csharp
public sealed class EntitasDemoSystems : Feature
{
    public EntitasDemoSystems(GameContext game) : base("Entitas Demo")
    {
        Add(new DemoMoveSystem(game));
        Add(new DemoViewSystem(game));
    }
}
```

`Feature` 是生成物：编辑器下继承 `DebugSystems`，Player 构建下继承 `Systems`，所以 Inspector 只在编辑器可用，构建不会带调试逻辑。

重新生成后，`Contexts.cs` 会带上：

```csharp
[PostConstructor]
public void InitializeContextObservers()
{
    // 内部调用 CreateContextObserver(game)
}

public void CreateContextObserver(Entitas.IContext context)
{
    if (UnityEngine.Application.isPlaying)
    {
        var observer = new Entitas.VisualDebugging.Unity.ContextObserver(context);
        UnityEngine.Object.DontDestroyOnLoad(observer.gameObject);
    }
}
```

进入 Play 后自动创建，**不需要在 MonoBehaviour 里手写 `new ContextObserver(...)`**。本项目已经按这个方式配置，`EntitasDemoBehaviour` 里没有手动创建代码。

只有在生成器被关闭的特殊情况下，才手动兜底：

```csharp
#if UNITY_EDITOR
var observer = new ContextObserver(Contexts.sharedInstance.game);
#endif
```

> 自动和手动只能二选一；同时使用会出现两个 `ContextObserver` 节点。

进入 Play 后，Hierarchy 顶层会出现：

| 节点 | 组件 | 作用 |
|------|------|------|
| `Entitas Demo` | `DebugSystemsBehaviour` | 系统面板（耗时、暂停、单步） |
| `Game (N entities, ...)` | `ContextObserverBehaviour` | Context / Group / Entity 面板 |
| `DemoEntity_0` | `EntityBehaviour` + `EntityLink` | 某个实体的 View 对象 |

这些节点都是运行时创建的，**Edit 模式看不到**。

#### 4.10.2 ContextObserver 面板

选中 `Game (...)`：

| 区域 | 内容 | 怎么用 |
|------|------|--------|
| 标题 | Context 名（`Game`） | 确认当前是哪个 Context |
| Entities | 当前实体数 | 判断有没有实体泄漏 |
| Reusable entities | 池里可复用的实体数 | 频繁创建/销毁时观察是否稳定 |
| Retained entities | 被 Retain 的实体数；非 0 时红色 + 警告 | 出现警告通常是有 `Retain` 没 `Release` |
| Create Entity | 新建一个空实体并选中 | 手动造测试实体 |
| Destroy All Entities | 清空该 Context | 复现“空世界”或重开一局 |
| Groups (N) | 每个 Group 的 `Matcher` 和实体数，按数量倒序 | 看哪个 Group 在膨胀、Matcher 是否过宽 |

Groups 列表是排查“为什么这个实体没进 Group”和“Group 数量是否失控”的第一入口。

#### 4.10.3 Entity 面板

从 ContextObserver 里点实体，或选中 `DemoEntity_0` 后点 `Show entity`：

| 区域 | 内容 | 怎么用 |
|------|------|--------|
| `Destroy Entity` | 红色按钮 | 立即销毁，观察后续系统行为 |
| `Components (N)` | 组件数量，左右两个按钮 | 一键折叠/展开全部组件 |
| 组件下拉框 | 添加组件 | 手动加组件复现问题 |
| 搜索框 | 按组件名过滤 | 组件多时定位 |
| 每个组件 | 折叠标题 + `-` 按钮 | `-` 移除组件 |
| 组件字段 | 可直接编辑 | 修改后走 `ReplaceComponent`，会触发 ReactiveSystem / Event |
| `Retained by (N)` | 谁 Retain 了它 | 可逐个 `Release`，排查泄漏 |
| `[DontDrawComponent]` | 不展开字段 | 标记为不希望在 Inspector 显示的类型 |

注意：

- Inspector 里改字段**不是**“直接改字段”，`EntityDrawer` 会复制一份新组件并 `ReplaceComponent`，所以会触发事件；但它是调试入口，不要拿它当正式数据编辑流程。
- 编辑只影响当前运行实例，停止 Play 就丢失。
- 修改组件字段时如果组件被池化/替换，Inspector 的引用可能失效，以最新一帧为准。

#### 4.10.4 Systems 面板（DebugSystems）

选中 `Entitas Demo`：

**Details**

- `Initialize Systems / Execute Systems / Cleanup Systems / TearDown Systems / Total Systems`
- 用来确认系统树是否按预期注册，尤其是生成的事件/清理系统有没有加进去。

**Performance**

- `Execution duration` / `Cleanup duration`：当前帧耗时。
- 暂停按钮：只暂停 `DebugSystems` 的 `Execute/Cleanup`，不是暂停 Unity Editor。
- 单步按钮：暂停后手动执行一次 `Execute + Cleanup`，适合逐帧看状态变化。
- 曲线：最近 60 帧的总耗时，用来发现尖刺。

**Systems**

| 控件 | 作用 |
|------|------|
| `Reset average duration` | 平均耗时重置间隔（Always / VeryFast / Fast / Normal / Slow / Never） |
| `Reset now` | 立即清空平均/最小/最大统计 |
| `Threshold` | 0～33 ms 的告警阈值；超过的系统名会变红 |
| `Hide empty systems` | 隐藏没有对应阶段系统的分组 |
| 排序下拉 | 按注册顺序、名称、耗时升/降序 |
| 搜索框 | 按系统名过滤 |
| 系统前的勾选框 | 启用/停用该系统；ReactiveSystem 会调用 `Activate/Deactivate` |
| 每行右侧 | 平均 / 最小 / 最大耗时（Execute/Cleanup） |
| 缩进 | 嵌套的 `DebugSystems` 会缩进显示 |

典型用法：

1. 先看 `Total Systems` 是否符合预期。
2. 按耗时降序，找最慢的 Execute 系统。
3. 把 Threshold 调到目标帧预算（例如 2 ms），超标的会标红。
4. 用勾选框临时停掉某个系统，确认它是否是卡顿来源。
5. 改完代码后 `Reset now`，重新积累平均值。

#### 4.10.5 Hierarchy 图标与 EntityLink

- Context / Entity / Systems 节点前会有 Entitas 图标；Systems 超阈值、Entity 被 Retain 时图标会变红。
- 选中 `DemoEntity_0` 的 `EntityLink`：
  - `Unlink`：解绑 GameObject 和实体。
  - `Show entity`：跳到对应的 Entity 节点。
  - 下方直接显示实体组件（和 Entity 面板一致）。

#### 4.10.6 Unity 6 兼容适配（本项目已做）

1.14.1 的 VisualDebugging 编辑器代码在 Unity 6 下有两个问题：

1. `Styles.ToolbarSearchTextField` 用 `GUI.skin.FindStyle("ToolbarSearchTextField")`，Unity 6 返回 null，导致 `EditorLayout.SearchTextField` 抛 NRE，Inspector 布局错乱。
2. Hierarchy 图标通过 Asset Label 查找，官方 `.meta` 没有 label，`LoadTexture` 返回 null，每帧刷 `GUI.DrawTexture(null)`，造成卡顿。

本项目的适配：

| 位置 | 内容 |
|------|------|
| `Assets/Plugins/EntitasOfficial/DesperateDevs/Editor/Compat/` | `DesperateDevs.Unity.Editor` 源码，`Styles` 增加 `EditorStyles.toolbarSearchField` 回退，同名 asmdef 编译 |
| `Assets/Plugins/EntitasOfficial/DesperateDevs/Editor/DesperateDevs.Unity.Editor.dll.disabled` | 原 DLL 备份，Unity 不加载 |
| `Assets/Plugins/EntitasOfficial/Entitas/Editor/Images/*.png.meta` | 8 张 Hierarchy 图标补了 `labels:` |
| `Assets/Plugins/EntitasOfficial/Entitas/Editor/Entitas.VisualDebugging.Unity.Editor.dll` | 官方 DLL 保持启用，依赖适配后的 `DesperateDevs.Unity.Editor` |

**重新导入官方包时，这套适配会被覆盖**：需要重新复制 `Compat` 源码、禁用原 `DesperateDevs.Unity.Editor.dll`、补图标 label。

#### 4.10.7 构建与发布

- VisualDebugging 只在 Editor 生效；打包时不会带编辑器逻辑。
- 建议在 Player 构建里定义 `ENTITAS_DISABLE_VISUAL_DEBUGGING`，避免生成 `DebugSystems`/`ContextObserver` 相关分支。
- 不要把 Inspector 里的临时修改当作配置或存档数据。

---

## 5. 代码生成手册

代码生成不是"可选加速器"，而是 1.x 的正常写法。手写 `AddComponent(index, new XxxComponent())` 既难读又容易错索引。

### 5.1 Attribute 一览

| 特性 | 写法 | 作用 |
|------|------|------|
| Context | `[Game]` / `[Input]` | 组件归属哪个 Context（特性本身是生成的） |
| Unique | `[Game, Unique]` | 每个 Context 单例，生成 `context.SetX/ReplaceX/RemoveX` |
| Event | `[Game, Event(EventTarget.Any)]` | 生成监听器组件、接口、事件系统 |
| Event Removed | `[Event(EventTarget.Any, EventType.Removed)]` | 移除时也触发 |
| Cleanup | `[Game, Cleanup(CleanupMode.RemoveComponent)]` | 帧末移除组件 |
| Cleanup | `[Game, Cleanup(CleanupMode.DestroyEntity)]` | 帧末销毁实体 |
| EntityIndex | `[EntityIndex]` | 普通索引，一键多实体 |
| PrimaryEntityIndex | `[PrimaryEntityIndex]` | 唯一索引，重复 key 抛异常 |
| CustomEntityIndex | `[CustomEntityIndex(typeof(GameContext))]` | 自定义索引类 |
| FlagPrefix | `[Game, FlagPrefix("flag")]` | flag 属性改名 `flagX` |
| DontGenerate | `[DontGenerate]` | 不生成组件 API |
| ComponentName | `[ComponentName("Pos")]` | 覆盖组件名 |
| PostConstructor | `[PostConstructor]` | `Contexts` 构造后调用（注册索引） |

### 5.2 生成物清单

以 `Game` Context、`PositionComponent` 为例：

| 生成物 | 内容 |
|--------|------|
| `GameAttribute.cs` | `[Game]` 特性 |
| `GameComponentsLookup.cs` | 组件索引常量（如 `Position = 9`，实际值以生成结果为准）、`TotalComponents` |
| `GameEntity.cs` | `partial class GameEntity : Entitas.Entity` |
| `Components/GamePositionComponent.cs` | `position` / `hasPosition` / `AddPosition` / `ReplacePosition` / `RemovePosition` + `GameMatcher.Position` |
| `GameMatcher.cs` | `AllOf` / `AnyOf` |
| `GameContext.cs` | `partial class GameContext : Context<GameEntity>` |
| `Contexts.cs` | `sharedInstance`、`game` 属性、`Reset()`、ContextObserver |
| `Feature.cs` | `Feature` 基类 |

有 `[Unique]` 时还会生成 `context.SetX/ReplaceX/RemoveX/hasX/x`；有 `[Event]` 时生成 `Events/` 目录；有 `[EntityIndex]` 时在 `Contexts` 里生成 `InitializeEntityIndices`。

### 5.3 为什么"改组件"会卡住

生成器需要解析**能编译的工程**：

1. 你改了组件名/删了字段。
2. 旧生成代码还在引用旧名字 → 编译失败。
3. 编译失败 → 生成器读不到新代码 → 无法重新生成。

官方 FAQ 的绕法：

1. 新建 `Assets/StreamingAssets/`（该目录不参与编译）。
2. 把手写代码（Components/Systems/Controller）临时移进去。
3. 删掉 `Assets/Generated/` 整个目录。
4. 生成一次（此时只有框架，没有你的组件）。
5. 把手写代码移回来，改好组件。
6. 再生成。
7. 修系统里的编译错误。

**降低频率的办法**：改组件前先想清楚字段；一次改完再生成；生成目录入库，出问题能回滚。

### 5.4 配置项

`Jenny.properties`：

```properties
# Context 列表，第一个是默认 Context
Entitas.CodeGeneration.Plugins.Contexts = Game, Input

# 是否忽略命名空间
Entitas.CodeGeneration.Plugins.IgnoreNamespaces = false

# 目标工程（asmdef 工程填 GameLogic.csproj）
Jenny.Plugins.ProjectPath = Assembly-CSharp.csproj

# 生成目录
Jenny.Plugins.TargetDirectory = Assets/Generated
```

`Entitas.properties`：可视化调试相关（系统耗时阈值、TypeDrawer 目录等）。

### 5.5 生成入口

| 方式 | 操作 |
|------|------|
| **CLI（推荐，Unity 6 也稳）** | `dotnet Jenny\Jenny.Generator.Cli.dll client gen`（先起 server），或 `doctor` 先 dry-run |
| 自动导入 | 运行 `Jenny-Auto-Import.bat`（`Jenny auto-import -s` + `Jenny doctor`） |
| Unity 菜单 | `Tools > Jenny > Generate`（`Ctrl+Shift+G`）；Unity 2022+ 窗口有已知问题，失败就切 CLI |

生成成功会打印 `Generated N files (...)`；失败先看 Console 第一条错误，再检查 server 窗口。

---

## 6. 实战：回合制 Roguelike 切片

目标：一个玩家、一个怪物、一张格子地图；玩家走一步，怪物追一步；撞到就扣血；血量为 0 死亡。

### 6.1 设计

**Context**：`Game`（玩法）、`Input`（指令）。

**组件**：

| 组件 | 类型 | 归属 | 说明 |
|------|------|------|------|
| `GridPositionComponent` | `Vector2Int` | Game | 格子坐标 |
| `ActorComponent` | `int Team` | Game | 阵营（0 玩家，1 怪物） |
| `HealthComponent` | `Current/Max` | Game | 血量 |
| `AttackComponent` | `int Damage` | Game | 攻击力 |
| `TurnComponent` | `Round/State` | Game | 单例，回合状态 |
| `DeadComponent` | flag | Game | 死亡标记，帧末销毁 |
| `MoveInputComponent` | `Vector2Int Delta` | Input | 一次性指令，帧末销毁 |

**系统顺序**：

```
InputSystem（Input）
→ PlayerActionSystem（Game）
→ AISystem（Game）
→ DeathSystem（Game）
→ InputCleanupSystems（生成）
→ GameCleanupSystems（生成）
```

> 事件/表现层（`DamageSystem`、`ViewSystem`）在第 4 节已经单独演示，这个切片先保持纯逻辑，方便你先把回合跑通。

### 6.2 组件代码

```csharp
using Entitas;
using Entitas.CodeGeneration.Attributes;
using UnityEngine;

public enum TurnState
{
    PlayerInput,
    EnemyTurn
}

[Game]
public sealed class GridPositionComponent : IComponent
{
    public Vector2Int Value;
}

[Game]
public sealed class ActorComponent : IComponent
{
    public int Team;
}

[Game]
public sealed class HealthComponent : IComponent
{
    public int Current;
    public int Max;
}

[Game]
public sealed class AttackComponent : IComponent
{
    public int Damage;
}

[Game, Unique]
public sealed class TurnComponent : IComponent
{
    public int Round;
    public TurnState State;
}

[Game, Cleanup(CleanupMode.DestroyEntity)]
public sealed class DeadComponent : IComponent
{
}

[Input, Unique, Cleanup(CleanupMode.DestroyEntity)]
public sealed class MoveInputComponent : IComponent
{
    public Vector2Int Delta;
}
```

### 6.3 输入系统

```csharp
using Entitas;
using UnityEngine;

public sealed class InputSystem : IExecuteSystem
{
    readonly InputContext _input;
    readonly GameContext _game;

    public InputSystem(Contexts contexts)
    {
        _input = contexts.input;
        _game = contexts.game;
    }

    public void Execute()
    {
        if (!_game.hasTurn || _game.turn.State != TurnState.PlayerInput)
        {
            return;
        }

        var delta = ReadDelta();
        if (delta == Vector2Int.zero)
        {
            return;
        }

        _input.CreateEntity().AddMoveInput(delta);
    }

    static Vector2Int ReadDelta()
    {
        if (Input.GetKeyDown(KeyCode.W)) return Vector2Int.up;
        if (Input.GetKeyDown(KeyCode.S)) return Vector2Int.down;
        if (Input.GetKeyDown(KeyCode.A)) return Vector2Int.left;
        if (Input.GetKeyDown(KeyCode.D)) return Vector2Int.right;
        return Vector2Int.zero;
    }
}
```

### 6.4 玩家行动

```csharp
using Entitas;

public sealed class PlayerActionSystem : IExecuteSystem
{
    readonly Contexts _contexts;
    readonly IGroup<GameEntity> _actors;

    public PlayerActionSystem(Contexts contexts)
    {
        _contexts = contexts;
        _actors = contexts.game.GetGroup(
            GameMatcher.AllOf(GameMatcher.Actor, GameMatcher.GridPosition, GameMatcher.Health)
                .NoneOf(GameMatcher.Dead));
    }

    public void Execute()
    {
        if (!_contexts.game.hasTurn || !_contexts.input.hasMoveInput)
        {
            return;
        }

        if (_contexts.game.turn.State != TurnState.PlayerInput)
        {
            return;
        }

        var player = FindActor(0);
        if (player == null)
        {
            return;
        }

        var target = player.gridPosition.Value + _contexts.input.moveInput.Delta;
        var other = FindActorAt(target);

        if (other != null && other.actor.Team != player.actor.Team)
        {
            Attack(player, other);
        }
        else if (other == null)
        {
            player.ReplaceGridPosition(target);
        }

        _contexts.game.ReplaceTurn(_contexts.game.turn.Round, TurnState.EnemyTurn);
    }

    GameEntity FindActor(int team)
    {
        var entities = _actors.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            if (entities[i].actor.Team == team)
            {
                return entities[i];
            }
        }

        return null;
    }

    GameEntity FindActorAt(UnityEngine.Vector2Int position)
    {
        var entities = _actors.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            if (entities[i].gridPosition.Value == position)
            {
                return entities[i];
            }
        }

        return null;
    }

    static void Attack(GameEntity attacker, GameEntity target)
    {
        var current = target.health.Current - attacker.attack.Damage;
        target.ReplaceHealth(current < 0 ? 0 : current, target.health.Max);
    }
}
```

> 这里为了短，直接改了 `Health`。真实项目建议改成 `target.ReplaceDamaged(...)` 发事件，由 `DamageSystem` 结算、UI 订阅。

### 6.5 怪物 AI

```csharp
using Entitas;
using UnityEngine;

public sealed class AISystem : IExecuteSystem
{
    readonly Contexts _contexts;
    readonly IGroup<GameEntity> _actors;

    public AISystem(Contexts contexts)
    {
        _contexts = contexts;
        _actors = contexts.game.GetGroup(
            GameMatcher.AllOf(GameMatcher.Actor, GameMatcher.GridPosition, GameMatcher.Health)
                .NoneOf(GameMatcher.Dead));
    }

    public void Execute()
    {
        if (!_contexts.game.hasTurn || _contexts.game.turn.State != TurnState.EnemyTurn)
        {
            return;
        }

        var player = FindActor(0);
        if (player == null)
        {
            return;
        }

        var entities = _actors.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            var enemy = entities[i];
            if (enemy.actor.Team == 0 || enemy.health.Current <= 0)
            {
                continue;
            }

            var position = enemy.gridPosition.Value;
            var target = player.gridPosition.Value;

            if (position == target)
            {
                continue;
            }

            var step = new Vector2Int(System.Math.Sign(target.x - position.x), 0);
            if (step.x == 0)
            {
                step = new Vector2Int(0, System.Math.Sign(target.y - position.y));
            }

            var next = position + step;
            if (next == target)
            {
                var current = player.health.Current - enemy.attack.Damage;
                player.ReplaceHealth(current < 0 ? 0 : current, player.health.Max);
            }
            else if (FindActorAt(next) == null)
            {
                enemy.ReplaceGridPosition(next);
            }
        }

        _contexts.game.ReplaceTurn(_contexts.game.turn.Round + 1, TurnState.PlayerInput);
    }

    GameEntity FindActor(int team)
    {
        var entities = _actors.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            if (entities[i].actor.Team == team)
            {
                return entities[i];
            }
        }

        return null;
    }

    GameEntity FindActorAt(Vector2Int position)
    {
        var entities = _actors.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            if (entities[i].gridPosition.Value == position)
            {
                return entities[i];
            }
        }

        return null;
    }
}
```

> 两个系统里的 `FindActor` / `FindActorAt` 是重复实现。真实项目应抽成 `GameContext` 扩展方法，或用 `EntityIndex`（见 4.8）直接按坐标查。

### 6.6 死亡与清理

```csharp
using Entitas;

public sealed class DeathSystem : IExecuteSystem
{
    readonly IGroup<GameEntity> _alive;

    public DeathSystem(GameContext context)
    {
        _alive = context.GetGroup(GameMatcher.Health);
    }

    public void Execute()
    {
        var entities = _alive.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            var entity = entities[i];
            if (entity.health.Current <= 0 && !entity.isDead)
            {
                entity.isDead = true;
            }
        }
    }
}
```

`DeadComponent` 带 `Cleanup(DestroyEntity)`，帧末由生成的 `GameCleanupSystems` 销毁，所以同一帧里 AI、掉落、动画都还能看到"尸体"。

### 6.7 系统树与启动

```csharp
public sealed class GameSystems : Feature
{
    public GameSystems(Contexts contexts)
    {
        Add(new InputSystem(contexts));
        Add(new PlayerActionSystem(contexts));
        Add(new AISystem(contexts));
        Add(new DeathSystem(contexts.game));

        // 如果定义了 [Event] 组件，再加生成的 GameEventSystems
        Add(new InputCleanupSystems(contexts));
        Add(new GameCleanupSystems(contexts));
    }
}
```

```csharp
using Entitas;
using UnityEngine;

public sealed class GameBootstrap : MonoBehaviour
{
    Systems _systems;

    void Start()
    {
        var contexts = Contexts.sharedInstance;

        contexts.game.SetTurn(0, TurnState.PlayerInput);

        CreatePlayer(contexts.game, new Vector2Int(1, 1));
        CreateEnemy(contexts.game, new Vector2Int(5, 5));

        _systems = new GameSystems(contexts);
        _systems.Initialize();
    }

    void Update()
    {
        _systems.Execute();
        _systems.Cleanup();
    }

    void OnDestroy()
    {
        _systems.TearDown();
    }

    static void CreatePlayer(GameContext game, Vector2Int position)
    {
        var entity = game.CreateEntity();
        entity.AddGridPosition(position);
        entity.AddActor(0);
        entity.AddHealth(20, 20);
        entity.AddAttack(5);
    }

    static void CreateEnemy(GameContext game, Vector2Int position)
    {
        var entity = game.CreateEntity();
        entity.AddGridPosition(position);
        entity.AddActor(1);
        entity.AddHealth(10, 10);
        entity.AddAttack(3);
    }
}
```

### 6.8 这一局怎么跑

1. `InputSystem` 读 WASD，创建一条 `MoveInput`。
2. `PlayerActionSystem` 消费指令：撞墙不动、撞怪扣血、空地移动；然后把回合交给怪物。
3. `AISystem` 让每只怪物追一步，结束后回合数 +1，交还玩家。
4. `DeathSystem` 把血量归零的实体标记 `Dead`。
5. `InputCleanupSystems` 帧末销毁残留的 `MoveInput` 实体，`GameCleanupSystems` 帧末销毁 `Dead` 实体。

这就是一个最小可玩的回合制循环。加技能、物品、状态效果，都是"加组件 + 加系统 + 插到正确位置"。

---

## 7. 常见错误与排查

| 报错/现象 | 原因 | 处理 |
|-----------|------|------|
| `The type or namespace name 'GameAttribute' could not be found` | 还没生成过 `[Game]` 特性 | 先空生成一次 |
| `Could not find .csproj` | `ProjectPath` 填错，或 Unity 还没生成 csproj | `Assets > Open C# Project` 后重试 |
| 报 `Jenny.SearchPaths` | 插件目录没配对 | 指向 Jenny 包里的 `Jenny/Plugins/Entitas` 与 `Jenny/Plugins/Jenny` |
| `You must install or update .NET` | 生成机没有 .NET 6 Runtime | 安装 .NET 6，或设 `DOTNET_ROLL_FORWARD=LatestMajor` |
| 生成后编译错 | 组件改名/删字段，旧生成代码还在 | 按 5.3 的 StreamingAssets 流程重生成 |
| `EntityAlreadyHasComponentException` | 重复 `AddX` | 先 `hasX` 判断，或改 `ReplaceX` |
| `EntityDoesNotHaveComponentException` | `RemoveX` 了不存在的组件 | 先判断 |
| `GroupSingleEntityException` | 同一 Context 出现多个单例 | 用 `context.SetX`，不要 `entity.AddX` |
| `EntityIndexException` | PrimaryIndex 重复 key | 检查是否两个实体同 Id/同格 |
| ReactiveSystem 不触发 | 直接改字段、没走 Replace；或事件系统没注册 | 改 `ReplaceX`；检查系统树 |
| 事件不触发 | 监听器实体没创建；监听接口没实现；事件系统顺序错 | 检查 `AddAnyXListener` 与 `GameEventSystems` |
| 实体查不到 | Context 用错；实体已 `Destroy` | ContextObserver 确认 |
| 帧率下降 | Matcher/Group 太多；高频组件建了索引 | 减少 Matcher；高频数据改拉模式 |
| 真机泛型报错 | 热更/AOT 程序集边界 | 生成 + 业务放同一热更程序集；运行时 DLL 保持 AOT 可引用 |
| 异步加载后实体已销毁 | 回调没校验生命周期 | `entity.isEnabled && context.HasEntity(entity)` |

排查顺序：**先编译 → 再确认生成 → 再看实体在哪个 Context → 再看 Matcher 是否命中 → 最后看修改方式**。不要一上来就怀疑框架。

---

## 8. 性能建议

1. **控制 Matcher 数量**。官方 FAQ 的原话：100 个 Group × 每帧 2 万次组件替换 = 200 万次 `Matches`。每个 Group 都会监听每一次组件变化。
2. **不要给每帧变化的组件建 Matcher/索引**。位置、朝向这类高频数据用"拉"（系统里直接读），不要用 Group 事件推。
3. **缓存 Group**。在构造函数里 `GetGroup` 一次，不要每帧查。
4. **不要在 `Execute` 里 new 集合、LINQ、字符串拼接**。
5. **实体及时销毁**，但用 `Dead` 标记 + 帧末清理，不要中途直接 `Destroy` 打断后续系统。
6. **单例不要滥用**。Unique 组件会生成额外的 `GetSingleEntity` 查询和一套 Context API。
7. **Context 不要拆太细**。每个 Context 的实体都带一份组件数组。
8. **JobSystem 只做只读计算**，写组件回主线程。

---

## 9. 接入 TEngine 的建议

- 目录：`Assets/GameScripts/HotFix/GameLogic/Entitas/`（Components / Systems / Features / Generated），生成目录入库。
- 程序集：Entitas 以 DLL 形式被引用；**生成代码 + 业务系统必须在同一个热更程序集** `GameLogic`，不要把组件和系统拆到不同程序集。Jenny 只在 Editor。
- 资源：View 系统用 TEngine 的异步资源接口，禁止 `Resources.Load`；异步回调必须校验实体存活。
- UI：ECS 事件 → `UiBridgeSystem` → TEngine `GameEvent`；UI 不引用 Entitas 类型。
- 配置：Luban 表不进 Context，系统直接读配置服务；只有本局可变值才放 `[Unique]` 组件。
- 流程：TEngine 的 Procedure 负责进出战斗；进入建 Context/Systems，退出 `TearDown` + `Reset`。
- 热更：先用真机 IL2CPP + HybridCLR 验证 `Context<GameEntity>`、`Matcher<GameEntity>`、生成的事件系统能跑。

---

## 10. 速查表

**Entity**

```csharp
e.AddX(...); e.ReplaceX(...); e.RemoveX();
e.hasX; e.x; e.isFlag;
e.creationIndex; e.Destroy();
```

**Context**

```csharp
context.CreateEntity();
context.GetGroup(GameMatcher.X);
context.GetEntities(GameMatcher.AllOf(X, Y));
context.SetX(...); context.ReplaceX(...); context.RemoveX();
context.Reset();
```

**Matcher**

```csharp
AllOf(A, B); AnyOf(A, B); AllOf(A).NoneOf(B);
```

**Group**

```csharp
group.GetEntities();
group.GetSingleEntity();
group.OnEntityAdded / Removed / Updated;
```

**ReactiveSystem**

```csharp
protected override ICollector<T> GetTrigger(IContext<T> context);
protected override bool Filter(T entity);
protected override void Execute(List<T> entities);
```

**生成物命名**

| 组件名 | Entity API | Matcher |
|--------|------------|---------|
| `PositionComponent` | `AddPosition/ReplacePosition/RemovePosition/hasPosition/position` | `GameMatcher.Position` |
| `MovableComponent`（flag） | `isMovable` | `GameMatcher.Movable` |
| `TurnComponent`（Unique） | `context.SetTurn/ReplaceTurn/RemoveTurn/hasTurn/turn` | `GameMatcher.Turn` |

**常用快捷键/菜单**

| 操作 | 入口 |
|------|------|
| 生成代码 | `Tools > Jenny > Generate` / `Ctrl+Shift+G` |
| Entitas 设置 | `Tools > Entitas > Preferences...` / `Ctrl+Shift+E` |
| 查看实体 | 运行时 Hierarchy 的 `Contexts` 节点 |

---

## 11. FAQ

**Q：可以不用代码生成吗？**
可以。直接 `entity.AddComponent(GameComponentsLookup.Position, new PositionComponent())`，但可读性差、索引易错。也可以用第三方的 Entitas-Lite（无生成器）。

**Q：组件索引能写进存档吗？**
不能。`GameComponentsLookup` 的数值会随组件增删整体偏移。存档要存组件名或业务 ID，使用时重新映射。

**Q：一个组件能同时属于多个 Context 吗？**
可以，写 `[Game, Input]`。但每个 Context 都会有一份组件槽位和一套生成 API，跨 Context 的实体不能直接互传，必须用 ID/事件。

**Q：为什么生成这么多文件？**
每个 Context 的 Entity/Matcher/Context/Lookup 各一份，每个组件一份 API，事件/索引/清理再各生成一套。这是 1.x 的设计，换来的是业务代码可读。

**Q：多人协作时生成代码老冲突怎么办？**
固定生成顺序、生成目录入库、改组件前先合并；冲突时以"重新生成"为准，不要手工合并生成文件。

**Q：能升级到 2.x 吗？**
2.x（master 的 Roslyn 生成器）还没正式发布，API 与 1.x 不同（`[Context(typeof(...))]`、`GamePositionMatcher`、`Entity.Id`），社区案例为零。生产项目留在 1.14.1。

**Q：支持 IL2CPP / 热更吗？**
Entitas 是纯 C#，支持 IL2CPP。热更时把**生成代码 + 业务系统**放同一热更程序集，运行时 DLL 保持 AOT 可引用，并先用真机验证泛型实例化。

**Q：怎么做回放？**
记录"种子 + 每帧/每回合指令流"，重放时用同一套系统和同样的随机序列。逻辑层不要用 `UnityEngine.Random`/`Time`/`Physics`。

**Q：UI 能不能直接订阅 ECS 事件？**
能，但不建议。UI 实现 `IAnyXxxListener` 会直接依赖 Entitas 类型；更好的做法是桥接系统转成项目自己的 `GameEvent`。

---

## 附：1.14.1 与常见教程的差异

| 教程里的写法 | 1.14.1 实际 |
|--------------|-------------|
| `Tools > Entitas > Generate` | `Tools > Jenny > Generate`（`Ctrl+Shift+G`） |
| 把 Entitas 源码拖进 Assets | Release 提供的是 DLL 包（`Entitas.zip`） |
| 直接生成，无需额外进程 | 需要 Jenny server（`.NET 6`），或使用 CLI |
| `Pools` / `ISetPools` | `Context` / `Contexts` + 构造函数注入 |
| 属性大驼峰（`Count`、`ContextInfo`） | 1.14.1 属性是小驼峰（`count`、`contextInfo`） |

