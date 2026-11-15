# Entitas 1.14.1 来源与阅读路径

版本基线为 GitHub 标签 `1.14.1`，提交 `08ee51f6010035e02c65102c35ac342d1427364c`。标签源码和生成模板用于判定 API 与行为。Wiki、示例工程和 Issue 用来理解用法、选择设计及定位故障。文档中的示例按源码推演，项目兼容性需要对应环境的运行证据。

| 问题 | 优先读 | 可以确认 |
| --- | --- | --- |
| Runtime 版本和工具切换 | [1.14.1 release](https://github.com/sschmid/Entitas/releases/tag/1.14.1) · [1.14.0 迁移说明](https://github.com/sschmid/Entitas/releases/tag/1.14.0) · [作者说明](https://github.com/sschmid/Entitas/discussions/1008) | 1.14 系列的 .NET CLI、Roslyn 和发布包约定 |
| 池化、销毁、Reset、按索引通知 | [Context.cs](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas/src/Context/Context.cs) · [Entity.cs](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas/src/Entity/Entity.cs) | 活跃、已销毁仍保留与回池的区别 |
| 替换通知、触发归并、筛选时点 | [Group.cs](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas/src/Group/Group.cs) · [Collector.cs](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas/src/Collector/Collector.cs) · [ReactiveSystem.cs](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas/src/Systems/ReactiveSystem.cs) | Replace 发出的通知、去重与 Retain/Release |
| 按键查询与生成 | [运行时索引](https://github.com/sschmid/Entitas/tree/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas/src/EntityIndex) · [EntityIndexGenerator.cs](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas.CodeGeneration.Plugins/src/EntityIndex/CodeGenerators/EntityIndexGenerator.cs) | 索引是否为唯一、键更新、构造时注册 |
| 普通组件、Unique 和命名 | [组件生成器](https://github.com/sschmid/Entitas/tree/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas.CodeGeneration.Plugins/src/Component/CodeGenerators) · [ContextsGenerator.cs](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas.CodeGeneration.Plugins/src/Context/CodeGenerators/ContextsGenerator.cs) | 生成的实体与 Context 方法、flag 与数据单例的区别 |
| 生成事件和清理 | [事件生成器](https://github.com/sschmid/Entitas/tree/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas.CodeGeneration.Plugins/src/Events/CodeGenerators) · [CleanupSystemGenerator.cs](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas.Roslyn.CodeGeneration.Plugins/src/Cleanup/CodeGenerators/CleanupSystemGenerator.cs) · [生成示例](https://github.com/sschmid/Entitas/tree/08ee51f6010035e02c65102c35ac342d1427364c/Tests/TestFixtures/Generated) | Self/Any 的监听位置、Removed 载荷、显式 Cleanup |
| Jenny 与 Editor 输出 | [官方 fixture 配置](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/Tests/TestFixtures/Jenny.properties) · [Roslyn 组件 providers](https://github.com/sschmid/Entitas/tree/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas.Roslyn.CodeGeneration.Plugins/src/Component/DataProviders) · [FeatureClassGenerator.cs](https://github.com/sschmid/Entitas/blob/08ee51f6010035e02c65102c35ac342d1427364c/src/Entitas.VisualDebugging.CodeGeneration.Plugins/src/FeatureClassGenerator.cs) | 解析输入、可选生成器及 Feature 走不同分支的条件 |

## 作者示例里可迁移的做法

[Match-One 固定提交](https://github.com/sschmid/Match-One/tree/7d490c6d236c478f62b83a579724d730d2c9b88f) 的 `GameController` 装配根系统并依次调用 Execute、Cleanup。`GameSystems` 先执行输入和棋盘演算，再绑定表现、派发生成事件，生成 Cleanup 在清理阶段运行。`PositionComponent` 用 Self 将位置更新发给绑定对象。迁移这条消费链时保留宿主、生产者、监听者和清理的依赖，按当前项目决定 Context、推进周期和世界退出机制。示例的 `Jenny.properties` 是另一套工程配置。

[官方 Wiki 的 Systems](https://github.com/sschmid/Entitas/wiki/Systems) 和 [FAQ](https://github.com/sschmid/Entitas/wiki/FAQ) 可提供设计思路和诊断线索。Group 成本以标签源码和目标场景为准，不能直接将 Wiki 的全组估算套用到 1.14.1。`Context` 用组件索引查相关组。安装问题可查 [1.14.1 社区实操记录](https://github.com/sschmid/Entitas/issues/1055)，其中的插件安装和编辑器现象需结合具体工具包与 Unity 版本。

