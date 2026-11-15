---
name: entitas-dev
description: 在 Unity/TEngine 项目中开发和排查 Entitas 1.14.1。用于 Context、Entity、Component、Matcher、Group、Collector、ReactiveSystem、Feature、事件、索引、清理、Jenny 生成与 ECS 生命周期问题。遇到 0.x Pools、2.x Entitas.Generators 或 Unity Entities/DOTS 时先辨认版本和框架。
---

# Entitas 1.14.1 开发指南

## 入口

使用 [1.14.1 标签](https://github.com/sschmid/Entitas/releases/tag/1.14.1) 和项目实际生成物核签名。1.14.1 的典型形态是 `[Game]` 或 `[Context("Game")]`、`GameMatcher.Health`、`GameEntity`、`entity.creationIndex` 与 Jenny。`Pools` 属于旧 API，`[Context(typeof(GameContext))]` 与 `Entitas.Generators` 属于新版路线。核对目标程序集引用、Context 名、Jenny provider、生成输出和根系统之后再写调用。

| 当前任务 | 阅读 |
| --- | --- |
| 建模、写组件、索引和查询，核生成 API | [1.14.1 API](references/api-1.14.1.md) |
| 选系统、接线、排查触发及重复请求 | [系统、事件与生命周期](references/systems-and-lifecycle.md) |
| 新增 Context、重新生成、排查 Jenny | [Jenny 与项目接入](references/jenny-and-integration.md) |
| 查原文或判断版本、示例是否可迁移 | [来源与阅读路径](references/sources.md) |

同时遵循 Unity 项目 `AGENTS.md`。TEngine 的热更、资源、UI 和事件桥接按 [tengine-dev](../tengine-dev/SKILL.md) 的相应参考。当前仓库已有运行时插件文件，目标程序集与生成能力按实际引用和工具配置判断。

## 从需求走到系统树

1. 确定数据由谁写、在哪个 Context 存活、谁何时读、谁清理。按世界和生命周期划分 Context。能用稳定业务 ID 关联的场景保留 ID，跨局数据由其所属模块管理。
2. 决定组件形态。匹配布尔状态用 flag，一局唯一状态用 `[Unique]`，按键频繁查找时评估索引。逐笔指令保留各自的数据、顺序和消费约定。修改组件字段、特性或归属时，先确定生成输入、输出和相关调用的迁移范围。
3. 维护手写组件后走项目已选的 Jenny 入口。由生成物提供 `AddX`、`ReplaceX`、`RemoveX`、Matcher 等 API。生成输出只放生成物，避免手改和重复生成同名类型。执行生成与项目验证遵循当前任务授权。
4. 按触发语义选系统。持续演算用 `IExecuteSystem` 和缓存的 Group，按变化刷新用 `ReactiveSystem<TEntity>`，需要逐笔处理时用独立请求实体或显式队列。数据通过领域组件或明确的服务接口交换，根系统负责装配。
5. 画出同一推进周期的生产者和消费者，再按阶段注册系统。先初始化，按调度调用 `Execute()` 与 `Cleanup()`，结束时停止生产、解除订阅、释放外部持有并销毁世界。生成事件组要在写入之后执行，清理组要等相关消费者读完。
6. 项目外部交互走已有入口。玩法组件保持帮助模拟的数据，Unity 对象和异步资源由桥接层管理。异步完成后按世界、实体及请求身份重新解析结果归属。把编译、运行、重开一局或 Profiler 检查作为可选验收项记录，据实际执行报告结果。

## 写入、消费和排障的判断

- 使用组件 API 触发监听与索引更新。直接改已挂载的字段或集合会绕过通知，也可能破坏旧 key 计算。变更前先读 API 和索引的实际实现。
- Reactive 收集的是发生过变化的实体，处理时用其当前状态。一次替换也能触发 Group 的 Removed 和 Added。需要每笔输入、旧值或稳定顺序时，建模时显式保存这些信息。
- `Destroy()` 会立即退出 Context 并移除组件。需要后续系统读死亡状态时，先标记并在消费后清理。结束时先停用 Collector，再释放外部引用，最后销毁或 Reset。
- 排查按 **输入确实被生成 → 运行时 Context 与组件正确 → Matcher 命中 → 写入走通知 → Collector 在写入前订阅 → Filter 和系统顺序正确 → 清理与生命周期合拍** 的顺序。用实际调用链定位失败点。
- 热路径先观察关联索引的 Group、集合快照、事件分发和调试开销。缓存固定查询或可复用缓冲区，确定性模拟需显式排序、控制时钟、随机和数值表示。Entitas 负责组织状态与调用顺序。

