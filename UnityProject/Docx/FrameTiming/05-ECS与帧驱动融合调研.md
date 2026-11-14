# ECS / Entitas 与帧驱动：样本库与融合方案

采集日期：2026-11-14（Asia/Shanghai）。GitHub 星标为采集时快照。

## 0. 先给结论

1. **ECS 与帧驱动是天然搭档，但不是免费组合**：固定 tick 驱动 systems、系统顺序稳定、数据/表现分离，这三点 ECS 天生适合；但快照/回滚、事件语义、多世界隔离，Entitas 本身都不提供。
2. **Entitas 生态里几乎没有成熟的“帧同步/回滚”实现**：唯一直接相关的是 `UnityLockstep`（Entitas + 锁步 + 回滚，已归档），`Entitas-Sync-Framework` 只面向回合制/慢节奏。
3. **真正做帧同步的项目大多自研 ECS**：LittleBee 的 ECS(R)、Klotho、ME.ECS、LockstepECS 都是自带 ECS + 快照，而不是基于 Entitas。
4. **对本项目**：短期用 Entitas 做“战斗实体 + 系统顺序”是可行的；但不要指望 Entitas 直接支撑回滚。动作帧数据仍建议走 XMLib 风格的数据模型，而不是全部塞进 ECS 组件。

证据分层：GitHub 源码/文档为 A 类；CSDN 实读为 B 类；知乎标题为 C 类（正文 403）。

---

## 1. GitHub 样本（17 个）

| # | 仓库 | Star | 最后提交 | 许可证 | 类型 | 与帧驱动的关系 |
| ---: | --- | ---: | --- | --- | --- | --- |
| 1 | [sschmid/Entitas](https://github.com/sschmid/Entitas) | 7,688 | 2023-12 | MIT | C#/Unity ECS 框架 | 本项目已用 1.14.1；无内建快照/回滚 |
| 2 | [Unity-Technologies/EntityComponentSystemSamples](https://github.com/Unity-Technologies/EntityComponentSystemSamples) | 8,220 | 2026-11 | NOASSERTION | DOTS 官方示例 | `FixedStepSimulationSystemGroup` 的官方用法 |
| 3 | [genaray/Arch](https://github.com/genaray/Arch) | 1,874 | 2026-11 | Apache-2.0 | 高性能 C# ECS | 备选框架；无 Unity 深度集成 |
| 4 | [Dreaming381/Latios-Framework](https://github.com/Dreaming381/Latios-Framework) | 1,364 | 2026-11 | NOASSERTION | DOTS 框架 + Ticking | **固定 tick + 插值的完整设计**，见 §4 |
| 5 | [scellecs/morpeh](https://github.com/scellecs/morpeh) | 677 | 2026-11 | MIT | Unity ECS 框架 | 备选；轻量 |
| 6 | [proepkes/UnityLockstep](https://github.com/proepkes/UnityLockstep) | 712 | 2019-03 | MIT | Entitas + 锁步 + 回滚 | **Entitas 与帧驱动最直接样本**，已归档 |
| 7 | [dudu502/LittleBee](https://github.com/dudu502/LittleBee) | 583 | 2024-09 | 无 LICENSE | 自研 ECS(R) + 帧同步 | 快照、回放、断线重连的完整闭环 |
| 8 | [chromealex/ecs (ME.ECS)](https://github.com/chromealex/ecs) | 564 | 2023-06 | MIT | ECS + 自动回滚 + 联机 | 世界状态自动快照，RTS 向 |
| 9 | [Unity-Technologies/ECSGalaxySample](https://github.com/Unity-Technologies/ECSGalaxySample) | 301 | 2026-02 | NOASSERTION | 确定性 ECS 示例 | 定点数、确定性模拟的官方样例 |
| 10 | [JiepengTan/LockstepECS](https://github.com/JiepengTan/LockstepECS) | 279 | 2022-02 | 无 | 锁步 ECS | 高性能结构体 ECS |
| 11 | [nilpunch/massive-ecs](https://github.com/nilpunch/massive-ecs) | 224 | 2026-04 | MIT | Bitset ECS + 回滚 | 回滚型 ECS 的轻量实现 |
| 12 | [RomanZhu/Entitas-Sync-Framework](https://github.com/RomanZhu/Entitas-Sync-Framework) | 171 | 2019-06 | MIT | Entitas 网络同步 | 偏回合制/慢节奏，不是帧同步 |
| 13 | [trecs/trecs](https://github.com/trecs/trecs) | 89 | 2026-11 | MIT | ECS + 状态序列化 + 输入回放 | 快照/回放设计参考 |
| 14 | [xpTURN/Klotho](https://github.com/xpTURN/Klotho) | 85 | 2026-10 | Apache-2.0 | 确定性 ECS + 回滚 | 联机首选候选 |
| 15 | [m969/EcsNode](https://github.com/m969/EcsNode) | 64 | 2026-03 | MIT | ECS + 数据/逻辑/视图分离 + 帧同步 Demo | 预测移动、冲突回滚；有 SLG/帧同步两个 Demo |
| 16 | [dudu502/littlebee_libs](https://github.com/dudu502/littlebee_libs) | 31 | 2025-08 | MIT | Keyframe sync SDK | 可搬的轻量帧同步库 |
| 17 | [JuDelCo/CoreECS](https://github.com/JuDelCo/CoreECS) | 20 | 2025-03 | MIT | 确定性轻量 ECS | 参考“确定性 ECS”最小实现 |

> 备注：Entitas 官方仓库 2023-12 后基本停更；1.14.1 是 2022-09 的版本。项目内实际已安装 Entitas 1.14.1（DLL 位于 `Assets/Plugins/EntitasOfficial/`），这与 `UnityProject/AGENTS.md` 中“当前仓库尚未安装 Entitas”的描述冲突，需要更新规则文档。

---

## 2. CSDN 样本

采集说明：CSDN 有 WAF，前 5 篇用 iPhone UA + 静态 HTML 解析读到正文，后续批量请求被 521 拦截；最终 **10 篇完整读到正文，8 篇只拿到搜索元数据**。未读到的条目不填观点。

### 2.1 已读正文（10 篇）

| # | 标题 / 链接 | 发布 / 阅读 | 类型 | 核心观点（实读） | 价值 |
| ---: | --- | --- | --- | --- | --- |
| 1 | [【Unity学习笔记】ECS开发框架和帧同步](https://blog.csdn.net/milu_elk/article/details/140496242) | 2024-07 / 3.3k | 原创笔记 | 组件只存数据、System 只处理拥有组件的实体；作者弃用 UnityLockStepDemo 的理由是“服务端做物理、双端代码两份不一致” | 中 |
| 2 | [ECS 架构下的序列化与网络回滚](https://blog.csdn.net/rain_sxr/article/details/168345123) | 2026-10 / 3.5k | 疑似 AI | 回滚预算 <2ms；快照=Archetype Chunk memcpy；组件必须 POD、实体用世代 ID；RNG 状态必须进快照 | 高 |
| 3 | [ECS 中的确定性随机与回放](https://blog.csdn.net/2301_77785315/article/details/163219029) | 2026-07 / 4.9k | AI 分发 | 固定 System tick 顺序、禁并行/非确定容器；LCG 随机；回放=重放输入+哈希比对 | 低 |
| 4 | [ECS架构与帧同步实战：从理论到Demo](https://blog.csdn.net/wasm7browser/article/details/151913222) | 2026-03 / 404 | AI 分发 | 字典组件池 + List<ISystem> 顺序更新；帧同步只广播输入 | 低 |
| 5 | [物理模拟在 ECS 中的确定性积分步长](https://blog.csdn.net/rain_sxr/article/details/165614082) | 2026-09 / 1.7k | 疑似 AI | 固定步长累加器 + MaxSubSteps 防螺旋死亡；Previous/Current 双缓冲 + alpha 插值；禁读系统时钟 | 高 |
| 6 | [【ECS游戏架构】逻辑帧驱动性能和即时性](https://blog.csdn.net/qq_43413788/article/details/134002473) | 2023-10 / 999 | 原创 | 发送 system 排在输入 system 前会多 1 帧延迟；客户端必须固定帧率，服务器可灵活调 | 高 |
| 7 | [Unity手游实战：SLG——ECS战斗（二）Entitas](https://blog.csdn.net/haog87/article/details/107026981) | 2020-06 / 1.5k | 原创实战 | Entitas 概念链 Context/Group/Collector/Matcher；5 种 System；**System 没有内建执行顺序，完全取决于加入顺序** | 高 |
| 8 | [Unity使用ECS架构entitas实现ui响应及回放](https://blog.csdn.net/qq992817263/article/details/78155443) | 2017-10 / 1.2万 | 原创+Demo | `TickComponent.currentTick` + `TickUpdateSystem` 在 Execute 里自增；`PauseComponent` 停帧；回放从第 0 帧重跑 | 高 |
| 9 | [开始立项时候的一些帧同步总结](https://blog.csdn.net/weixin_45610260/article/details/114882840) | 2021-03 / 625 | 原创清单 | 确定性 9 条检查项（浮点、线程、遍历、物理、随机、对时…）；快照依赖“数据全在 Component” | 中高 |
| 10 | [Unity DOTS 升级，先把 System 顺序测清](https://blog.csdn.net/rain_sxr/article/details/163755188) | 2026-08 / 2.9k | 疑似 AI | 升级后“编译通过≠行为一致”；固定初始状态跑 N tick 比对快照 | 中 |

### 2.2 只拿到元数据（8 篇，正文 521）

| # | 标题 / 链接 | 发布 / 阅读 | 主题 |
| ---: | --- | --- | --- |
| 11 | [帧循环ECS、快照和回滚](https://blog.csdn.net/daming1/article/details/105487920) | 2020-04 / 2.5k | ECS 回滚/快照（最贴题，建议人工开） |
| 12 | [Unity帧同步解决方案全篇01](https://blog.csdn.net/aaa583004321/article/details/104963785) | 2020-04 / 9k | 帧同步路线 |
| 13 | [Unity ECS 之 Entitas 简单介绍](https://blog.csdn.net/u014361280/article/details/112732257) | 2021-01 / 7.8k | Entitas 入门 |
| 14 | [Entitas Wooga 学习1](https://blog.csdn.net/u012632851/article/details/75370836) | 2017-07 / 1.1万 | Entitas 源码 |
| 15 | [ECS方式实现帧同步](https://blog.csdn.net/weixin_30632883/article/details/95224794) | 2019-02 / 792 | ECS 帧同步（转载） |
| 16 | [ECS 确定性模拟与回滚系统设计](https://blog.csdn.net/rain_sxr/article/details/166130425) | 2026-09 / 599 | 回滚系统 |
| 17 | [Entitas系统架构完全指南](https://blog.csdn.net/gitblog_01038/article/details/145007895) | 2025-01 / 467 | Entitas 三 System |
| 18 | [基于 ECS 的确定性帧同步与 Go 协程](https://blog.csdn.net/iymei4986533030/article/details/163001542) | 2026-07 / 3.2k | 服务端 ECS 帧同步 |

### 2.3 CSDN 汇总

- **同质化**：10 篇里 6 篇以“守望先锋 2017 GDC”为源头；入门三件套（组件存数据、System 处理行为、组合优于继承）反复出现。
- **真正稀缺**：① Entitas × 逻辑帧结合，只有第 8 条（`TickComponent` + 回放）和第 7 条（System 顺序坑）沾边；② Entitas 下可运行的环形快照代码，0 篇；③ DOTS `FixedStepSimulationSystemGroup` 实际用法，第 5 条手写调度器却没引用官方组；④ 表现层插值边界只有零散一句。
- **AI 识别**：2026 年扎堆、`rain_sxr`/`wasm7browser`/`2301_...` 账号、模板化“工业级 C++ 代码 + LaTeX + ASCII 图”、`HashWorld(){return 0;}` 占位。注意 `weixin_45610260` 是真人笔记，不能只凭前缀判断。
- **最值得读**：第 7 条（Entitas 系统顺序）、第 8 条（TickComponent/回放）、第 2 条（快照数据布局）、第 5 条（固定步长+插值）、第 6 条（系统排序与 1 帧延迟）。

---

## 3. 知乎样本

采集说明：以下 24 条全部实测 403，正文均未读到；作者、点赞、评论未知；主题仅由标题判断，不作为正文观点引用。

| # | 标题 | 链接 | 类型 | 参考价值 |
| ---: | --- | --- | --- | --- |
| 1 | ECS白皮书——认识ECS在游戏研发中的位置 | https://zhuanlan.zhihu.com/p/560377898 | 专栏 | 高（框架定位） |
| 2 | 战斗系统架构：为什么游戏战斗适合ECS架构? | https://zhuanlan.zhihu.com/p/1962496803904656360 | 专栏 | 高（直击命题） |
| 3 | ECS 的收益、代价及与传统对象模型的差异 | https://zhuanlan.zhihu.com/p/2094726625132913235 | 专栏 | 中 |
| 4 | 一场关于ECS的问答 | https://zhuanlan.zhihu.com/p/1897317274865624099 | 专栏 | 中 |
| 5 | 游戏开发中的ECS架构实用性如何? | https://www.zhihu.com/question/455479955/answer/85702189113 | 回答 | 中 |
| 6 | 游戏开发中的ECS架构有哪些局限性? | https://www.zhihu.com/question/555506297/answer/2025829758588524337 | 回答 | 中 |
| 7 | Unity手游实战：从0开始SLG——ECS战斗（二）Entitas插件 | https://zhuanlan.zhihu.com/p/78783892 | 专栏 | 中 |
| 8 | 用Entitas开发游戏的体验是怎么样的？ | https://www.zhihu.com/question/64701202/answer/226077589 | 回答 | 中 |
| 9 | Entitas最新版的坑 | https://zhuanlan.zhihu.com/p/2001011339414487046 | 专栏 | 中 |
| 10 | 关于Unity Dots 1.0版本的学习研究(一) | https://zhuanlan.zhihu.com/p/573063785 | 专栏 | 中 |
| 11 | ECS范式框架与帧同步Demo——EcsNode | https://zhuanlan.zhihu.com/p/1888651087923373761 | 专栏 | 中高 |
| 12 | 基于ECS思想的帧同步模式下的房间战斗系统(一) | https://zhuanlan.zhihu.com/p/575429075 | 专栏 | 高 |
| 13 | 基于ECS思想的帧同步模式下的房间战斗系统(二) | https://zhuanlan.zhihu.com/p/575590294 | 专栏 | 高 |
| 14 | 仿ECS实现帧同步战斗系统的个人总结 | https://zhuanlan.zhihu.com/p/566990745 | 专栏 | 高 |
| 15 | 从零开始实现浮点数跨平台确定性（帧同步） | https://zhuanlan.zhihu.com/p/682531986 | 专栏 | 高 |
| 16 | Unity基于定点数的3D物理系统，可以用于帧同步 | https://zhuanlan.zhihu.com/p/577039641 | 专栏 | 高 |
| 17 | 为什么帧同步要创建确定性的数学和物理运算库？ | https://www.zhihu.com/question/555190273 | 问题 | 中 |
| 18 | 关于帧同步中的预表现 | https://zhuanlan.zhihu.com/p/2018463207220606735 | 专栏 | 高 |
| 19 | 游戏网络同步绿皮书 | https://zhuanlan.zhihu.com/p/565875153 | 专栏 | 中 |
| 20 | 细谈网络同步在游戏历史中的发展变化（中） | https://zhuanlan.zhihu.com/p/164686867 | 专栏 | 中 |
| 21 | 游戏技能系统漫谈 | https://zhuanlan.zhihu.com/p/567353885 | 专栏 | 高 |
| 22 | MMORPG游戏基于ECS的技能释放与Buff管理 | https://zhuanlan.zhihu.com/p/628287987 | 专栏 | 高 |
| 23 | 我的live-网络游戏同步算法 | https://zhuanlan.zhihu.com/p/65450918 | 专栏 | 中 |
| 24 | Vibe Coding 多人游戏(六)——帧同步(Lockstep) | https://zhuanlan.zhihu.com/p/2058219316596716819 | 专栏 | 低 |

知乎汇总：概念论证（1/3/4/5/6/2）与“从零搭帧同步 Demo”连载（11/12/13/14/24）最多；确定性底层（15/16/17）最硬；Entitas 以体验/踩坑为主（7/8/9）；DOTS 与逻辑帧结合几乎空白（10）。**只能当选题索引，不能当实现依据。**

---

## 4. 交叉分析：ECS 与帧驱动的 8 个结合点

### 4.1 固定 tick 驱动 systems，而不是 Update

- DOTS 的 `FixedStepSimulationSystemGroup` 只负责“追帧”，不提供插值；Latios 的 Ticking 在它之上补了 tick 编号、输入对齐和插值。
- LittleBee、UnityLockstep、Klotho 都是“tick → 执行 systems → 快照”的结构。
- **结论**：`Systems.Execute()` 必须放进 tick，而不是 `MonoBehaviour.Update()`。现有 `EntitasDemoBehaviour` 正是反例。

### 4.2 系统顺序就是确定性

- CSDN 的 ECS 文章指出：输入记录 system 必须在网络发送 system 之前，否则每帧多 1 帧延迟；服务器可以灵活调帧率，客户端必须固定。
- Entitas 的 `Feature` 是顺序执行的；`IExecuteSystem` 的添加顺序就是执行顺序。
- **结论**：把顺序固化为：输入采集 → 网络接收 → 逻辑 → 物理 → 网络发送 → 清理 → 表现。顺序变化必须视为破坏性改动。

### 4.3 数据与表现必须拆成两个 Feature

- 现有 `EntitasDemoSystems` 同时挂了 `DemoMoveSystem` 和 `DemoViewSystem`，两者都在同一 `Execute()` 里跑。
- 帧驱动要求：逻辑 systems 只在 tick 内跑；表现 systems 在渲染帧跑，并做插值。
- **结论**：拆成 `SimulationFeature` 与 `PresentationFeature`，后者只读组件、不写逻辑状态。

### 4.4 快照与回滚：Entitas 不提供

- Entitas 没有内建序列化/快照；`Entitas-Sync-Framework` 只做消息同步，不是状态回滚。
- UnityLockstep 在 Entitas 之上自己实现了实体/组件的回滚；LittleBee、Klotho、ME.ECS 都是自带 ECS + 快照。
- **结论**：如果只做单机，跳过；如果要做联机，别在 Entitas 上自研回滚，直接评估 Klotho 或 littlebee_libs。

### 4.5 多世界隔离：`Contexts.sharedInstance` 是障碍

- Entitas 的 `Contexts.sharedInstance` 是全局单例，代码生成也围绕它；而 Verified/Predicted 双链需要两套独立世界。
- **结论**：单机不需要多世界；联机时用自带世界管理的框架（Klotho/ME.ECS），不要在 Entitas 上硬造双世界。

### 4.6 事件语义：ReactiveSystem 与回滚冲突

- Entitas 的 `ReactiveSystem` 在组件变化时触发；回滚重模拟会重复触发，导致特效/伤害重复。
- Klotho 的做法：事件分 Regular（可预测、可撤销）与 Synced（验证后一次），并用高水位保证 exactly-once。
- **结论**：单机可以继续用 ReactiveSystem；一旦引入回滚，必须把事件分成“表现型”和“结算型”，后者走验证链。

### 4.7 表现插值：ECS 里存两份状态

- Latios Ticking 的第三种模式：多跑一个 tick，让渲染帧落在两个 tick 之间，再用 `previous/current` 两份组件插值；代价是丢弃并重模拟最后一个 tick。
- 对 Entitas：可以给需要插值的组件加 `Previous` 副本，或在表现层缓存上一 tick 快照。
- **结论**：插值不要改逻辑组件；在表现层做。

### 4.8 EcsNode 给出的三级演进路线

`m969/EcsNode`（MIT，64★）的 README 把“ECS + 帧同步”拆成三步，很值得借用：

1. **只预测移动**：冲突就重置回滚、重新预测（已实现）；
2. **预测碰撞事件缓存**：先做特效表现，等权威帧验证（未实现）；
3. **全量预测**：缓存状态帧快照用于回滚（未实现）。

这条路线的好处是：先只回滚“位置”这一个最小状态，验证 tick/快照/重放链路，再逐步扩大到碰撞事件和全量状态。对 TEngine 的 M0/M1 很有参考价值。

---

## 5. Entitas 专项（1.14.1）

### 5.1 现状

- 版本：`Assets/Plugins/EntitasOfficial/Entitas/CHANGELOG.md` 首行 `[1.14.1] - 2022-09-26`。
- 形态：官方 DLL（`Entitas.dll`、`Entitas.Unity.dll`、`Entitas.VisualDebugging.Unity.dll`），不是源码；不能改框架内部。
- 代码生成：Jenny（`Jenny.dll`、`Jenny.Generator.*`）。
- Demo：`EntitasDemoBehaviour` 在 `Update()` 里 `_systems.Execute(); _systems.Cleanup();`，**没有帧驱动**。

### 5.2 可用的系统接口

| 接口 | 用途 | 帧驱动里的位置 |
| --- | --- | --- |
| `IInitializeSystem` | 初始化 | 战斗开始 |
| `IExecuteSystem` | 每 tick 逻辑 | tick 内 |
| `ICleanupSystem` | 清理标记/事件 | tick 末 |
| `ITearDownSystem` | 释放 | 战斗结束 |
| `ReactiveSystem` | 组件变化响应 | 单机可用；回滚需改造 |

### 5.3 必须注意的坑

1. **Systems 没有内建执行顺序**：`Feature.Add()` 的顺序就是执行顺序，和 MonoBehaviour 的 Awake/Start 不同；必须显式固定，并按“输入 → 逻辑 → 快照 → 网络发送”排列。CSDN 第 7 条把这个称为“非常坑”。
2. **Group 遍历顺序**：不要依赖 `GetEntities()` 的天然顺序；需要确定性时按 `creationIndex` 排序，或维护稳定 id 列表。
3. **实体销毁是即时的**：一帧内销毁会影响后续 system 的查询；需要“延迟销毁”组件 + cleanup system。
4. **全局 Contexts**：`Contexts.sharedInstance.Reset()` 会清空所有上下文；多场战斗/多世界不能共用。
5. **代码生成依赖**：新增组件要跑 Jenny；DLL 形式下生成器版本与运行时版本要匹配。
6. **线程安全**：Entitas 不是为多线程模拟设计的；tick 内单线程执行，表现层另算。

### 5.4 最小帧驱动改造（参考 CSDN 第 8 条）

1. 给 `GameContext` 加 `TickComponent { long currentTick; }` 与 `PauseComponent`；
2. `TickUpdateSystem : IInitializeSystem, IExecuteSystem`，在 `Execute()` 里 `ReplaceTick(currentTick + 1)`；
3. 战斗逻辑 system 只在 `TickUpdateSystem` 之后执行；
4. `MonoBehaviour` 不再在 `Update()` 里直接 `Execute()`，而是由 `FrameScheduler` 在逻辑帧调用 `SimulationFeature.Execute()`；
5. 回放先只记录“第 N 帧的输入”，重放时从第 0 帧重跑——这是 demo 级方案，不是快照回滚。

---

## 6. 三种架构方案

| 方案 | 结构 | 优点 | 缺点 | 适用 |
| --- | --- | --- | --- | --- |
| A. 纯 OOP + 帧时钟 | FrameClock + 每单位 ActionMachine（XMLib 风格） | 简单、动作数据直观、调试容易 | 大量单位时遍历/查询成本高 | 单机 ACT、单位数 < 100 |
| B. Entitas ECS + 帧时钟 | FrameClock + SimulationFeature / PresentationFeature | 数据驱动、系统顺序清晰、易扩展 | 无快照/回滚；全局 Contexts；Group 顺序坑 | 单机、多单位、战斗逻辑复杂 |
| C. 混合 | ECS 管实体/位置/状态；每单位 ActionMachine 管动作帧 | 兼顾数据驱动与动作表达 | 两套模型边界要定清楚 | 推荐 |

**推荐 C**：ECS 只负责“实体、位置、状态、buff、空间查询”，动作帧仍由 ActionMachine（纯 C# 对象，作为组件数据）推进；命中检测在物理 PostStep 用 ECS 查询完成。

---

## 7. TEngine 落地方案

### 7.1 模块

```
GameModule.Frame (新)
  ├─ FrameClock        整数 tick、60Hz、追帧上限、暂停
  ├─ FrameScheduler    Input → Logic → Physics → Late
  ├─ FrameTimer        Once / Repeat / Wait（UniTask）
  └─ BattleWorld       每场战斗一个 Entitas Contexts + Feature
```

### 7.2 Entitas 改造

1. `EntitasDemoBehaviour.Update()` → 由 `FrameScheduler` 的 Logic 阶段调用 `SimulationFeature.Execute()`；
2. `SimulationFeature`：输入、移动、动作、命中、伤害、清理；
3. `PresentationFeature`：在渲染帧读组件、插值、更新 GameObject；
4. `DemoViewSystem` 从 `SimulationFeature` 移出；
5. 实体销毁改延迟销毁；
6. 需要确定性的遍历按 `creationIndex` 排序。

### 7.3 动作机与 ECS 的边界

- ActionMachine 作为 `UnitActionComponent` 的字段（纯 C# 对象），由 `ActionTickSystem` 推进；
- 当前帧的 attack/body ranges 写回 ECS 组件（`HitboxComponent`），由物理/查询 system 消费；
- 表现层只读 `animName + normalizedTime`，不反向写逻辑。

---

## 8. 风险与待确认

1. **Entitas 1.14.1 老旧**：2022 年后停更，Unity 版本升级有兼容风险；DLL 形式无法热修。
2. **Group 顺序不确定性**：若用于联机，必须先验证遍历顺序并排序。
3. **全局 Contexts**：多场战斗/多世界需要自建 Contexts，代码生成是否支持待验证。
4. **回滚成本**：Entitas 无快照；自研回滚的工作量可能超过直接换 Klotho。
5. **文档冲突**：`AGENTS.md` 说未安装 Entitas，实际已安装 1.14.1，需要更新规则。
6. **动作机与 ECS 的职责边界**：如果全部塞进 ECS，动作帧编辑/调试会变难；建议保留 ActionMachine 作为独立对象。

---

## 9. 结论

- ECS 适合做“帧驱动的执行层”，不适合单独承担“动作帧数据 + 回滚”。
- Entitas 可以作为单机战斗的 ECS 底座，但必须拆 Simulation/Presentation、固定系统顺序、处理 Group 顺序与实体销毁。
- 联机不要基于 Entitas 自研回滚；优先评估 Klotho。
- 推荐混合架构：FrameClock + ECS 实体/状态 + ActionMachine 动作帧 + 独立表现层。
