# Entitas 框架调研与实战指南

> 调研时间：2026-11-14
> 调研方式：GitHub 仓库源码直读 + GitHub Search API 取数 + CSDN 搜索接口 + 中文社区文章抽样精读 + 官方 Wiki
> 说明：本文没有在 Unity 里实际编译运行 Entitas，所有结论来自源码、生成代码快照、示例工程结构与社区文章。涉及版本差异的地方会明确标注。

**目录**

- [0. 一句话结论](#0-一句话结论先看这里)
- [1. 调研样本](#1-调研样本)
- [2. 这个框架到底是什么](#2-这个框架到底是什么)
- [3. 版本与接入方式](#3-版本与接入方式)
- [4. 标准工作流：从 0 到跑起来](#4-标准工作流从-0-到跑起来)
- [5. 每个模块怎么用](#5-每个模块怎么用api--示例--注意点)
- [6. 功能配方：具体需求怎么做](#6-功能配方具体需求怎么做)
- [7. 别人是怎么设计代码的](#7-别人是怎么设计代码的案例拆解)
- [8. 常见坑清单](#8-常见坑清单按踩坑概率排序)
- [9. 落到你这个 Roguelike 项目](#9-落到你这个-roguelike-项目)
- [10. 参考来源与核验说明](#10-参考来源与核验说明)
- [附录 A：最小可运行骨架](#附录-a最小可运行骨架复制用)
- [附录 B：术语对照](#附录-b术语对照读老文章必备)

---

## 0. 一句话结论（先看这里）

**Entitas 是一套"代码生成 + 数据与逻辑彻底分离"的 C# ECS 框架，稳定版 1.14.x 已经停止功能迭代（2022-11 之后只有零星维护），master 分支正在重写为 Roslyn 源生成器（2.x 形态，未正式发布）。它适合做规则复杂、需要回放/同步/确定性模拟的玩法内核，不适合拿来做 UI、动画、资源加载这类 OOP 更顺手的部分。**

对你这个 Roguelike 项目，我的判断是：

- **值得借鉴、可以试点，但不建议"全项目 ECS 化"**。用 Entitas 承载回合推进、地图格子、AI、战斗结算、状态/物品这些"纯数据 + 纯规则"的部分；UI、表现、资源、流程仍走 TEngine 现有模块。
- **试点成本可控**：一个垂直切片（移动 + 回合 + 一个怪物 AI）大约 3～5 天能跑通；真正的成本在"团队习惯改造"和"代码生成流水线"，不在 API 学习。
- **版本选择要务实**：生产用 1.14.x（Jenny 生成器，资料最多、示例最多）；不要用 master 的 2.x 生成器做正式项目，API 还在变，社区案例为零。

---

## 1. 调研样本

### 1.1 GitHub 项目（star 数为 2026-11-14 通过 GitHub Search API 抓取）

| # | 项目 | Star | 语言 | 最后 push | 类型 | 我实际核实到的内容 |
|---|------|------|------|-----------|------|-------------------|
| 1 | [sschmid/Entitas](https://github.com/sschmid/Entitas) | 7688 | C# | 2023-12-30 | 官方框架 | 读了 `src/Entitas` 全部核心类、`src/Entitas.Generators.Attributes`、`samples/Unity`、`tests/.../snapshots` 生成代码快照 |
| 2 | [proepkes/UnityLockstep](https://github.com/proepkes/UnityLockstep) | 712 | C# | 2019-03-21 | 确定性帧同步 + 预测回滚 | 读 README 架构说明：ECS 核心不依赖 Unity，服务器控制台 + Unity 只做表现 |
| 3 | [JuDelCo/Entitas-Cpp](https://github.com/JuDelCo/Entitas-Cpp) | 356 | C++ | 2023-07-01 | C++11 移植 | 读 README/仓库定位，用于验证"框架概念可跨语言"，不参与 Unity 实践 |
| 4 | [sschmid/Match-One](https://github.com/sschmid/Match-One) | 214 | C# | 2023-07-28 | 官方推荐入门项目（三消） | 读了目录结构、`GameSystems`、`GameController`、`FallSystem`、`BoardSystem`、`AddViewSystem`、`View`、生成代码 |
| 5 | [RomanZhu/Entitas-Sync-Framework](https://github.com/RomanZhu/Entitas-Sync-Framework) | 171 | C# | 2019-06-12 | 回合制网络同步 | 读 README：Sync 标记组件自动同步、命令系统、位缓冲、服务端/客户端 Feature |
| 6 | [JamesMcMahon/entitas-2d-roguelike](https://github.com/JamesMcMahon/entitas-2d-roguelike) | 153 | C# | 2017-06-13 | 把 Unity 官方 2D Roguelike 教程重写为 ECS | 读 README 的改造动机与迁移思路 |
| 7 | [rocwood/Entitas-Lite](https://github.com/rocwood/Entitas-Lite) | 152 | C# | 2022-06-30 | 无代码生成分支 | 读 README 与手写 API 示例：`Context<Default>.AllOf<T1,T2>()`、`e.Get<T>()`、`e.Modify<T>()` |
| 8 | [jeffcampbellmakesgames/Entitas-Redux](https://github.com/jeffcampbellmakesgames/Entitas-Redux) | 104 | C# | 2022-04-29 | 带代码生成与可视化调试的分支 | README 未取到，仅按仓库描述与 star/更新记录列为参考 |
| 9 | [sschmid/Entitas-Shmup](https://github.com/sschmid/Entitas-Shmup) | 75 | C# | 2017-04-01 | 官方进阶示例（打飞机） | 读了 `Assets/Sources/Features` 目录、`GameController.createSystems()`、`IncrementTickSystem`；注意它用的是 0.35 旧 API |
| 10 | [IceLanguage/Pokemon_Unity3D_Entitas](https://github.com/IceLanguage/Pokemon_Unity3D_Entitas) | 72 | C# | 2018-12-29 | 国内宝可梦玩法 Demo | 读 README 定位 |
| 11 | [RomanZhu/Endless-Runner-Entitas-ECS](https://github.com/RomanZhu/Endless-Runner-Entitas-ECS) | 66 | C# | 2018-09-18 | 跑酷模板 | 按官方 Wiki 示例列表收录，未逐文件读 |
| 12 | [mzaks/Entitas-ReactiveUI](https://github.com/mzaks/Entitas-ReactiveUI) | 65 | C# | 2017-05-17 | ReactiveUI + Entitas 的响应式 UI 实验 | 按 star 与仓库描述收录 |
| 13 | [ShadeSlider/Entitas-RTS-Template](https://github.com/ShadeSlider/Entitas-RTS-Template) | 47 | C# | 2018-01-21 | RTS 模板 | 官方 Wiki 描述：配置管理、输入、场景 GameObject 初始化 |
| 14 | [sschmid/Entitas-CSharp-Example](https://github.com/sschmid/Entitas-CSharp-Example) | 47 | C# | 2017-02-14 | 早期官方 HelloWorld | 官方 Wiki 收录，用于对照老 API |
| 15 | [sschmid/Entitas-Standalone](https://github.com/sschmid/Entitas-Standalone) | 33 | C# | 2022-11-10 | 纯 C# 控制台 + NuGet + Jenny CLI | 读了 `src/Program.cs`、`HealthComponent.cs`、`jenny/Program.cs`、csproj |
| 16 | [BlueMonk1107/Samurai2_BasedEntitas](https://github.com/BlueMonk1107/Samurai2_BasedEntitas) | 31 | C# | 2019-05-20 | 国内《武士二》案例（Entitas + GOAP） | 核对仓库体积与目录（含 `Assets/Entitas`、`BlueGOAP`），未逐文件读 |
| 17 | [cloudjubei/EntitasTanks](https://github.com/cloudjubei/EntitasTanks) | 32 | C# | 2017-12-08 | Unity Tanks 示例的 Entitas 移植 | 官方 Wiki 收录 |
| 18 | [QianMo/Unity-Entitas-Framework-Usage](https://github.com/QianMo/Unity-Entitas-Framework-Usage) | 27 | C# | 2017-12-02 | "上手使用与实用性测试" | 读 README 定位：偏测评与心得，不是完整游戏 |

> 统计口径说明：以上是"相关项目"而不是"全部用 Entitas 做的商业游戏"。真正上线的商业产品（Wooga、Gram Games、Popcore、Plarium 等）不开源，官方 README 只给了公司名单，没有可核实的项目链接，本文不把它们当作案例。

### 1.2 中文社区文章（CSDN 为主，按主题分组）

> 数据来自 CSDN 搜索接口（标题、作者、阅读量、发布时间），链接为文章原始地址。抓取时 CSDN 对连续请求返回 521 限流，因此没有逐篇打开正文；标 ★ 的是我实际抓取并读了正文的。

**入门与概念**

| # | 文章 | 作者 | 阅读 | 时间 | 链接 |
|---|------|------|------|------|------|
| 1 | Unity3D Entitas Wooga 的 ECS Entity Component System 入门学习 1 | 暗光之痕 | 11215 | 2017-07-19 | https://blog.csdn.net/u012632851/article/details/75370836 |
| 2 | Unity ECS 之 Entitas 的简单介绍、插件下载、导入和简单使用 | 仙魁XAN | 7780 | 2021-01-18 | https://blog.csdn.net/u014361280/article/details/112732257 |
| 3 | Unity 框架探索——ECS 架构 Entitas 篇之基础概念 | 蓝天小僧（Andy） | 6814 | 2019-01-12 | https://blog.csdn.net/zcaixzy5211314/article/details/84888743 |
| 4 | ECS 框架学习（Entitas）入门 | 舌尖上的中国001 | 6721 | 2019-03-18 | https://blog.csdn.net/wkqwe/article/details/88639447 |
| 5 | ECS 架构 Entitas-CSharp 学习之路（一） | 寂灭万乘 | 3756 | 2018-04-10 | https://blog.csdn.net/qq_34244317/article/details/79887524 |
| 6 | 我所理解的 Entitas——入门（一） | s0ok | 2547 | 2020-11-21 | https://blog.csdn.net/u010020342/article/details/109898326 |
| 7 | Entitas 深入研究（2）：Unity 交互 | 金朝 | 2144 | 2019-02-26 | https://blog.csdn.net/zjz520yy/article/details/87932615 |
| 8 | Unity3D ECS 框架 Entitas 基本概念 | edison_maze | 2041 | 2018-10-08 | https://blog.csdn.net/edison_maze/article/details/82970421 |

**原理与源码分析**

| # | 文章 | 作者 | 阅读 | 时间 | 链接 |
|---|------|------|------|------|------|
| 9 ★ | Unity3D ECS 框架 Entitas 入门学习 4：ReactiveSystem 原理总结 | 暗光之痕 | 6378 | 2017-12-25 | https://blog.csdn.net/u012632851/article/details/78895750 |
| 10 ★ | ECS Entitas 源码分析（一）概括 | 爱上对方zzq | 1415 | 2020-07-10 | https://blog.csdn.net/u013781447/article/details/107225502 |
| 11 | ECS Entitas 源码分析（二）Context | 爱上对方zzq | 1069 | 2020-07-16 | https://blog.csdn.net/u013781447/article/details/107303520 |
| 12 | EntitasLite 源码分析（四） | 栗子大人 | 1089 | 2024-11-26 | https://blog.csdn.net/zhiai315/article/details/144070915 |
| 13 | unity 游戏开发之 entitas 框架 | 清木Moyu | 2173 | 2019-06-18 | https://blog.csdn.net/sun124608666/article/details/92767103 |

**代码生成与工具链**

| # | 文章 | 作者 | 阅读 | 时间 | 链接 |
|---|------|------|------|------|------|
| 14 | ECS Entitas1.5 Jenny 使用方法 | Bili最光阴 | 2110 | 2018-04-10 | https://blog.csdn.net/u011627082/article/details/79881751 |
| 15 | ECS Entitas 1.13.0 Jenny 使用方法 | GA博客 | 1551 | 2021-03-28 | https://blog.csdn.net/baidu_39447417/article/details/115275222 |
| 16 | Entitas 配套代码自动生成工具 | 蓝天小僧（Andy） | 1683 | 2019-03-02 | https://blog.csdn.net/zcaixzy5211314/article/details/88082672 |
| 17 | ECS 架构 Entitas-CSharp 学习之路（三） | 寂灭万乘 | 1483 | 2018-04-10 | https://blog.csdn.net/qq_34244317/article/details/79887538 |

**工程实战**

| # | 文章 | 作者 | 阅读 | 时间 | 链接 |
|---|------|------|------|------|------|
| 18 | Unity 使用 ECS 架构 entitas 实现 UI 响应及回放系统 | 神码编程 | 12120 | 2017-10-03 | https://blog.csdn.net/qq992817263/article/details/78155443 |
| 19 | 如何使用 Entitas 开发游戏（FNGGames） | jince1991 | 6971 | 2018-06-04 | https://blog.csdn.net/u012662020/article/details/80574960 |
| 20 | 如何使用 Entitas 构建游戏 | NK_1012620 | 4395 | 2018-05-30 | https://blog.csdn.net/zty_1012620/article/details/80507517 |
| 21 | 使用 Entitas 构建游戏框架（一） | popcorn丶 | 3276 | 2022-05-01 | https://blog.csdn.net/qq_17347313/article/details/124521453 |
| 22 | Unity 使用 Entitas 开发逻辑显示分离 Demo（一） | 东北砍王 | 2229 | 2021-05-19 | https://blog.csdn.net/qq_33064771/article/details/117049431 |
| 23 | Unity 手游实战：ECS 设计思想和 Entitas 插件 | donnyxia1128 | 2659 | 2022-06-29 | https://blog.csdn.net/summerhust/article/details/125523595 |
| 24 ★ | Unity 手游实战：从 0 开始 SLG——ECS 设计思想和 Entitas 插件 | UWA | 1963 | 2019-09-04 | https://blog.csdn.net/uwa4d/article/details/100535531 |
| 25 | Unity 手游实战：从 0 开始 SLG——ECS 战斗（二）Entitas 插件 | 壹种念头 | 1558 | 2020-06-29 | https://blog.csdn.net/haog87/article/details/107026981 |

**坑与经验**

| # | 文章 | 作者 | 阅读 | 时间 | 链接 |
|---|------|------|------|------|------|
| 26 | Unity3d Entitas 框架 入门深坑总结 1 | Xiaojueming | 1443 | 2018-08-28 | https://blog.csdn.net/xiaojueming/article/details/82145757 |
| 27 | Entitas 框架学习笔记 | 警言 | 1356 | 2019-04-13 | https://blog.csdn.net/xj1009420846/article/details/89283165 |
| 28 | 我所理解的 Entitas——Attributes（十一） | s0ok | 1096 | 2020-11-22 | https://blog.csdn.net/u010020342/article/details/109898879 |

**其他平台补充**

| # | 来源 | 内容 | 链接 |
|---|------|------|------|
| 29 | 腾讯云开发者社区 | ECS（Entitas）For Unity #1（与掘金同文） | https://cloud.tencent.com/developer/article/2115430 |
| 30 | 腾讯云开发者社区 | Unity 手游实战：从 0 开始 SLG——ECS 战斗（二）Entitas 插件 | https://cloud.tencent.com/developer/article/1659090 |
| 31 | 掘金 | 同上（SLG ECS 战斗 Entitas 插件） | https://juejin.cn/post/6950947952353345544 |

> 中文资料的整体特征：**2017～2021 年的文章占绝大多数，几乎全部基于 1.x（Jenny），且集中在"入门 + 源码分析 + 如何生成代码"**。真正讲"工程化、模块划分、长期维护"的很少，这也是我后面要结合 GitHub 工程结构来补的部分。另外要注意：不少文章里还在用 `Pool`/`Pools` 这个词，那是 0.36 之前的叫法，现在叫 `Context`。

---

## 2. 这个框架到底是什么

### 2.1 核心概念

Entitas 的概念非常少，官方 README 的说法是"需要知道的类一只手数得过来"：

```
                    ┌──────────────────────────────┐
                    │           Context            │
                    │  （实体容器 + 工厂 + 索引）   │
                    │                              │
                    │   e   e    e   e   e         │
                    └───────┬──────────────────────┘
                            │ 1:N
                            ▼
                    ┌──────────────┐        ┌─────────────┐
                    │    Entity    │ 1:N    │  Component  │
                    │ （只有 id 和  │───────►│ （纯数据）   │
                    │  组件数组）   │        └─────────────┘
                    └──────┬───────┘
                           │ 被筛选
                           ▼
                    ┌──────────────┐        ┌─────────────┐
                    │    Group      │◄──────│   Matcher   │
                    │ （满足条件的   │        │ （筛选条件） │
                    │  实体子集）    │        └─────────────┘
                    └──────┬───────┘
                           │ 事件
                           ▼
                    ┌──────────────┐
                    │  Collector   │──► ReactiveSystem（攒一批再处理）
                    └──────────────┘
```

- **Context**：实体的"世界"。负责创建/销毁实体、缓存 Group、维护 EntityIndex。一个游戏可以有几个 Context（Match-One 用了 Game / Input / GameState / Config 四个）。
- **Entity**：一个 int id + 一个 `IComponent[]` 数组。本身没有任何业务字段。组件的增删改都会发事件。
- **Component**：只实现空接口 `IComponent` 的数据类。**不要放方法、不要放逻辑**（可以有 `ToString`、只读属性、简单的值对象）。
- **Group**：某个 Matcher 对应的实体集合，随实体变化**自动增量维护**。所以 `GetGroup(...).GetEntities()` 几乎是 O(1) 拿结果。
- **Matcher**：`AllOf / AnyOf / NoneOf` 组合出来的筛选条件，被当作 Group 的 key 缓存。
- **Collector**：订阅 Group 的增删事件，把"这一帧发生变化的实体"攒起来，供 ReactiveSystem 批量处理。
- **System**：纯逻辑。只有 5 种生命周期接口：`IInitializeSystem`、`IExecuteSystem`、`IReactiveSystem`、`ICleanupSystem`、`ITearDownSystem`。

### 2.2 数据流（一帧发生了什么）

```
Unity Update
  └─ GameController.Update()
       ├─ systems.Execute()
       │    ├─ IExecuteSystem.Execute()           每帧跑（输入、移动、AI）
       │    └─ ReactiveSystem.Execute()           只处理 Collector 攒到的变化实体
       └─ systems.Cleanup()
            └─ ICleanupSystem.Cleanup()           清理"一次性"组件/实体
```

`Initialize` 在启动时跑一次，`TearDown` 在销毁时跑一次。顺序完全由你 `Add()` 的顺序决定，**没有隐式排序，也没有依赖注入容器**——这是优点（可预测）也是缺点（手工维护顺序）。

### 2.3 性能设计：为什么它敢说"super fast"

读源码可以确认几个关键点（`src/Entitas`）：

1. **实体池**：`Context` 内部有 `Stack<TEntity> _reusableEntities`，`DestroyEntity` 后实体对象被回收复用，不反复 new。
2. **组件池**：每个 Context 每个组件索引一个 `Stack<IComponent>`，`RemoveComponent` 把组件对象压回池子，`CreateComponent` 优先复用。**这也是一个坑：你移除的组件对象可能马上被别的实体复用，不能长期持有引用。**
3. **Group 增量更新**：`Context` 维护 `List<IGroup>[] _groupsForIndex`，组件变化时只通知"关心这个组件索引"的 Group，而不是遍历所有 Group。
4. **Matcher 缓存**：同样的 Matcher 只会创建一个 Group，`GetGroup` 命中字典。
5. **数组缓存**：`Entity` 的 `_componentsCache`、`_componentIndexesCache` 在变化时失效、下次访问重建。
6. **AERC（自动实体引用计数）**：Group/Collector 持有实体时增加引用计数，防止"还在被引用就被池化复用"。`ENTITAS_FAST_AND_UNSAFE` 宏可以换成 `UnsafeAERC` 换性能。

但官方 FAQ 里也明确写了一个**反直觉的性能陷阱**：

> 每个 Group 都会监听每个实体的每次组件变化，然后用自己的 Matcher 去比对。100 个 Group × 每帧 20000 次组件替换 = 200 万次 `Matches` 调用。官方自己的项目里因此删掉了所有 Transform/Position 相关的 Matcher。

这句话非常关键：**Entitas 的性能不是"用了就快"，而是"Group 数量 × 组件变更频率"决定的上限**。Roguelike 这种低频、回合制的场景反而很安全；实时弹幕/大量单位每帧移动的场景要非常小心。

### 2.4 代码生成：Entitas 的灵魂，也是最大的门槛

Entitas 的核心 API 是 `entity.AddComponent(index, component)` 这种"索引 + 强转"的写法。直接手写会又臭又长：

```csharp
entity.AddComponent(GameComponentsLookup.Position, new PositionComponent { Value = pos });
var p = (PositionComponent)entity.GetComponent(GameComponentsLookup.Position);
```

代码生成器（1.x 叫 **Jenny**）读取你的组件类，生成：

```csharp
// 生成的 GameEntity 扩展
public PositionComponent position { get; }
public bool hasPosition { get; }
public void AddPosition(Vector2Int newValue);
public void ReplacePosition(Vector2Int newValue);
public void RemovePosition();
```

于是业务代码变成：

```csharp
entity.AddPosition(new Vector2Int(1, 2));
if (entity.hasPosition) { var p = entity.position.Value; }
```

生成物通常包括（1.x，按 Context 各一份）：

| 生成物 | 作用 |
|--------|------|
| `GameComponentsLookup` | 组件索引、名字、类型表 |
| `GameEntity` + 各组件 partial 扩展 | `AddX / ReplaceX / RemoveX / hasX / x`；flag 组件生成 `isX` |
| `GameMatcher` | 每个组件的静态 Matcher（`GameMatcher.Position`） |
| `GameContext` | 继承 `Context<GameEntity>`，带 `ContextInfo` |
| `Contexts` | `sharedInstance`、`allContexts`（1.x 常用入口） |
| `[Unique]` 扩展 | `context.SetX(...)`、`context.x`、`context.hasX` |
| `[Event]` 扩展 | 监听器组件、监听接口、`XxxEventSystem`、`XxxEventSystems` |
| `[EntityIndex]` 扩展 | `GetEntityWithX` / `GetEntitiesWithX` |
| `[Cleanup]` 扩展 | 自动清理系统 |
| `Feature` / `ContextObserver` | 可视化调试相关（由 VisualDebugging 插件生成） |

**代价**：生成器靠反射读已编译的程序集，所以"组件改名/删字段"会先让生成代码编译不过，而编译不过又没法重新生成——形成死循环。官方 FAQ 给的解法是：把非生成代码临时挪到 `StreamingAssets`（不参与编译）→ 删生成目录 → 重新生成 → 挪回来 → 再生成。这个流程很土，但确实是 1.x 的标准操作。

### 2.5 框架仓库里到底有什么

Entitas 不是一个 DLL，而是一组项目/包（MIT 协议，可商用）。按职责分：

| 项目/包 | 职责 | 你需要关心吗 |
|---------|------|--------------|
| `Entitas` | 运行时核心：Context / Entity / Group / Matcher / Collector / Systems | 要，业务代码直接依赖 |
| `Entitas.CodeGeneration.Attributes` | `[Context]`、`[Unique]`、`[Event]`、`[EntityIndex]`、`[Cleanup]`、`[PostConstructor]` 等特性 | 要，写组件时用 |
| `Entitas.CodeGeneration.Plugins` | 1.x 的生成器插件集合（Context、Entity、Matcher、Event、Index、Cleanup…） | 配好即可，一般不改 |
| `Entitas.Roslyn.CodeGeneration.Plugins` | 1.13+ 的 Roslyn 数据提供器（配合 Jenny 用，解决部分反射问题） | 配好即可 |
| `Entitas.Blueprints` | 1.x 的"蓝图"（用预制体/配置批量创建实体），官方已标记为 deprecated | 新项目不要用 |
| `Entitas.Migration` | 老版本 API 升级工具 | 升级旧工程时用 |
| `Entitas.VisualDebugging.Unity` / `.Editor` | ContextObserver、DebugSystems、自定义 TypeDrawer | 调试时用 |
| `Entitas.Unity` | `EntityLink`、Unity 侧的小工具 | 要，View 绑定用 |
| `Feature`（不是独立包） | 1.x 里由 VisualDebugging 的 `FeatureClassGenerator` **生成**到你的工程；开启调试时继承 `DebugSystems`，否则继承 `Systems` | 用，生成一次即可 |
| `DesperateDevs` | Jenny 依赖的基础库（配置、序列化、反射、日志） | 不用管 |
| `Jenny` / `Jenny.Generator.Cli` | 代码生成器本体（编辑器菜单 / CLI） | 用，但不用改 |
| `Entitas.Generators`（master/2.x） | Roslyn 源生成器，替代 Jenny | 评估即可 |
| `Entitas.Benchmarks` / `Entitas.Tests` | 性能基准与单测 | 想看性能数据时读 |

一句话：**你真正会碰的只有 `Entitas` + `Attributes` + 生成器配置 + `VisualDebugging`**，其余是支撑设施。

---

## 3. 版本与接入方式

### 3.1 先把版本搞清楚

| 分支/版本 | 形态 | 代码生成 | 状态 | 建议 |
|-----------|------|----------|------|------|
| **1.14.x**（tag 到 1.14.1，CHANGELOG 最后一条 1.14.2，2022-11-11） | 传统 Entitas + Unity 集成 | Jenny（反射 + 模板，编辑器菜单生成） | 稳定、资料最多 | **生产项目选这个** |
| **master（2.x 形态）** | 重构为 .NET + Roslyn Source Generator | `Entitas.Generators`，编译期增量生成 | 未正式发布，README 里 UPM 还写着 "Coming soon" | 只适合学习和评估 |
| **Entitas-Lite**（第三方分支） | 去掉生成器，泛型 + 运行时反射/缓存 | 无 | 社区维护，2022 后基本停更 | 讨厌生成代码的团队可评估 |
| **Entitas-Cpp / entitas-lua / entitas-ts 等** | 其他语言移植 | 各自实现 | 与 Unity 无关 | 服务器/多端一致性参考 |

**为什么 1.x 和 2.x 不能混着看**：两代的 API 名字和接入方式都变了。

```csharp
// 1.x：组件用「生成的 Context 特性」标注
[Game]
public sealed class PositionComponent : IComponent { public Vector2Int Value; }
// 生成：entity.AddPosition(...)、GameMatcher.Position、Contexts.sharedInstance.game

// 2.x（master）：组件用 [Context(typeof(...))] 标注，Context 是 partial 类
[Context(typeof(GameContext))]
public sealed class PositionComponent : IComponent { public Vector2 Value; }
// 生成：entity.AddPosition(...)、GamePositionMatcher.Position、GamePositionComponentIndex.Index.Value
```

如果你看的中文文章是 2018～2021 年写的，基本都是 1.x；看官方仓库 `samples/Unity` 和 `tests/.../snapshots`，才是 2.x。

### 3.2 方式 A：Unity 项目接入 1.14.x（推荐）

**Step 1：拿包**
从 [Releases](https://github.com/sschmid/Entitas/releases) 下载对应版本（README 明确推荐 Releases，同时说明 NuGet 可用、UPM 尚未提供；Release 里通常附带 Unity 导入包和 NuGet 包）。不要直接 clone master 丢进 Unity。

**Step 2：导入后确认这些目录都在**

```
Assets/
├── Entitas/                 # 框架运行时 + 编辑器（Entitas、Entitas.Unity、Entitas.Unity.Editor）
├── DesperateDevs/           # Jenny 依赖的基础库（序列化、配置、反射工具；部分版本合并进 Jenny）
├── Jenny/                   # 代码生成器（编辑器）
└── Plugins/                 # 可能还有第三方插件
```

不同版本/不同示例的目录名不完全一样（Shmup 放在 `Assets/Libraries/Entitas`，Match-One 放在 `Assets/Entitas`），**以导入包的实际结构为准**，不要照抄路径。

**Step 3：配置 Context 和生成目录**
菜单 `Tools > Entitas`（1.x 里生成项是 `Generate`，设置项是 `Preferences/Settings...`，不同版本文案有差异），或直接改根目录的 `Entitas.properties` / `Jenny.properties`。关键项：

```properties
# 你要几个 Context，名字是什么（顺序有意义：第一个是默认 Context）
Entitas.CodeGeneration.Plugins.Contexts = Game, Input, GameState, Config

# 生成代码放哪：这里填 Unity 工程根（生成器会在其下建 Generated/<Context>/）
Jenny.Plugins.TargetDirectory = Assets

# 生成器需要能反射到你的程序集（路径按项目实际位置改）
Jenny.SearchPaths = Assets/Entitas, Jenny/Plugins/Entitas
Jenny.Plugins.ProjectPath = Assembly-CSharp.csproj

# 是否忽略命名空间（老项目常见 true；新项目建议 false）
Entitas.CodeGeneration.Plugins.IgnoreNamespaces = false
```

> 注意一个"先有鸡还是先有蛋"的问题：`[Game]`、`[Input]` 这些 Context 特性**本身也是生成出来的**（`GameAttribute.cs`）。所以全新工程的第一步是：先配好 Contexts → 生成一次（此时还没有组件）→ 拿到 Context 特性 → 再写组件 → 再生成。

**Step 4：写第一个组件**

```csharp
using Entitas;
using Entitas.CodeGeneration.Attributes;
using UnityEngine;

[Game]                                  // 归属 Game Context
public sealed class PositionComponent : IComponent
{
    public Vector2Int Value;            // 只能是字段/属性，不能有逻辑
}

[Game, Unique]                          // 每个 Context 只有一个
public sealed class TurnComponent : IComponent
{
    public int Value;
}

[Game]                                  // 无字段 = flag 组件
public sealed class PlayerComponent : IComponent { }
```

**Step 5：生成**
菜单 `Tools > Entitas > Generate`（若版本没有该主菜单，则在 `Tools > Entitas` 下找生成入口）。生成后检查 `Assets/Generated/Game/` 下是否出现 `GameEntity.cs`、`GameMatcher.cs`、`Components/GamePositionComponent.cs` 等。**第一次生成前必须保证项目能编译**，否则生成器反射不到程序集。

**Step 6：写系统、组系统树、驱动生命周期**（见第 4、5 节）

**Step 7：打开可视化调试**
在启动脚本里加：

```csharp
#if (!ENTITAS_DISABLE_VISUAL_DEBUGGING && UNITY_EDITOR)
var observer = new Entitas.VisualDebugging.Unity.ContextObserver(Contexts.sharedInstance.game);
UnityEngine.Object.DontDestroyOnLoad(observer.gameObject);
#endif
```

之后 Hierarchical 面板里能直接看每个 Context 的实体、组件字段，还能改值、删组件、销毁实体。系统的耗时也能用 `DebugSystems`（`Feature` 的调试版）看。

**Step 8：把生成纳入团队流程**
- 生成目录**提交到版本库**（否则每个人都要本地生成，且生成顺序可能不同导致 diff 噪音）。
- 约定"改组件 → 立刻生成 → 再改业务代码"，不要攒着。
- CI 里如果要做纯 C# 校验，可以用 `Jenny.Generator.Cli`（见 3.4）。

### 3.3 方式 B：2.x 源生成器（只建议评估）

master 的用法（来自 `samples/Unity` 与生成快照）：

```csharp
// 1) Context 是一个 partial 类，自己声明
partial class GameContext : IContext { }

// 2) 组件用 ContextAttribute 标注（可多个）
[Context(typeof(GameContext))]
public sealed class MyStringComponent : IComponent
{
    public string Value;
}

// 3) 初始化入口是 partial 方法，生成器补实现
public static partial class ContextInitialization
{
    public static void InitializeAllContexts()
    {
        InitializeGameContext();
        InitializeInputContext();
    }

    [ContextInitialization(typeof(GameContext))]
    public static partial void InitializeGameContext();
}
```

生成结果（快照里可以逐字核对；下面的类型名来自官方测试快照，实际名字由你的命名空间决定）：

```csharp
// 每个组件一个静态 Matcher 类
public static class MyAppMainSomeMatcher
{
    public static IMatcher<MyApp.Main.Entity> Some { get; }
}

// 每个组件一个索引类（运行时初始化）
global::MyAppMainSomeComponentIndex.Index = new ComponentIndex(0);

// Entity 扩展
public static Entity AddSome(this Entity entity);
public static Entity ReplaceSome(this Entity entity);
public static Entity RemoveSome(this Entity entity);
public static bool HasSome(this Entity entity);
public static SomeComponent GetSome(this Entity entity);
```

**评价**：方向是对的（编译期生成、增量、IDE 友好、不再有"改名死循环"），但 API 还在动、没有正式版本、没有社区案例。**现在接 2.x 等于给自己加一个不稳定的私有依赖。**

### 3.4 方式 C：纯 C# / 服务器 / 工具链（Entitas-Standalone）

官方示例 [Entitas-Standalone](https://github.com/sschmid/Entitas-Standalone) 核心只有几个文件，结构非常清楚：

```xml
<!-- src/MyProject.csproj -->
<PackageReference Include="Entitas" Version="1.*" />
<PackageReference Include="Entitas.CodeGeneration.Attributes" Version="1.*" />
```

```csharp
// src/Program.cs
var contexts = Contexts.sharedInstance;
var e = contexts.game.CreateEntity();
e.AddHealth(100);
Console.WriteLine(e.health.Value);
```

```csharp
// jenny/Program.cs —— 生成器的 CLI 入口
public static void Main(string[] args) => Jenny.Generator.Cli.Program.Main(args);
```

这套组合的意义：**逻辑层可以完全脱离 Unity 跑**。对 Roguelike 很有价值——战斗结算、地图生成、AI 可以做成纯 .NET 库，用 xUnit/NUnit 直接测，Unity 只做表现。UnityLockstep 就是这个思路的极致：ECS 核心工程不引用 UnityEngine，Unity 端只负责渲染和输入。

### 3.5 方式 D：Entitas-Lite（无代码生成）

如果团队抵触生成代码，Lite 的 API 是这样：

```csharp
public class MovementSystem : IExecuteSystem
{
    public void Execute()
    {
        var entities = Context<Default>.AllOf<PositionComponent, VelocityComponent>().GetEntities();
        foreach (var e in entities)
        {
            var vel = e.Get<VelocityComponent>();
            var pos = e.Modify<PositionComponent>();   // 主动标记"改过了"，才会触发 Monitor
            pos.x += vel.x;
            pos.y += vel.y;
        }
    }
}
```

它的取舍：**少了生成步骤和文件爆炸，多了运行时代理/反射开销和手写样板**。适合"组件不多、团队小、想快速上手"的项目；组件上百、追求极致性能的项目不合适。

### 3.6 接入现有 Unity 项目的检查清单

在动手前先确认这几件事，任何一条不满足都可能在接入过程中出问题：

| 检查项 | 为什么 | 处理方式 |
|--------|--------|----------|
| Unity 版本 | Entitas 1.14.x 发布时主流是 Unity 2021，Unity 2022/6 没有官方兼容性声明 | 先在目标版本的空工程里验证编译与生成；Match-One 自己用的是 2021.3.0f1 |
| 程序集定义（asmdef） | 生成器按 `SearchPaths`/`ProjectPath` 反射程序集，asmdef 拆多了会"找不到组件" | 把组件放到生成器配置能扫到的程序集；或把 asmdef 路径加进配置 |
| 热更方案（HybridCLR/IL2CPP） | 生成代码和组件必须和业务在同一热更程序集；Entitas 核心可放 AOT | 先做最小验证：热更程序集里定义组件 + 生成 + 运行 |
| 生成目录是否入库 | 不入库会导致每个人环境不一致 | 入库，并在 Code Review 里检查生成 diff |
| 命名空间 | 老项目常关 `IgnoreNamespaces`，容易和现有类重名 | 新代码建议开启命名空间 |
| 现有架构边界 | TEngine 已有资源/UI/流程/事件模块 | Entitas 只管玩法数据与规则，不要复刻一套资源/UI 系统 |

---

## 4. 标准工作流：从 0 到跑起来

这一节是"照着做就能出东西"的流程。以 1.x 为准。

### 4.1 七步法

**① 划 Context**
不要按"业务名词"划，按**生命周期和更新频率**划：

| Context | 放什么 | 为什么单独 |
|---------|--------|-----------|
| `Game` | 地图、单位、物品、战斗状态 | 核心模拟，可能需要确定性/回放 |
| `Input` | 玩家输入、UI 指令 | 输入是"外部事件"，和模拟解耦；回放时可替换 |
| `GameState` | 当前流程状态（准备/战斗/结算） | 状态机性质，变化少 |
| `Config` | 配置表数据（只读） | 只读、启动时灌入，和运行时实体分开 |

Match-One 就是 `Game / Input / GameState / Config` 四个；Shmup 是 `Input / Core / Bullets / Blueprints`（按"实体生命周期"分，子弹单独一个 Context 以便整体清理）。两种划法都对，关键是**别把所有东西塞一个 Context**（每个 Context 的实体都带一份全量组件数组，Context 越大越浪费）。

**② 写组件（只写数据）**

```csharp
[Game]
public sealed class HealthComponent : IComponent
{
    public int Current;
    public int Max;
}

[Game, Unique]
public sealed class TurnComponent : IComponent
{
    public int Round;
    public GameTurnState State;   // 自定义 enum
}

[Game, Event(EventTarget.Any)]     // 发生"受伤"时通知 UI
public sealed class DamagedComponent : IComponent
{
    public int Amount;
}

[Game, Cleanup(CleanupMode.RemoveComponent)]  // 每帧末自动移除
public sealed class SelectedComponent : IComponent { }
```

**③ 生成代码**（菜单，见 3.2）

**④ 写系统**（只写逻辑，通过 Context/Group 拿数据）

```csharp
public sealed class HealthSystem : IExecuteSystem
{
    readonly IGroup<GameEntity> _group;
    public HealthSystem(GameContext context)
    {
        _group = context.GetGroup(GameMatcher.Health);
    }

    public void Execute()
    {
        foreach (var e in _group.GetEntities())
        {
            if (e.health.Current <= 0 && !e.isDead)
                e.isDead = true;          // flag 组件的写法
        }
    }
}
```

**⑤ 用 Feature 组系统树**

```csharp
public sealed class GameSystems : Feature
{
    public GameSystems(Contexts contexts)
    {
        // 顺序 = 执行顺序，不要随意打乱
        Add(new InputSystem(contexts));
        Add(new TurnSystem(contexts));
        Add(new AISystem(contexts));
        Add(new MovementSystem(contexts));
        Add(new CombatSystem(contexts));
        Add(new DeathSystem(contexts));
        Add(new ViewSystem(contexts));       // 表现放最后

        Add(new GameEventSystems(contexts)); // 生成的，必须放最后
        Add(new GameCleanupSystems(contexts));
    }
}
```

**⑥ GameController 驱动生命周期**

```csharp
public sealed class GameController
{
    readonly Systems _systems;

    public GameController(Contexts contexts)
    {
        _systems = new GameSystems(contexts);
    }

    public void Initialize() => _systems.Initialize();
    public void Execute()
    {
        _systems.Execute();
        _systems.Cleanup();     // 注意：Cleanup 要跟 Execute 成对出现
    }
    public void TearDown() => _systems.TearDown();
}
```

```csharp
public sealed class GameControllerBehaviour : MonoBehaviour
{
    GameController _controller;
    void Awake()  => _controller = new GameController(Contexts.sharedInstance);
    void Start()  => _controller.Initialize();
    void Update() => _controller.Execute();
    void OnDestroy() => _controller.TearDown();
}
```

**⑦ 接表现层**
不要在系统里直接 `Instantiate` 然后到处 `Find`。标准做法是"实体上加 Asset/View 组件，专门的 View 系统负责实例化和绑定"（Match-One/Shmup 都是这个套路）：

```csharp
public sealed class AddViewSystem : ReactiveSystem<GameEntity>
{
    readonly Transform _parent;
    public AddViewSystem(Contexts contexts) : base(contexts.game)
        => _parent = new GameObject("Views").transform;

    protected override ICollector<GameEntity> GetTrigger(IContext<GameEntity> context)
        => context.CreateCollector(GameMatcher.Asset);

    protected override bool Filter(GameEntity entity) => entity.hasAsset && !entity.hasView;

    protected override void Execute(List<GameEntity> entities)
    {
        foreach (var e in entities)
        {
            var prefab = Resources.Load<GameObject>(e.asset.Value);
            var view = Object.Instantiate(prefab, _parent);
            view.Link(e);                        // Entitas.Unity 的 EntityLink
            e.AddView(view.GetComponent<GameView>());
        }
    }
}
```

### 4.2 一次完整的功能开发（ checklist ）

新增"中毒持续伤害"：

1. 组件：`[Game] PoisonComponent { int DamagePerTurn; int TurnsLeft; }`
2. 生成：菜单生成，确认 `GameEntity.AddPoison(...)` 出现
3. 系统：`PoisonSystem : IExecuteSystem`，`GetGroup(AllOf(Poison, Health))`，每回合扣血、减层数、归零时 `RemovePoison()`
4. 注册：`GameSystems` 里放在 `TurnSystem` 之后、`DeathSystem` 之前
5. 表现：`[Event(EventTarget.Any)]` 或 Group 事件通知 UI
6. 验证：ContextObserver 里看实体组件变化；断点看 Execute 顺序
7. 清理：如果中毒是"一次性施加"，记得 `Cleanup(RemoveComponent)`，否则会跨回合残留

---

## 5. 每个模块怎么用（API + 示例 + 注意点）

### 5.1 Component：只放数据

**四种常见形态：**

```csharp
// 1) 普通数据组件
[Game] public sealed class PositionComponent : IComponent { public Vector2Int Value; }

// 2) Flag 组件（零字段）——默认生成 isX；可用 [FlagPrefix("flag")] 改前缀
[Game] public sealed class DeadComponent : IComponent { }

// 3) 单例组件——每个 Context 只有一份
[Game, Unique] public sealed class TurnComponent : IComponent { public int Value; }

// 4) 事件组件——变化时生成监听器与事件系统
[Game, Event(EventTarget.Any)] public sealed class ScoreChangedComponent : IComponent { public int Value; }
```

**规则：**

- 组件类必须 `public`（生成器要反射），字段必须 `public`（EntityIndex 要求）。
- 一个组件类型在一个 Context 里只能有一个索引；**组件索引由生成器统一分配、各 Context 共用同一套编号**（`GameComponentsLookup.Position` 是编译期常量，不是运行时字典）。
- 不要放 `UnityEngine.Object` 的长期引用（GameObject、Texture、Material）。要放就放资源路径/ID，由 View 层解析。理由：逻辑层要能脱离 Unity 跑，且对象销毁后引用会变成"假 null"。
- 不要放对其它 Entity 的引用（官方 FAQ 明确不建议）。用 `IdComponent + PrimaryEntityIndex` 代替。
- 组件可以有自己的小工具方法（`ToString`、`IsAlive => Current > 0`），但不要依赖 Context/其它系统。

### 5.2 Entity：数据的容器

```csharp
var e = context.CreateEntity();

e.AddPosition(new Vector2Int(3, 4));
e.ReplacePosition(new Vector2Int(4, 4));
e.RemovePosition();

bool has = e.hasPosition;
var pos = e.position;              // 直接拿组件对象（引用）
e.isDead = true;                   // flag 组件
int id = e.creationIndex;          // 旧版；新版是 e.Id
```

**关键 API：**

| API | 说明 |
|-----|------|
| `entity.AddX/ReplaceX/RemoveX` | 生成方法；`Replace` 在不存在时会走 Add 逻辑（1.x 行为），但**建议先判断 has 再 Replace**，避免语义歧义 |
| `entity.GetComponent(index)` / `GetComponents()` | 底层访问，业务代码尽量不用 |
| `entity.Retain(owner)` / `Release(owner)` | 手动引用计数，跨帧持有实体时必须成对调用 |
| `entity.Destroy()` | 立即销毁：从 Context 移除、从所有 Group 移除、组件回池 |
| `entity.RemoveAllComponents()` | 只清组件，不销毁实体 |
| `entity.OnComponentAdded/Removed/Replaced` | 底层事件，一般用 Group 事件代替 |

**三个必须知道的坑：**

1. `Destroy()` 是**立即生效**的。A 系统销毁了实体，B 系统这一帧就再也看不到它，也就无法对它做结算/表现。→ 用 `DeadComponent`/`DestroyedComponent` 打标记，最后一个 `CleanupSystem` 统一销毁（Match-One 的 `DestroyedComponent` + `Cleanup(DestroyEntity)` 就是标准答案）。
2. 组件对象会被池化复用。`var c = e.position; e.RemovePosition();` 之后 `c` 可能已经被别的实体拿去用了。需要留存就拷贝值。
3. `Retain/Release` 不是给业务层随便用的。只有 Group、Collector、ReactiveSystem 这类"跨帧持有"的组件才需要；业务代码手动 Retain 很容易漏 Release 导致实体永远不回收。

### 5.3 Context：世界与工厂

```csharp
var context = Contexts.sharedInstance.game;   // 1.x 全局入口（也可自己 new GameContext()）
var e = context.CreateEntity();
var group = context.GetGroup(GameMatcher.Position);
var entities = context.GetEntities(GameMatcher.AllOf(Position, Velocity));
context.OnEntityCreated += (ctx, entity) => { /* 统一初始化 */ };
```

| API | 用途 |
|-----|------|
| `CreateEntity()` | 创建（从池里取） |
| `DestroyAllEntities()` | 销毁该 Context 的所有实体（切场景/重开时用） |
| `Reset()` | 清空所有实体并重置（`Contexts.Reset()` 会遍历所有 Context）；重开一局时用 |
| `GetGroup(matcher)` | 拿缓存的 Group |
| `GetEntities(matcher)` | 等价于 `GetGroup(matcher).GetEntities()`，内部也走缓存 |
| `AddEntityIndex(index)` | 注册索引（要在创建实体前，通常在 `[PostConstructor]` 里） |
| `GetEntityIndex(name)` | 取索引 |
| `contextInfo` | 组件名/类型表，调试用（1.x 属性是小驼峰，master 改成大驼峰） |

**Context 划分的实际影响**：实体只带"本 Context 的组件数组"，所以把子弹/特效放进独立 Context，整批销毁时直接 `DestroyAllEntities()` 很爽；但跨 Context 通信要显式（比如 Input 系统写 Input Context，Game 系统读 Input Context），不能直接拿另一个 Context 的 Entity 当组件字段。

### 5.4 Matcher 与 Group：查询

```csharp
using static GameMatcher;

var all  = context.GetGroup(AllOf(Position, Velocity));          // 同时拥有
var any  = context.GetGroup(AnyOf(Player, Enemy));               // 拥有任一
var none = context.GetGroup(AllOf(Position).NoneOf(Dead));       // 排除
var single = context.GetGroup(AllOf(Turn)).GetSingleEntity();    // 恰好一个，否则抛异常
```

**Group 事件：**

```csharp
var group = context.GetGroup(GameMatcher.Damaged);
group.OnEntityAdded   += (g, e, index, component) => { };
group.OnEntityRemoved += (g, e, index, component) => { };
group.OnEntityUpdated += (g, e, index, prev, next) => { };
```

**注意：**

- `GetSingleEntity()`：数量为 0 返回 `null`，数量 > 1 时**抛 `GroupSingleEntityException`**。单例组件用 `[Unique]` 更安全。
- 每创建一个新 Matcher 就会多一个 Group，Group 会监听所有实体变化。**Matcher 要复用**（用生成的 `GameMatcher.X`，不要每次 `Matcher<GameEntity>.AllOf(...)` 新建）。
- Group 的 `GetEntities()` 返回内部缓存的数组，**不要修改它**；需要排序/过滤请自己拷一份。

### 5.5 Collector 与 ReactiveSystem：只处理"变了的东西"

```csharp
public sealed class DeathSystem : ReactiveSystem<GameEntity>
{
    readonly GameContext _context;
    public DeathSystem(GameContext context) : base(context) => _context = context;

    // 1) 触发条件：关心哪些组件的哪种变化
    protected override ICollector<GameEntity> GetTrigger(IContext<GameEntity> context)
        => context.CreateCollector(GameMatcher.Health);

    // 2) 二次过滤：Collector 收进来后再筛一遍
    protected override bool Filter(GameEntity entity)
        => entity.hasHealth && entity.health.Current <= 0 && !entity.isDead;

    // 3) 批量处理：这一帧收集到的所有实体
    protected override void Execute(List<GameEntity> entities)
    {
        foreach (var e in entities)
            e.isDead = true;
    }
}
```

**ReactiveSystem 的执行时机**：它实现 `IExecuteSystem`，在 `systems.Execute()` 时被调用；内部先看 Collector 有没有攒到东西，没有就直接返回。所以**不需要每帧遍历全量实体**。

**关键细节（很多人踩）：**

- 只有通过 `Add/Replace/Remove` 修改组件才会触发；**直接改字段 `e.position.Value.x++` 不会触发**（暗光之痕的文章专门验证过这一点，官方 FAQ 也写了）。
- `GetTrigger` 里用的是 `CreateCollector(matcher)`，默认监听 `Added`；要监听 `Removed`/`Updated` 用 `TriggerOnEvent` 重载。
- 在 ReactiveSystem 里又去改组件，可能触发同一帧的连锁反应；**要保证系统顺序**，或者用 `Cleanup` 把"一次性组件"在帧末清掉。
- ReactiveSystem 默认是激活的；`systems.DeactivateReactiveSystems()` 可以在暂停/回放时停掉。

### 5.6 Systems 与 Feature：系统树

```csharp
public sealed class GameSystems : Feature
{
    public GameSystems(Contexts contexts)
    {
        Add(new InputSystem(contexts));
        Add(new TurnSystem(contexts));
        Add(new MovementSystem(contexts));
        Add(new CombatSystem(contexts));
        Add(new GameEventSystems(contexts));    // 生成
        Add(new GameCleanupSystems(contexts));  // 生成
    }
}
```

- `Feature` 是"有名字的 Systems"，本质还是按 `Add` 顺序执行。**坑点**：1.x 里 `Feature` 不是框架自带的类，而是由 VisualDebugging 的 `FeatureClassGenerator` 生成到你的工程里（开调试时继承 `DebugSystems`，否则继承 `Systems`）；如果你的生成器配置里没启用它，就没有 `Feature` 可用，直接用 `Systems` 即可。master/2.x 才把它内置进 `Entitas.Unity`。
- 一个系统可以实现多个接口，`Systems` 会按阶段分别调用：

```csharp
public sealed class BoardSystem : ReactiveSystem<GameEntity>, IInitializeSystem
{
    public void Initialize() { /* 建棋盘 */ }
    // ReactiveSystem 的 Execute...
}
```

- `Systems` 提供 `ActivateReactiveSystems / DeactivateReactiveSystems / ClearReactiveSystems`，做暂停、回放、重开时有用。
- 系统之间**不要互相引用**。需要共享数据就放到组件/Context 里，或者抽一个纯函数工具类（Match-One 的 `BoardLogic` 就是静态纯函数，方便测试）。

### 5.7 Events：组件变化的"发布订阅"

1.x 的事件是**生成出来的一套监听器组件**，不是 C# event。

```csharp
[Game, Event(EventTarget.Any)]
public sealed class DamagedComponent : IComponent { public int Amount; }
```

生成：

```csharp
public interface IAnyDamagedListener
{
    void OnAnyDamaged(GameEntity entity, int amount);
}

public sealed class AnyDamagedListenerComponent : IComponent
{
    public List<IAnyDamagedListener> value;
}

public sealed class AnyDamagedEventSystem : ReactiveSystem<GameEntity> { ... }
public sealed class GameEventSystems : Feature { Add(new AnyDamagedEventSystem(contexts)); }
```

用法：

```csharp
// UI 侧（MonoBehaviour）
public sealed class DamagePopup : MonoBehaviour, IAnyDamagedListener
{
    public void OnAnyDamaged(GameEntity entity, int amount) { /* 弹伤害数字 */ }
}

// 注册：找一个"监听器实体"，把 listener 挂上去
var listenerEntity = contexts.game.CreateEntity();
listenerEntity.AddAnyDamagedListener(damagePopup);
```

`EventTarget.Self` 与 `Any` 的区别：

| | `Self` | `Any` |
|---|--------|-------|
| 监听器挂在哪 | 产生事件的那个实体上 | 任意一个"监听器实体"上 |
| 生成接口 | `IDamagedListener.OnDamaged(GameEntity, int)` | `IAnyDamagedListener.OnAnyDamaged(GameEntity, int)` |
| 适用 | 这个实体自己的表现（View 跟随位置） | 全局 UI（分数、弹窗、音效） |

**坑（官方 FAQ 逐条列过）：**

- flag 组件要同时监听 true/false，得加 `EventType.Removed` 版本。
- 事件系统必须加到 `Systems` 里，且放在所有"会修改组件"的系统之后。
- 事件处理过程中再触发事件，可能因为顺序问题丢失；用 `Order` 调优先级，或延迟到下一帧。
- 监听器实体不用了要销毁/移除监听，否则 UI 关了还在收事件。

### 5.8 EntityIndex：按值查实体

```csharp
[Game]
public sealed class IdComponent : IComponent
{
    [PrimaryEntityIndex]        // 唯一索引 → GetEntityWithId
    public int Value;
}

[Game]
public sealed class GridComponent : IComponent
{
    [EntityIndex]               // 普通索引 → GetEntitiesWithGrid（可能多个）
    public Vector2Int Value;
}
```

```csharp
var e = context.GetEntityWithId(42);
var list = context.GetEntitiesWithGrid(new Vector2Int(3, 4));
```

**自定义索引**（Match-One 的做法，适合"一个格子一个单位"）：

```csharp
public partial class Contexts
{
    public const string Piece = "Piece";

    [Entitas.CodeGeneration.Attributes.PostConstructor]
    public void InitializePieceEntityIndices()
    {
        game.AddEntityIndex(new PrimaryEntityIndex<GameEntity, Vector2Int>(
            Piece,
            game.GetGroup(GameMatcher.AllOf(GameMatcher.Piece, GameMatcher.Position)
                                     .NoneOf(GameMatcher.Destroyed)),
            (e, c) => (c as PositionComponent)?.Value ?? e.position.Value));
    }
}

public static class PieceContextsExtension
{
    public static GameEntity GetPieceWithPosition(this GameContext ctx, Vector2Int v)
        => ((PrimaryEntityIndex<GameEntity, Vector2Int>)ctx.GetEntityIndex(Contexts.Piece)).GetEntity(v);
}
```

**注意**：索引要在实体创建之前注册（`[PostConstructor]` 就是干这个的）；索引本身也维护 Group，所以别建太多。

### 5.9 Unity 集成：EntityLink 与 View

Entitas 提供 `gameObject.Link(entity)` / `gameObject.Unlink()`（`Entitas.Unity`），在 GameObject 上挂一个 `EntityLink` 记录对应实体。标准 View 写法（Match-One）：

```csharp
public class View : MonoBehaviour, IView, IPositionListener, IDestroyedListener
{
    GameEntity _linkedEntity;

    public void Link(IEntity entity)
    {
        gameObject.Link(entity);
        _linkedEntity = (GameEntity)entity;
        _linkedEntity.AddPositionListener(this);    // Self 事件
        _linkedEntity.AddDestroyedListener(this);
        transform.localPosition = ...;
    }

    public void OnPosition(GameEntity entity, Vector2Int value)
        => transform.localPosition = new Vector3(value.x, value.y);

    public void OnDestroyed(GameEntity entity) => Destroy(gameObject);
}
```

要点：

- **View 只读实体，不写实体**。要发指令就走 Input Context 或命令组件。
- 实体销毁时记得 `Unlink`，否则 GameObject 上挂着已池化的实体引用。
- 大量同类 View 用对象池（Shmup 的 `AddViewFromObjectPoolSystem`），不要每次 Instantiate/Destroy。

### 5.10 调试手段

| 手段 | 用法 |
|------|------|
| `ContextObserver` | Hierarchy 里可视化 Context/Entity/Component，运行时可改值 |
| `DebugSystems` / `Feature` | 看每个系统耗时，定位慢系统 |
| `Entitas.VisualDebugging.Unity.Editor` | 自定义 `ITypeDrawer` 画自己的类型 |
| `Contexts.sharedInstance.game.ToString()` | 打印实体列表 |
| 断点 + `Matcher.Matches` | 排查"为什么这个实体没进 Group" |

---

## 6. 功能配方：具体需求怎么做

这一节给"可抄的骨架"。全部是 1.x 写法。

### 配方 1：输入 → 指令（跨 Context 的标准做法）

Match-One 的做法值得直接抄：**输入是"一次性实体"，帧末自动销毁**。

```csharp
// Input 组件：Unique + 帧末销毁
[Input, Unique, Cleanup(CleanupMode.DestroyEntity)]
public sealed class InputComponent : IComponent
{
    public Vector2Int Value;
}

// 每帧把 Unity 输入写成实体
public sealed class InputSystem : IExecuteSystem
{
    readonly Contexts _contexts;
    public InputSystem(Contexts contexts) => _contexts = contexts;

    public void Execute()
    {
        if (!Input.GetMouseButtonDown(0)) return;
        var world = Camera.main.ScreenToWorldPoint(Input.mousePosition);
        _contexts.input.CreateEntity().AddInput(new Vector2Int((int)world.x, (int)world.y));
    }
}

// 游戏侧消费输入（ReactiveSystem 监听 Input Context）
public sealed class ProcessInputSystem : ReactiveSystem<InputEntity>
{
    readonly Contexts _contexts;
    public ProcessInputSystem(Contexts contexts) : base(contexts.input) => _contexts = contexts;

    protected override ICollector<InputEntity> GetTrigger(IContext<InputEntity> context)
        => context.CreateCollector(InputMatcher.Input);

    protected override bool Filter(InputEntity entity) => entity.hasInput;

    protected override void Execute(List<InputEntity> entities)
    {
        var target = _contexts.game.GetPieceWithPosition(_contexts.input.input.Value);
        if (target != null && target.isInteractive) target.isDestroyed = true;
    }
}
```

要点：
- `[Unique]` + `Cleanup(DestroyEntity)` 让"这一帧的输入"天然只有一份，且不会残留。
- 注意：`[Unique]` 的唯一性由生成的 `context.SetX(...)` 检查，直接 `entity.AddX(...)` 是**绕过检查**的。这里能成立是因为"一帧最多一次点击 + 帧末销毁"；如果你的输入可能一帧多条，改成普通实体（非 Unique）并让消费方遍历。
- 输入系统只负责"翻译输入"，不碰 Game 的实体；消费方是 Game 侧的系统。
- 回放时把 InputSystem 换成"读录像"的系统即可，Game 逻辑完全不用改——这就是逻辑/输入分离的价值。

### 配方 2：回合制推进（Roguelike 核心）

```csharp
public enum TurnState { PlayerInput, Resolving, EnemyTurn, GameOver }

[Game, Unique]
public sealed class TurnComponent : IComponent
{
    public int Round;
    public TurnState State;
}

[Game]
public sealed class EnergyComponent : IComponent
{
    public int Current;
    public int Speed;          // 每回合恢复的能量
}

[Game]
public sealed class ReadyToActComponent : IComponent { }
```

```csharp
public sealed class TurnSystem : IExecuteSystem
{
    readonly Contexts _contexts;
    readonly IGroup<GameEntity> _actors;

    public TurnSystem(Contexts contexts)
    {
        _contexts = contexts;
        _actors = contexts.game.GetGroup(
            GameMatcher.AllOf(GameMatcher.Actor, GameMatcher.Energy));
    }

    public void Execute()
    {
        var turn = _contexts.game.turn;

        switch (turn.State)
        {
            case TurnState.PlayerInput:
                if (!_contexts.input.hasInput) return;   // 等玩家操作
                _contexts.game.ReplaceTurn(turn.Round, TurnState.Resolving);
                break;

            case TurnState.Resolving:
                // 指令已经在 ProcessInputSystem 里变成"意图组件"
                AdvanceEnergy();
                _contexts.game.ReplaceTurn(turn.Round, TurnState.EnemyTurn);
                break;

            case TurnState.EnemyTurn:
                // AISystem 在上一阶段已排好队，这里只等它们执行完
                _contexts.game.ReplaceTurn(turn.Round + 1, TurnState.PlayerInput);
                break;
        }
    }

    void AdvanceEnergy()
    {
        foreach (var e in _actors.GetEntities())
        {
            e.ReplaceEnergy(e.energy.Current + e.energy.Speed, e.energy.Speed);
            if (e.energy.Current >= 100)
                e.isReadyToAct = true;
        }
    }
}
```

**注意**：上面是"骨架"，真实项目里"谁在什么时候行动"通常要更细的调度（按 energy 排序、插入、打断）。核心原则是：**回合状态放在 `[Unique]` 组件里，推进逻辑放在一个系统里，其它系统只读状态决定要不要跑**。不要用 `MonoBehaviour.Update` 里的 if-else 拼回合。

### 配方 3：战斗、死亡与清理

```csharp
[Game]
public sealed class HealthComponent : IComponent { public int Current; public int Max; }

[Game]
public sealed class AttackComponent : IComponent { public int Damage; }

[Game, Event(EventTarget.Any)]
public sealed class DamagedComponent : IComponent { public int Amount; }

[Game, Event(EventTarget.Self), Cleanup(CleanupMode.DestroyEntity)]
public sealed class DeadComponent : IComponent { }

[Game, Cleanup(CleanupMode.RemoveComponent)]
public sealed class AttackRequestComponent : IComponent { public GameEntity Target; }
```

```csharp
// 结算伤害
public sealed class DamageSystem : ReactiveSystem<GameEntity>
{
    public DamageSystem(GameContext context) : base(context) { }

    protected override ICollector<GameEntity> GetTrigger(IContext<GameEntity> context)
        => context.CreateCollector(GameMatcher.Damaged);

    protected override bool Filter(GameEntity e) => e.hasHealth && e.hasDamaged;

    protected override void Execute(List<GameEntity> entities)
    {
        foreach (var e in entities)
        {
            var hp = Math.Max(0, e.health.Current - e.damaged.Amount);
            e.ReplaceHealth(hp, e.health.Max);
            if (hp == 0 && !e.isDead) e.isDead = true;
        }
    }
}
```

关键点：
- **伤害不要直接改 Health**，而是 `ReplaceDamaged(...)` 发事件，让结算、UI、音效各自订阅。这就是"事件驱动"的好处。
- `DeadComponent` 用 `Cleanup(DestroyEntity)`，帧末统一销毁，保证同一帧里其它系统还能看到"尸体"做掉落、动画。
- `AttackRequestComponent` 里存了 `GameEntity Target`——这是**反例**（官方不建议组件存实体引用）。正确做法是存 `TargetId`，用 `PrimaryEntityIndex` 查。这里只是为了演示"一次性请求组件"的写法。

### 配方 4：UI 与表现（事件监听）

```csharp
[Game, Event(EventTarget.Any)]
public sealed class ScoreChangedComponent : IComponent { public int Value; }
```

```csharp
public sealed class ScoreView : MonoBehaviour, IAnyScoreChangedListener
{
    [SerializeField] TMP_Text _label;

    public void OnAnyScoreChanged(GameEntity entity, int value)
        => _label.text = value.ToString();
}

// 启动时挂到监听器实体
public sealed class ScoreViewBootstrap : MonoBehaviour
{
    public ScoreView View;

    void Start()
    {
        var e = Contexts.sharedInstance.game.CreateEntity();
        e.AddAnyScoreChangedListener(View);
    }
}
```

**不适合 ECS 的部分**：UI 的布局、动画、Tween、文本本地化。这些留在原来的 UI 框架里，Entitas 只负责"把数据推过去"。UWA 的 SLG 文章也明确说 UI/网络层不适合 ECS。

### 配方 5：地图格子与"按坐标查实体"

Roguelike 的典型需求：`GetActorAt(x, y)`。

```csharp
[Game]
public sealed class GridPositionComponent : IComponent { public Vector2Int Value; }

[Game]
public sealed class BlocksMovementComponent : IComponent { }
```

方案 A：`[EntityIndex]`（一格可能多个实体，比如道具+怪物）

```csharp
[Game]
public sealed class GridPositionComponent : IComponent
{
    [EntityIndex] public Vector2Int Value;
}
// 生成：context.GetEntitiesWithGridPosition(pos)
```

方案 B：自定义 `PrimaryEntityIndex`（一格只允许一个"占据者"）——见 5.8 的 Match-One 写法。同一个 key 插入第二个实体时 `PrimaryEntityIndex` 会抛 `EntityIndexException`，等于免费帮你做了"格子占用校验"。

方案 C：不用索引，用二维数组缓存 entity id。**数据量小的时候这是最快的**，但要注意实体销毁时同步清理缓存。索引方案的优势是自动维护，劣势是每次位置变化都有 Group 更新开销。

### 配方 6：存档 / 回放 / 网络同步

Entitas 的组件是纯数据，这使三件事变简单：

| 需求 | 做法 | 参考 |
|------|------|------|
| 存档 | 遍历 Context 的实体，把组件序列化成 DTO（不要直接序列化组件类，容易和运行时耦合） | 自己写 `SaveSystem`；或看 `EntitasSaveLoader`（raveneer/EntitasSaveLoader） |
| 回放 | 记录"初始种子 + 每回合指令流"，重放时用同一套系统跑 | [神码编程：UI 响应及回放系统](https://blog.csdn.net/qq992817263/article/details/78155443)、[coding2233/Entitas-Replay-Demo](https://github.com/coding2233/Entitas-Replay-Demo) |
| 帧同步/状态同步 | 固定 tick + 确定性随机 + 只同步组件/指令 | [UnityLockstep](https://github.com/proepkes/UnityLockstep)、[Entitas-Sync-Framework](https://github.com/RomanZhu/Entitas-Sync-Framework) |

**确定性三条铁律**（Roguelike 做回放/种子分享必需）：

1. 逻辑层不调用 `UnityEngine.Random`、`Time.deltaTime`、`Physics`。
2. 随机数用带种子的自定义 `Rand`（Match-One 的 `Rand` 就是干这个的），并且**随机调用顺序必须稳定**。
3. 不用 `float` 做关键判定（浮点在不同平台可能不一致），用 int/定点。

### 配方 7：对象池与 View 复用（大量同类单位）

Shmup 的做法：

- `ViewObjectPoolComponent` 记录池子；
- `AddViewFromObjectPoolSystem` 从池里取 GameObject，绑定实体；
- 实体销毁时 View 回池，不 Destroy。

Roguelike 里怪物数量通常不大，可以先用简单 Instantiate/Destroy；等到了"弹幕/大量特效"再上池。

---

## 7. 别人是怎么设计代码的（案例拆解）

### 7.1 四种目录组织方式对比

| 项目 | 目录组织 | 特点 | 适合谁 |
|------|----------|------|--------|
| **Match-One** | `Assets/Match-One/{Board,Pieces,Input,View,Score,Config,Game}`，领域目录下放组件、系统（部分有 `Systems/` 子目录）、View | 按**领域**分；`GameSystems` 是唯一的系统树入口 | 中小型玩法项目，推荐 |
| **Shmup** | `Assets/Sources/Features/{Bullets,Enemies,Health,Input,Player,...}`，每个 Feature 里放 Component + System + ViewController | 按**功能垂直切片**分，改一个功能只动一个文件夹 | 功能多、团队并行开发 |
| **官方 sample（2.x）** | `Runtime/{Components,Contexts,Systems}` | 按**技术角色**分，适合演示 API | 学习，不适合大项目 |
| **Entitas-Standalone** | `src/*.cs` + `jenny/` + `Jenny.properties` | 极简，纯 .NET | 服务器/工具/测试 |

**我的建议**：用 Match-One 的"领域 + Systems 子目录"，因为 Roguelike 的领域边界（地图、单位、战斗、物品、AI）比"技术角色"稳定，比"功能切片"好找代码。

### 7.2 Match-One：一个"教科书级"的 Entitas 工程

它值得学的地方（都能在源码里逐行确认）：

1. **系统树只有一处**：`GameSystems` 构造函数里按 Input → 逻辑 → View → Event → Cleanup 排列，读代码时一眼能看出执行顺序。
2. **`GameController` 只做生命周期转发**：`Initialize/Execute`，不写业务。`GameControllerBehaviour` 只把 Unity 的 `Awake/Start/Update` 转发给它。
3. **`ReactiveSystem` 用在"变化驱动"的地方**：`FallSystem` 监听 `Destroyed`，只在下落发生时跑；`BoardSystem` 同时实现 `IInitializeSystem` + `ReactiveSystem`，初始化建棋盘、后续响应棋盘尺寸变化。
4. **纯函数抽出来**：`BoardLogic.GetNextEmptyRow(...)` 是静态纯函数，不依赖 Context，方便单测。
5. **EntityIndex 解决"按坐标找棋子"**：`PrimaryEntityIndex<GameEntity, Vector2Int>` + `GetPieceWithPosition` 扩展方法，业务代码读起来像普通字典查询。
6. **View 通过 Self 事件更新**：`PositionComponent` 标了 `[Event(EventTarget.Self)]`，`View` 实现 `IPositionListener`，位置变了才改 Transform，不做每帧同步。

### 7.3 Shmup：老 API，但工程结构仍然值得看

- `Assets/Sources/Features/*` 是"按功能切片"的典范：一个子弹功能 = `BulletComponent` + `BulletCoolDownSystem` + `BulletOutOfScreenSystem` + `BulletViewController`，全在一个文件夹。
- `GameController.createSystems()` 用链式 `Add` 把系统按"初始化 → 输入 → 更新 → 动画销毁 → 销毁"分组，注释清楚。
- 它用的是 0.35 的 `Pools`/`ISetPools`/`pools.CreateSystem(...)`，**不要照抄 API**，只学结构。
- 它有 `Assets/Tests`（NSpec），说明 ECS 系统是可以单测的：给系统喂一个 Context，断言组件变化。

### 7.4 UnityLockstep / Sync Framework：逻辑与引擎分离的极限

- **UnityLockstep**：ECS 核心是独立 .NET 工程，Unity 只做可视化；服务器跑同一套模拟。它证明了"Entitas 可以完全脱离 Unity"。
- **Sync Framework**：给实体打 `Sync` 标记，框架自动把组件变化写进位缓冲发给客户端；命令用特性标注后由 T4 模板生成序列化代码。它展示了"ECS + 代码生成"在**网络协议**上的延伸。
- 这两个项目的共同点：**把"模拟"和"表现/传输"彻底切开**。如果你的 Roguelike 以后要做联机/云存档/回放，这个边界从第一天就要划好。

### 7.5 怎么快速读懂一个陌生的 Entitas 项目

按这个顺序看，通常 30 分钟能摸清骨架：

1. **找 Context 配置**：`Entitas.properties` / `Jenny.properties` 里的 `Contexts = ...`。这决定了世界的划分。
2. **看 Components 目录**：组件清单就是"这个游戏有哪些数据"。按名字就能猜出玩法。
3. **看生成目录**：`Generated/Game/GameMatcher.cs` 告诉你有哪些查询入口；`GameComponentsLookup.cs` 告诉你组件索引。
4. **看系统树**：搜 `: Feature` 或 `new Feature(`，找到唯一的根，读 `Add(...)` 顺序。这是"游戏一帧的剧本"。
5. **看 GameController/入口**：确认 `Initialize/Execute/Cleanup/TearDown` 的调用时机。
6. **看 View/表现层**：搜 `Link(`、`IView`、`AddXxxListener`，确认数据怎么变成画面。
7. **看索引与事件**：搜 `EntityIndex`、`Event(`，这两类最容易在阅读时被忽略，但往往是"为什么查不到/为什么没刷新"的答案。

### 7.6 社区对 Entitas 的评价（来源观点 + 我的判断）

**正面（多篇文章重复提到）：**

- 逻辑与表现天然分离，组件只有数据 → 回放、预测、服务器复用容易（UWA SLG 文章、源码分析文章）。
- 系统之间互不感知，改一个功能不容易碰坏另一个（同上）。
- Group 缓存 + 组件池，访问快、GC 少（官方 README、源码分析）。
- 代码生成让业务代码接近自然语言，可读性高（官方 README、Jenny 使用文章）。

**负面（同样有出处）：**

- "框架很自闭，所有事情都要在框架内完成"；UI、行为树、动画不适合（[源码分析（一）](https://blog.csdn.net/u013781447/article/details/107225502)）。
- 文件数量爆炸、新人上手难、对热更不友好（同上）。
- 社区活跃度下降，2017～2021 的文章居多，新资料少（我的观察：GitHub 最后 push 2023-12；2024 年之后的中文新文章多是源码分析/项目介绍，系统性的工程实践很少）。
- 代码生成的"改名死循环"很折磨（官方 FAQ 专门写了一节）。

**我的判断**：这些优缺点都成立，但"文件多/上手难"是**团队问题**不是框架问题——用目录约定 + 代码模板可以大幅缓解；"不适合 UI"是**边界问题**，只要一开始就划清"Entitas 管模拟、TEngine 管表现"，就不会痛苦。

---

## 8. 常见坑清单（按踩坑概率排序）

| # | 坑 | 现象 | 规避 |
|---|----|------|------|
| 1 | 直接改组件字段 | ReactiveSystem / 事件不触发 | 一律用 `ReplaceX`；只读用 `e.x` |
| 2 | 立即 `Destroy()` | 后续系统拿不到实体，掉落/动画丢失 | 用 `Dead/Destroyed` 标记 + `Cleanup(DestroyEntity)` |
| 3 | 组件里存 Entity 引用 | 实体回收后引用失效/指向新实体 | 存 Id + `PrimaryEntityIndex` |
| 4 | 组件里存 GameObject/材质 | 逻辑层无法脱离 Unity；对象销毁后假 null | 存资源路径/ID，View 层解析 |
| 5 | 每次 new Matcher | Group 数量暴涨，每帧 Matches 调用爆炸 | 用生成的 `GameMatcher.X` 静态缓存 |
| 6 | 给高频变化的组件建 Matcher | 位置/朝向每帧变 → 大量 Group 更新 | 高频数据用"拉"不用"推"；官方自己删过 Position Matcher |
| 7 | 组件改名/删字段 | 生成代码编译不过，无法再生成 | 按官方 FAQ：挪代码到 `StreamingAssets` → 删生成目录 → 生成 → 挪回 → 再生成 |
| 8 | 生成目录不入库 | 每个人生成结果不同、CI 飘 | 入库，Review 生成 diff |
| 9 | 事件系统没加/顺序错 | 事件不触发、UI 不刷新 | 事件系统放最后；flag 事件加 `Removed` 版本 |
| 10 | 在事件处理里再触发事件 | 丢事件/顺序错乱 | 用 `Order`、或延迟到下一帧 |
| 11 | 监听器实体不清理 | UI 关了还在收事件、内存泄漏 | 关闭时 `RemoveXxxListener` / 销毁监听器实体 |
| 12 | `GetSingleEntity()` 当判空用 | 0 个返回 null 没事，多个时直接抛异常 | 单例用 `[Unique]`；不确定就 `GetEntities().Length` |
| 13 | 组件池复用 | 移除的组件对象被别的实体复用，旧引用数据错乱 | 不长期持有组件引用，需要就拷贝 |
| 14 | 手动 `Retain` 忘 `Release` | 实体永不回收，内存上涨 | 业务层不要手动 Retain；交给 Group/Collector |
| 15 | Context 拆得太细/太多 | 每个实体都带一份按 Context 组件数分配的数组，空实体也有固定开销 | 按生命周期拆，3～5 个足够 |
| 16 | asmdef 拆太碎 | 生成器扫不到组件，"组件不生成" | 配置 `SearchPaths`/`ProjectPath`，或组件放主程序集 |
| 17 | 热更程序集边界 | 生成代码在 AOT、组件在热更 → 类型对不上 | 组件 + 生成代码 + 系统放同一热更程序集 |
| 18 | 逻辑层用 `UnityEngine.Random`/`Time` | 回放/帧同步不一致 | 自建 `Rand` + 固定 tick |
| 19 | 在系统里 `Find`/`Instantiate` | 性能差、生命周期混乱 | View 系统统一创建，EntityLink 绑定 |
| 20 | 把 UI/动画/资源塞进 ECS | 系统数量爆炸、开发效率下降 | 这些留在 TEngine/Unity 原生层 |

---

## 9. 落到你这个 Roguelike 项目

> 前提：以下只是方案建议，没有改任何代码。是否引入、引入到什么程度，需要你拍板。

### 9.1 先回答"该不该用"

满足以下 **3 条以上**，才值得引入：

- 玩法规则复杂，状态多，且需要频繁加"新词条/新效果/新怪物"（Roguelike 的典型特征）。
- 需要**确定性**：种子复现、录像回放、以后可能联机。
- 逻辑需要脱离 Unity 做单测/服务器校验。
- 团队愿意接受"代码生成 + 数据驱动"的开发习惯。

如果只是"想试试 ECS"，或者项目只有 2～3 个月生命周期，**不建议**——学习和流水线成本收不回来。

### 9.2 如果引入：建议的边界

```
TEngine（保留）
├── 资源 / UI / 流程 / 配置表 / 音频 / 网络传输
└── Roguelike 玩法层（新）
    ├── Entitas：Game / Input / Config 三个 Context
    ├── 纯 .NET 规则库：地图生成、战斗公式、掉落（可单测）
    └── View 层：把实体数据映射到 TEngine 的 UI/Prefab
```

- **Context 划分**：`Game`（运行中的一切实体）、`Input`（玩家指令，一次性实体）、`Config`（配置表只读数据）。不要一上来就 5 个 Context。
- **组件清单（起步版）**：

| 类别 | 组件 |
|------|------|
| 空间 | `GridPosition`、`BlocksMovement`、`Visible` |
| 单位 | `Actor`、`Health`、`Energy`、`Faction`、`Attack`、`Defense` |
| 物品 | `Item`、`Equipped`、`Stackable`、`Consumable` |
| AI | `AI`（行为 id）、`Aggro`、`PatrolRoute` |
| 回合 | `Turn`（Unique）、`ReadyToAct` |
| 表现 | `Asset`、`View`、`Animation` |
| 事件 | `Damaged`、`Died`、`PickedUp`、`TurnEnded` |

- **系统顺序（建议）**：

```
InputSystem → ProcessInputSystem
→ TurnSystem → AISystem → MovementSystem → CombatSystem
→ StatusEffectSystem → DeathSystem → LootSystem
→ ViewSystem → EventSystems（生成）→ CleanupSystems（生成）
```

- **与 TEngine 的接缝**：
  - 配置表：TEngine 的 Luban 数据加载后，灌进 `Config` Context（`contexts.config.SetXxx(...)`），玩法系统只读。
  - UI：Entitas 事件 → TEngine 的 UI 层（`IAnyXxxListener` 实现里调用 UI 模块），不要让 UI 直接改实体。
  - 资源：View 系统通过 TEngine 的资源模块加载 Prefab，而不是 `Resources.Load`。
  - 流程：TEngine 的流程状态机负责"进入战斗/退出战斗"，进入时创建 Context、退出时 `DestroyAllEntities()` + `TearDown()`。

### 9.3 迁移路径（低风险）

1. **第 1 周**：空工程验证 1.14.x + Unity 版本 + 热更方案；跑通"组件 → 生成 → 系统 → ContextObserver"。
2. **第 2 周**：在现有项目里做一个**垂直切片**（玩家移动 + 一个怪物 + 一次攻击结算），用 Feature 包起来，通过一个开关和旧逻辑并存。
3. **第 3～4 周**：把切片扩成"一局完整战斗"（回合、AI、掉落、死亡、胜负），补回放/种子校验。
4. **评估**：如果切片期间团队明显不适应（生成流程、调试方式），及时止损；如果可以，再逐步把地图生成、物品、技能迁进来。

### 9.4 成本与风险（保守估计）

| 项 | 估计 |
|----|------|
| 框架学习（1 人达到能独立写系统） | 3～5 天 |
| 流水线（生成、目录、Code Review 规则） | 2～3 天 |
| 垂直切片 | 3～5 天 |
| 一局完整战斗 | 2～4 周 |
| 主要风险 | 热更程序集边界、团队习惯、生成代码 diff 噪音、后期无人维护（社区已不活跃） |

**最大的风险不是技术，是"只有你一个人懂"**。如果团队里没有人能接手，ECS 会变成黑盒。引入前先确认至少 2 个人能独立开发。

---

## 10. 参考来源与核验说明

### 10.1 官方资料

- [sschmid/Entitas（GitHub）](https://github.com/sschmid/Entitas) — 源码、README、samples、benchmarks
- [Entitas Wiki](https://github.com/sschmid/Entitas/wiki) — Home / Code-Generator / Unity-integration / Example-projects / FAQ
- [Entitas 1.14.x Releases](https://github.com/sschmid/Entitas/releases)
- [sschmid/Match-One](https://github.com/sschmid/Match-One) — 官方推荐入门工程
- [sschmid/Entitas-Shmup](https://github.com/sschmid/Entitas-Shmup) — 进阶示例（旧 API）
- [sschmid/Entitas-Standalone](https://github.com/sschmid/Entitas-Standalone) — 纯 C# 工程

### 10.2 GitHub 项目（完整列表见 1.1）

除 1.1 的 18 个项目外，还参考了：
- [coding2233/Entitas-Replay-Demo](https://github.com/coding2233/Entitas-Replay-Demo) — 回放 Demo
- [raveneer/EntitasSaveLoader](https://github.com/raveneer/EntitasSaveLoader) — 存档扩展
- [OndrejNepozitek/Roguelike-Entitas](https://github.com/OndrejNepozitek/Roguelike-Entitas) — Roguelike + 多人 POC
- [sniper00/entitas-lua](https://github.com/sniper00/entitas-lua)、[darkoverlordofdata/entitas-ts](https://github.com/darkoverlordofdata/entitas-ts) — 其他语言实现

### 10.3 中文文章（完整列表见 1.2，共 28 篇 CSDN + 3 篇其他平台）

重点参考：
- 暗光之痕的入门系列（1/3/4）——概念讲得最细，ReactiveSystem 那篇有实测
- 爱上对方zzq 的源码分析（一/二）——模块划分与优缺点总结
- UWA / 放牛的星星的 SLG 系列——工程视角，明确说 UI/网络不适合 ECS
- Bili最光阴 / GA博客 的 Jenny 使用——代码生成的操作步骤
- 神码编程 的 UI 响应及回放——回放系统的落地思路

### 10.4 核验与限制

- GitHub star、最后 push 时间：2026-11-14 通过 GitHub Search API 获取。
- 官方版本：`git ls-remote --tags` 显示 tag 到 `1.14.1`，CHANGELOG 最后一条为 `1.14.2 (2022-11-11)`；master 上的生成器**没有正式 release**。
- 中文文章：通过 CSDN 搜索接口获取标题/作者/阅读量/时间；连续抓取时被 521 限流，因此未逐篇核对正文，仅对 3 篇标 ★ 的文章做了正文抽取。
- **没有实际编译运行**：Entitas 的 Unity 接入、代码生成、热更兼容性都需要在你的真实工程里验证，本文只能保证"源码与示例层面的事实准确"。

---

## 附录 A：最小可运行骨架（复制用）

```
Assets/
├── Entitas/                     # 框架（导入包）
├── Generated/                   # 生成（不要手改）
│   ├── Game/
│   └── Input/
├── Sources/
│   ├── Components/
│   │   ├── Game/PositionComponent.cs
│   │   ├── Game/HealthComponent.cs
│   │   └── Input/InputComponent.cs
│   ├── Contexts/
│   │   └── ContextsExtensions.cs
│   ├── Features/
│   │   ├── Movement/MovementSystem.cs
│   │   ├── Combat/CombatSystem.cs
│   │   └── View/AddViewSystem.cs
│   └── GameSystems.cs
├── GameController.cs
└── GameControllerBehaviour.cs
```

```csharp
// GameSystems.cs
public sealed class GameSystems : Feature
{
    public GameSystems(Contexts contexts)
    {
        Add(new InputSystem(contexts));
        Add(new ProcessInputSystem(contexts));
        Add(new MovementSystem(contexts));
        Add(new CombatSystem(contexts));
        Add(new AddViewSystem(contexts));
        Add(new GameEventSystems(contexts));
        Add(new GameCleanupSystems(contexts));
    }
}
```

```csharp
// GameControllerBehaviour.cs
public sealed class GameControllerBehaviour : MonoBehaviour
{
    Systems _systems;

    void Start()
    {
        var contexts = Contexts.sharedInstance;
#if (!ENTITAS_DISABLE_VISUAL_DEBUGGING && UNITY_EDITOR)
        var observer = new Entitas.VisualDebugging.Unity.ContextObserver(contexts.game);
        DontDestroyOnLoad(observer.gameObject);
#endif
        _systems = new GameSystems(contexts);
        _systems.Initialize();
    }

    void Update()
    {
        _systems.Execute();
        _systems.Cleanup();
    }

    void OnDestroy() => _systems.TearDown();
}
```

---

## 附录 B：术语对照（读老文章必备）

| 老叫法（≤0.35 或 1.x） | 新叫法（≥0.36 或 master/2.x） |
|-------------------------|--------------------------------|
| Pool / Pools | Context / Contexts |
| `pools.CreateSystem(...)` | `new XxxSystem(contexts)` |
| `ISetPools` | 构造函数注入 Context |
| `Entity.creationIndex`（1.x） | `Entity.Id`（master/2.x） |
| `Pools.sharedInstance` | `Contexts.sharedInstance` |
| `Entitas.CodeGenerator.*` 配置 | `Entitas.CodeGeneration.Plugins.*` / `Jenny.*` |
| 属性小驼峰（`entity.creationIndex`、`context.count`） | 属性大驼峰（`entity.Id`、`context.Count`） |

看到文章里写 `Pools`，把上面这张表替换一下就能对上现在的代码。


