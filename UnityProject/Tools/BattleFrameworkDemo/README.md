# 战斗框架验收 Demo

此目录存放可单独移除的验收代码。正式战斗框架不引用这里的代码。

从 `UnityProject` 根目录运行，独立验收需要 .NET 8 SDK 或支持 `net8.0` 的更高版本：

```powershell
pwsh -NoProfile -File ./Tools/BattleFrameworkDemo/FixedMathComparison/Run.ps1
dotnet run --project ./Tools/BattleFrameworkDemo/ReplaySpeeds --artifacts-path ./Temp/BattleReplaySpeeds-build
dotnet run --project ./Tools/BattleFrameworkDemo/ReplaySeek --artifacts-path ./Temp/BattleReplaySeek-build
```

第一条命令把固定提交的 TrueSync 参考文件保存到 `Temp` 并核对 SHA-256，再和当前项目 `Module/Utility` 的源文件一起编译；发现 `RawValue` 差异时退出码为 `1`。

第二、第三条命令直接编译 `Runtime/Lockstep` 的演算源码，以项目内 Entitas DLL 和独立 `Room` 验收倍率、分批定位、世界替换版本、恢复播放、帧前分歧、帧末自然结束和终局分歧。文件 I/O 与 Unity 场景由 Unity 宿主处理。

Editor 内验收时，先确认 Pipeline 已连接并在 `main` 场景进入 Play Mode。然后从 `UnityProject` 根目录执行：

```powershell
unity command --project-path . --timeout 40 run_script --file Tools/BattleFrameworkDemo/ReplaySpeedDemo.cs --entry ReplaySpeedDemo.Run --timeout_ms 35000
```

`BattleFrameworkDemo.cs` 中的 `RunEmptyRoom`、`Run` 和 `RunWorldRebuild` 使用独立 TEngine FSM。使用 `RunReplayFileCompatibility` 可验收 V3 固定样本、V4 终局指纹往返及坏档拒绝，文件路径在临时目录。使用 `RunManagerMenu` 可从刚打开的菜单验证正式开始按钮、当前局、首帧与释放重开。上游下载及编译产物位于 `Temp`，Demo 可独立移除。
