# Jenny 1.14.1 与 TEngine 接入

## 生成流程

1. 确认要维护的 Context 归属、程序集、组件源码和已有生成根。Jenny 解析工程与 Unity 业务程序集可以是不同工程。只有在它们包含相同组件契约时，生成 API 才能对应实际运行代码。
2. 打开该工作目录使用的 `Jenny.properties`。核对 `Jenny.SearchPaths`、`Jenny.Plugins`、`Jenny.DataProviders`、`Jenny.CodeGenerators`、`Jenny.PostProcessors`、`Jenny.Plugins.ProjectPath`、`Jenny.Plugins.TargetDirectory` 和 `Entitas.CodeGeneration.Plugins.Contexts`。使用专门的生成 csproj 时，确认新组件、基类和成员类型都在解析范围。更换工作目录会影响相对路径。
3. 从官方同版发布物或项目指定工具链取得 Jenny CLI 和插件。官方路线使用 .NET CLI，先对照包的 runtimeconfig 与实际的 .NET SDK。Roslyn/MSBuild 缺 SDK 时，仅安装 runtime 仍可能无法解析项目。选好输出路径后从 `Jenny.properties` 所在目录运行：

   ```powershell
   dotnet Jenny/Jenny.Generator.Cli.dll gen
   ```

   如项目指定 server/client 模式，在一个终端启动 `dotnet Jenny/Jenny.Generator.Cli.dll server`，另一个终端调用 `dotnet Jenny/Jenny.Generator.Cli.dll client gen`。核对 host、port、服务端配置与工作目录。配置变更后确认服务端读取了新配置。`doctor` 用于诊断生成环境。执行有写入的生成前确认目标目录，不把 `doctor` 当成对生成输出的预览。
4. 对照产物确认缺失和遗留文件。Context 通常产出 `XxxAttribute`、`XxxContext`、`XxxEntity`、`XxxMatcher`、`XxxComponentsLookup`，并更新 `Contexts.cs`。组件扩展分布在 Context 的 `Components/`，事件/索引/清理输出取决于额外的 provider 和 generator。
5. 核接线，特别是字段改名、删组件、修改命名空间、改变 Context、事件、索引等跨文件变化。生成物与扩展同名 partial 类型的手写代码同程序集。其它业务系统通过明确引用消费生成类型。提交策略、是否执行生成和编译以任务授权为准。

## 当生成失败时

| 现象 | 查证顺序 |
| --- | --- |
| CLI 文件不见、无法启动 | 检查发布包中的 Jenny CLI、运行版本和工作目录。Unity Editor 插件 DLL 与命令行入口是不同产物 |
| 提示 csproj 或 MSBuild 找不到 | 检查 `ProjectPath` 与 SDK。在使用独立生成项目时核对显式 `Compile Include` 和依赖路径 |
| 新组件没进 Lookup | 查 Roslyn 是否扫描该源文件、是否解析为正确的 `IComponent`、Context 特性与配置是否一致，以及是否被 `[DontGenerate]` 或命名冲突影响 |
| 旧生成 API 导致工程编译失败 | 先识别 data provider。Roslyn 读取项目和源码符号，部分编译错误下仍能生成，声明或必要引用无法解析时应先修输入。反射/程序集来源需要可加载的编译产物 |
| 缺监听器、索引或 Cleanup 系统 | 检查相应特性、启用的 provider/generator 与生成组。读取实际生成类名、签名和注册入口 |
| 重命名后出现重复类型 | 查旧生成目录是否仍纳入编译，是否有两条入口同时输出，以及清理 postprocessor 的范围。确认输出根只存生成文件再使用清理规则 |
| 出现 `Feature` 缺失 | `FeatureClassGenerator` 生成 `Feature.cs`。手写组织树可直接继承 `Systems`；启用官方事件/清理聚合生成器时检查产物依赖的 `Feature` 基类也存在 |

从旧文章迁移时，优先用 1.14.1 的 `.NET` 命令和当前配置键。默认配置可能随打包或工程变化。整份覆盖配置可能改变生成目录、Context 与插件，先按差异处理。

## VisualDebugging

`ContextObserverGenerator` 负责 Context Inspector 接线，`FeatureClassGenerator` 负责生成系统树基类。生成的 `Feature` 在 `UNITY_EDITOR` 且未定义 `ENTITAS_DISABLE_VISUAL_DEBUGGING` 时继承 `DebugSystems`。满足相应条件的 Development Build 中可通过生成分支采样，`ENTITAS_DISABLE_DEEP_PROFILING` 控制该分支。其余环境使用普通 `Systems`。

出现 Inspector 缺节点，检查生成器、条件编译、Play Mode 的 domain reload 与已有观察器。出现 GUI 报错，先查项目中插件的 Editor 兼容代码和图标资源的导入状态。调试面板只用于观看或复现当前实例的数据。根因仍要回到系统装配、组件写入和保留者定位。Unity 版本兼容与真机性能需要对应环境的运行证据。

## TEngine 边界

- 玩法由宿主持有世界和系统树。TEngine Procedure 或业务入口负责进出和调度。UI、资源加载、外部 IO 与游戏模块通过桥接消费业务状态或事件。
- 按 [热更工作流](../../tengine-dev/references/hotfix-workflow.md) 检查实际 asmdef、插件导入平台、运行时 DLL 引用和 HybridCLR 的 AOT 泛型/裁剪。Jenny 及其生成依赖保持在工具侧。生成索引和观察器使用 `Contexts` 的 `[PostConstructor]` 接线，部署新增行为时在获授权的目标构建中关注反射入口和保留情况。
- 展示资源使用 [TEngine 资源 API](../../tengine-dev/references/resource-api.md)。视图绑定与解绑由表现侧掌管，异步返回按 [实体与请求生命周期](systems-and-lifecycle.md#退出重开与异步) 校验身份。按 [TEngine 事件规范](../../tengine-dev/references/event-system.md) 向 UI 投递值载荷。

