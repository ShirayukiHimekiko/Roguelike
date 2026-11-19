# Entitas 与嵌入包 Unity 警告修复方案

状态：按已确认方案完成文件修改，未运行 Unity 验收。本次仅处理已报告的 4 条 CS0618 和 2 条嵌入包目录命名警告。

## 修改目标（按执行顺序）

- [x] **迁移 Entitas Editor 宏定义 API。** 已在 `ScriptingDefineSymbols.cs` 的 `Add` 和 `Remove` 中把 4 处旧调用替换为 `NamedBuildTarget` 版 API，保留公开签名、平台组枚举和原有宏增删规则。未升级 Entitas 或屏蔽告警。

  ```text
  target = NamedBuildTarget.FromBuildTargetGroup(buildTargetGroup)
  symbols = PlayerSettings.GetScriptingDefineSymbols(target)
  PlayerSettings.SetScriptingDefineSymbols(target, 按原规则增删指定宏(symbols))
  ```

- [x] **对齐两个嵌入包的目录名。** 已将 `Packages/UniTask` 整体改名为 `Packages/com.cysharp.unitask`，将 `Packages/YooAsset` 整体改名为 `Packages/com.tuyoogame.yooasset`，保留包内容、`.meta`、包 ID 和现有版本（UniTask `2.5.10`、YooAsset `2.3.17`）。未改 `manifest.json` 或手改 `packages-lock.json`；旧物理路径留待 Unity Package Manager 下次解析时更新，现有 Pipeline 路径改动未触碰。

  ```text
  对每个包：确认源与目标均在 Packages 内、目标不存在
  将现有目录整体改名为 package.json 中的 name
  ```

## 验收标准

Unity 完成包解析和脚本编译后，本次指定的 6 条警告不再出现，两个包仍以原版本和 `embedded` 来源解析，相关宏定义读写范围不变。不主动打开 Unity、刷新、编译或运行测试；如需在编辑器中验收，另行确认。
