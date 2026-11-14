# Entitas 代码生成（1.14.1）

完整包已放在工程内：

- `UnityProject/Assets/Plugins/EntitasOfficial/`：Entitas / DesperateDevs / Sherlog / TCPeasy / Jenny
- `UnityProject/Jenny/`：Jenny server 与 CLI
- `UnityProject/Jenny-Server.bat` / `Jenny-Auto-Import.bat`

`Tools/Entitas/EntitasGen` 只用于 Jenny 解析组件，不参与 Unity 编译。

官方源码包放在仓库外：`D:\Tools\Entitas-1.14.1-source`（63 MB，主要是 Readme 图片，不需要入库）。

## 前置

- .NET 6 SDK（只装 Runtime 会报 `No instances of MSBuild could be detected`）

## 生成步骤

在 `UnityProject/` 下执行：

```bat
dotnet Jenny\Jenny.Generator.Cli.dll doctor
dotnet Jenny\Jenny.Generator.Cli.dll server
```

另开一个终端，仍在 `UnityProject/` 下：

```bat
dotnet Jenny\Jenny.Generator.Cli.dll client gen
```

生成目标：`Assets/GameScripts/HotFix/GameLogic/EntitasDemo/Generated`。

配置在 `UnityProject/Jenny.properties`，使用相对路径，不需要改机器路径。

## 说明

- 新增组件后，把文件加入 `EntitasGen.csproj` 的 `<Compile Include=...>`，再执行 `client gen`。
- 已启用 `ContextObserverGenerator` 和 `FeatureClassGenerator`：`Contexts` 在 Play 时自动创建 `ContextObserver`；根系统用生成的 `Feature`（`EntitasDemoSystems`），不要在 MonoBehaviour 里手写 `new ContextObserver(...)` 或自定义 `Feature` 基类。
- Unity 6 下 DLL 必须放在 `Assets/Plugins` 下，否则 asmdef 不会自动引用（会报 `CS0246: Entitas`）。
