# Project B 游戏生命周期现状

2026-11-16 · 按当前源码记录

## 1. 启动入口和文件位置

`main.unity` 引用 `GameEntry` 和 `UIRoot` 预制体。业务入口为 `Assets/GameScripts/HotFix/GameLogic/GameApp.cs`。运行状态和宿主放在 `Module/GameAppModule/`，启动界面是 `UI/StartUI.cs` 与地址为 `StartUI` 的现有预制体。[main.unity](../../../Assets/Scenes/main.unity) · [GameEntry.cs](../../../Assets/GameScripts/GameEntry.cs) · [GameApp.cs](../../../Assets/GameScripts/HotFix/GameLogic/GameApp.cs) · [StartUI.prefab](../../../Assets/AssetRaw/UI/StartUI.prefab)

```text
GameEntry.Awake
  → 初始化更新驱动、资源、调试器与 FSM 模块，启动 Procedure
  → ProcedureLoadAssembly 切换到 ProcedureStartGame
  → 反射调用 GameApp.Entrance(object[])
  → GameApp 保存热更程序集并注册 ReleaseLogic
  → StartGameLogic 等待一次 UniTask.Yield
  → 请求异步显示 StartUI
  → GameAppManager.Instance.Start() → StartGameState → RunGameState
```

第 02 步在 `StartGameLogic` 中创建帧管理器。该入口启动应用级驱动，探针由 TEngine 调试器独立操作。[程序集加载](../../../Assets/GameScripts/Procedure/ProcedureLoadAssembly.cs) · [启动 Procedure](../../../Assets/GameScripts/Procedure/ProcedureStartGame.cs) · [第 02 步方案](02-Project_B固定帧驱动分步执行方案.md)

## 2. 五状态的当前行为

`GameAppManager : Singleton<GameAppManager>` 在 `OnInit` 创建名为 `GameApp` 的 TEngine FSM、登记五个状态、订阅应用暂停和退出。启动有 `_isStarted` 和 `_fsm.IsRunning` 两处保护。管理器经 `GameAppState.SwitchState<TState>` 发起外部切换，编辑器下该方法跳过同类型切换。[GameAppManager.cs](../../../Assets/GameScripts/HotFix/GameLogic/Module/GameAppModule/GameAppManager.cs) · [GameAppState.cs](../../../Assets/GameScripts/HotFix/GameLogic/Module/GameAppModule/State/GameAppState.cs)

| 状态 | 当前源码行为 |
| --- | --- |
| `StartGameState` | `OnEnter` 立即切入 `RunGameState`。 |
| `RunGameState` | 空状态类。 |
| `PauseGameState` | 空状态类。应用暂停回调收到 `true` 时，由管理器直接切入。收到 `false` 时，由管理器切入 `RunGameState`。 |
| `ExitGameState` | 应用退出回调由管理器切入。其 `OnEnter` 立即切入 `EndGameState`。 |
| `EndGameState` | 空状态类。 |

```text
首次 Start()             → StartGame → RunGame
应用暂停 / 恢复           → PauseGame / RunGame
应用退出                  → ExitGame → EndGame
应用销毁                  → SingletonSystem.Release → GameModule.Shutdown
                            → 移除 ReleaseLogic 销毁监听
```

销毁时 `GameAppManager.OnRelease` 取消暂停和退出监听。尚有效的 FSM 通过 `GameModule.Fsm.DestroyFsm` 回收，随后清空持有的引用。这里的 `GameModule.Shutdown` 清空业务侧的模块访问缓存。[SingletonSystem.cs](../../../Assets/GameScripts/HotFix/GameLogic/SingletonSystem/SingletonSystem.cs) · [GameModule.cs](../../../Assets/GameScripts/HotFix/GameLogic/GameModule.cs)

## 3. 启动界面与交付状态

| 范围 | 当前源码 |
| --- | --- |
| 「开始」 | 由生成绑定调用 `OnClick_StartBtn`，只输出 `[StartUI] start clicked.`。`GameAppManager.Start()` 由热更入口主动调用。 |
| 「退出」 | 由生成绑定调用 `OnClick_QuitBtn`。编辑器分支设置 `EditorApplication.isPlaying = false`，Player 分支写为 `Application.Quit()`。 |
| 局级流程 | `RunSession`、`RunId`、加载交接、局级暂停请求、结算和返回大厅仍属于后续实现目标。 |
| 启动资源 | `main.unity` 仍包含遗留的 `EntitasDemoBehaviour` 对象。Build Settings 唯一启用项仍指向仓库中缺失的 `Assets/Scenes/SampleScene.unity`。 |

[StartUI.cs](../../../Assets/GameScripts/HotFix/GameLogic/UI/StartUI.cs) · [StartUI 生成绑定](../../../Assets/GameScripts/HotFix/GameLogic/UI/Gen/StartUI_Gen.g.cs) · [现有场景列表](../../../ProjectSettings/EditorBuildSettings.asset)

本页为源码现状，第一步的行为和场景均未在 Unity 中验证。
