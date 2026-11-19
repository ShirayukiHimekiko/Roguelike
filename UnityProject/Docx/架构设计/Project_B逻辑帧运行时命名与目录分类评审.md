# Project B 逻辑帧运行时命名与目录分类评审

日期为 2026-11-19。评审按当时的工作区源码和项目选定的 ET10 提交 `743c635dd5b0f6f6bab549c0093382c85f3f8307` 进行。命名和目录方案已获确认，实施情况见文末清单。

## 结论

原 `Module/BattleSimulation` 的房间、帧调度、世界和录像数据现归 **`Runtime/Lockstep`**，录像文件读写归 **`Runtime/Battle`**。`BattleManager` 和四态 FSM 管理游戏进退场，`LockstepRoom` 管理这一局的演算资源。 [既有迁移记录](单机战斗流程与演算模块脚本迁移方案.md) · [BattleManager](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/BattleManager.cs) · [LockstepRoom](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs)

`Runtime/Lockstep` 包含推帧调度、单帧演算以及输入的保存和重放。以下对照关注 ET 脚本职责、挂接方式和 Project B 的对应代码。正式玩法接入另行处理。 [房间帧调度](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/RoomFrameUpdater.cs) · [世界装配](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/World/LockstepWorldSetup.cs)

## ET10 与 Project B 当前脚本的对应关系

迁移借用了 ET 的 `Lockstep` 术语。ET 的 `Model`、`Hotfix`、`HotfixView` 以及它们下面的 `Share`、`Client`、`Server` 表达数据、执行端和表现层的归属。Project B 的 `Runtime/Battle`、`Runtime/Lockstep`、`Runtime/Entitas` 同属 `GameLogic.asmdef`，其中 `Frame/`、`World/` 按源码职责组织。下表按实际调用和数据所有权对照。 [ET 包清单][et-package] · [GameLogic.asmdef](../../Assets/GameScripts/HotFix/GameLogic/GameLogic.asmdef)

ET 的三个 Updater 各有一个挂在 `Room` 上的 `IUpdate` 实体组件，配套 `*UpdaterSystem` 响应组件的更新回调。服务端组件可以仅充当更新入口，预测组件保存本地输入与身份，回放组件保存倍率。Project B 由 TEngine 的 `RunBattleState` 主动轮询当局，`LockstepRoom.StartSimulation()` 统一创建调度器，`RoomFrameUpdater.Update()` 每次根据 `IsReplay` 切到对应分支。这个差别来自两套生命周期模型和模式选择的位置。 [ET 服务端组件][et-server-model] · [ET 客户端组件][et-client-model] · [ET 回放组件][et-replay-model] · [Project B 房间启动](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L154)

| 职责 | ET10 入口 | Project B 当前入口及差别 |
| --- | --- | --- |
| 进局与挂接更新 | `LSSceneChangeHelper` 有实时、回放和重连入口。在实时入口挂入 Room、发场景事件、通知服务端就绪、等待开局消息、建世界并挂客户端更新器。 | `BattleManager.EnterBattle()` 持有当前局并启动 FSM。`InitializeBattleState` 等活动场景就绪后建世界，`StartBattleState` 建帧时钟，`RunBattleState` 负责轮询。对应的是几段流程的组合，且当前复用已有主场景。 [ET 场景切换][et-scene] · [BattleManager](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/BattleManager.cs#L68) · [初始化态](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/State/InitializeBattleState.cs) · [进行态](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/State/RunBattleState.cs) |
| 房间状态与共同步进 | `Model/Share/Room.cs` 持有数据，`Hotfix/Share/RoomSystem.cs` 负责初始化、输入投递、世界保存与步进。 | `Runtime/Lockstep/LockstepRoom.cs` 同时承担这两个文件的职责。`Tick()` 先通过 `ApplyInputs` 投递帧输入，再捕获帧前快照。实时分支记录像，回放分支先比对 hash，一致才继续执行 `World.Tick()`。 [ET Room][et-room] · [ET RoomSystem][et-room-system] · [LockstepRoom.Tick](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L194) |
| 帧到期与输入 | `FixedTimeCounter` 计算到期时刻，`FrameBuffer` 保留帧输入、快照与 hash。`LSInput` 是单人输入，`OneFrameInputs` 是整帧输入。 | `Frame/FrameClock.cs`、`FrameBuffer.cs`、`PlayerFrameInput.cs` 和 `FrameInputs.cs` 分别对应这些职责。Project B 的 `FrameBuffer.Seal()` 还合并本地待提交值，已确认历史存入环形槽，hash 随 `WorldSnapshot` 保存。 [ET 时钟][et-clock] · [ET 帧缓存][et-buffer] · [ET 输入][et-input] · [Project B 帧缓存](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/FrameBuffer.cs) |
| 服务端权威推进 | `LSServerUpdaterSystem` 等下一帧到期，补齐缺失玩家输入，推进权威帧并向客户端广播整帧输入，随后调用 `Room.Update()`。 | `RoomFrameUpdater.Update()` 的实时分支承担本地到期判断与推进，`FrameBuffer.Seal()` 封存当帧输入并沿用缺失槽的已确认值。服务端广播在当前实现中没有对应职责。 [ET 权威推进][et-server] · [Project B 实时分支](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/RoomFrameUpdater.cs#L11) · [FrameBuffer.Seal](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/FrameBuffer.cs#L41) |
| 客户端预测推进 | `LSClientUpdaterSystem` 按预测帧与权威帧的距离限制超前步数，组帧、预测推进并发送本地输入。权威帧到达后的比较和回滚走 `OneFrameInputsHandler` 与 `LSClientHelper.Rollback()`。 | 当前没有对应更新器或消息处理器。`LockstepRoom` 跟踪本地权威帧，录像定位恢复检查点后重演已有输入。 [ET 客户端预测][et-client] · [ET 权威帧处理][et-confirm] · [ET 回滚][et-client-helper] · [Project B 房间帧与定位](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L234) |
| 回放推进 | `LSReplayUpdaterSystem` 按时钟和预算读取录像里的整帧输入并推进 `Room`，通过 `ChangeReplaySpeed()` 调整时钟。`LSClientHelper.JumpReplay()` 处理跳转。 | 回放轮询在 `RoomFrameUpdater.UpdateReplay()`，倍速、定位请求、检查点恢复与 hash 分歧状态在 `LockstepRoom`。同一个 `LockstepRoom.Tick()` 仍负责执行单帧。 [ET 回放推进][et-replay-updater] · [ET 定位][et-client-helper] · [Project B 回放分支](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/RoomFrameUpdater.cs#L30) · [Project B 倍速与单帧](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L179) |
| 世界内演算与快照 | `cn.etetet.lsentity/LSWorld` 管帧号、ID 和随机状态，由内部 `LSUpdater` 按实体 ID 调用更新。`RoomSystem` 序列化或恢复 `LSWorld`。 | `World/LockstepWorld.cs` 集合了世界状态和单步入口，执行由 `LockstepWorldSetup` 装配的 Entitas `Systems.Execute()` 与 `Cleanup()`。遍历顺序有要求的系统显式调用 `GetEntitiesInOrder()`。`WorldSnapshot` 与 `SnapshotComponentCodecs` 承担本项目的快照数据及组件编解码。 [ET LSWorld][et-world] · [ET LSUpdater][et-updater] · [LockstepWorld](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/World/LockstepWorld.cs) |
| 录像、定位和文件 | `Replay` 保存整帧输入与快照，`LSClientHelper` 负责保存和跳转，`LSReplayUpdaterSystem` 负责调度重演。 | `ReplayRecording` 保存整帧输入、hash 和检查点。`LockstepRoom` 负责定位时的世界恢复，`RoomFrameUpdater` 分批追到目标帧。宿主由 `BattleManager` 选取文件，`BattleReplayFile` 负责本地 V3 读写。 [ET Replay][et-replay] · [ET 回放工具][et-client-helper] · [Project B 录像数据](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/ReplayRecording.cs) · [Project B 录像文件](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/BattleReplayFile.cs) |
| 世界内消费输入 | `RoomSystem.Update()` 先把帧输入写入单位。随后 `LSInputComponentSystem.LSUpdate()` 读取单位已有输入并修改位置、朝向。 | `LockstepWorldSetup.ApplyInputs` 对应房间投递动作，输入消费系统的对应位置是 `LockstepWorld` 的 Entitas 系统树。Demo 里可以看到这两个阶段分别装配。 [ET 投递输入][et-room-system] · [ET 消费输入][et-movement] · [Project B 的投递合同](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/World/LockstepWorldSetup.cs#L14) · [Demo 装配](../../Tools/BattleFrameworkDemo/BattleFrameworkDemo.cs#L136) |

当前正式推帧链如下。`LockstepRoom` 的 `Update()` 委托房间调度器，调度器再通过该房间的 `Tick()` 提交决定好的输入。

```text
StartUI → BattleManager → TEngine FSM / RunBattleState
    → LockstepRoom.Update → RoomFrameUpdater
        实时 → FrameBuffer.Seal → LockstepRoom.Tick
        回放 → ReplayRecording → LockstepRoom.ReplayTick → LockstepRoom.Tick
    → LockstepWorld.Tick → Entitas Systems.Execute / Cleanup
```

### 当前脚本结构的取舍

- **优先考虑独立回放调度。** 实时分支只判断到期、封帧和推进一步。回放分支还处理定位准备、分批追帧、分歧停止和恢复正常播放。若继续调整脚本结构，可先提取 `ReplayFrameUpdater`，让房间在启动时选定更新路径，并保留共同的 `LockstepRoom.Tick()`。命名可表达本地实时推进，出现真正的远端权威进程后再引入服务端和预测客户端脚本。提取时的验收点是帧前快照和 hash 校验时点、定位恢复与追帧预算、倍速锚点。 [当前帧调度](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/RoomFrameUpdater.cs) · [当前定位逻辑](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L234)
- **沿用现有的房间和进场边界。** ET 把 `Room` 与 `RoomSystem` 分开受其 Entity/System 约定驱动。Project B 的 `LockstepRoom` 持有世界和帧缓存，集中维护局部不变量。现有 `BattleManager` 与 FSM 已有进场、启动和更新入口。等出现独立场景加载、重连等新的共享进场流程时，再评估是否抽专门的流程对象。 [ET Room][et-room] · [ET RoomSystem][et-room-system] · [Project B BattleManager](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/BattleManager.cs#L68)

## 迁移前的分类问题与处理

1. **中，已确认。目录边界混入宿主 I/O。** 帧时钟、Room 与世界可以被独立 .NET Demo 链接；`BattleRecordingFile` 同时做 V3 编解码和 UniTask 文件 I/O，两个独立宿主都显式排除了它。把它搬到 `Runtime/Battle` 能让纯推进目录对应到真实的独立消费边界。`Application.persistentDataPath` 和“最后一局”的选择已经在 `BattleManager`，文件脚本继续接受传入路径即可。 [录像文件](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/BattleReplayFile.cs) · [ReplaySeek.csproj](../../Tools/BattleFrameworkDemo/ReplaySeek/ReplaySeek.csproj) · [ReplaySpeeds.csproj](../../Tools/BattleFrameworkDemo/ReplaySpeeds/ReplaySpeeds.csproj)
2. **中，已通过命名澄清。** `RoomFrameUpdater`、`LockstepRoom.Tick()`、`LockstepWorld.Tick()` 分别决定何时推进、投递帧输入与留存帧前状态、执行世界系统。房间的权威帧和世界的下一待执行帧具有不同含义。 [RoomFrameUpdater](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/RoomFrameUpdater.cs#L11) · [LockstepRoom.Tick](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L194) · [LockstepWorld.Tick](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/World/LockstepWorld.cs#L103)
3. **低，已确认。`FrameBuffer` 和录像都有帧数据，保留策略不同。** 帧缓冲既收集下一帧输入，也保存限长历史和帧前快照，适合沿用 ET 的 `FrameBuffer`。录像逐帧复制输入与 hash，并定期保存世界检查点，服务于落盘和定位。`WorldSnapshot` 是单帧状态；检查点是录像选中的一份快照。`BattleSnapshotComponents` 实际持有稳定键、组件索引和编解码器，叫 `SnapshotComponentCodecs` 更容易找到组件注册入口。 [帧缓存](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/FrameBuffer.cs) · [录像](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/ReplayRecording.cs) · [组件快照编解码](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/World/SnapshotComponentCodecs.cs)

`Module` 在项目中也包含 Utility，因此目录里没有 `GameModule` 门面本身不足以定性。我更倾向 `Runtime`，因为这组主要对象随进局、回放定位和退局创建、替换或释放，属于当局运行时。`Module/Lockstep` 仅更正功能名，仍延续先前的模块归类；`Runtime/Battle/Lockstep` 会把可被独立宿主消费的帧机制归到战斗流程下面。选同级目录能表达现有调用方向 `Battle → Lockstep`，同时保留 `Lockstep` 对项目 Entitas 类型的现实依赖。 [GameModule](../../Assets/GameScripts/HotFix/GameLogic/GameModule.cs) · [Room 恢复与释放](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L246) · [世界装配合同](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/World/LockstepWorldSetup.cs)

## 逐文件建议

路径相对于 `Assets/GameScripts/HotFix/GameLogic/`。表中的现文件名用于记录迁移前的对应关系。

| 现文件 | 建议路径 | 命名依据 |
| --- | --- | --- |
| `BattleRoom.cs` | `Runtime/Lockstep/LockstepRoom.cs` | 房间聚合世界、时钟、输入历史和重放状态。完整前缀能与未来的匹配房间或大厅区分。 |
| `BattleStartData.cs` | `Runtime/Lockstep/RoomStartData.cs` | 当前是本地玩家、参与玩家槽顺序和世界随机种子。包含本地玩家身份，仍是 Project B 的房间开局合同。 |
| `BattleUpdater.cs` | `Runtime/Lockstep/Frame/RoomFrameUpdater.cs` | 调度房间下一帧或按预算追帧。当前两种模式保留在一个类里，日后实际接入预测再评估是否拆策略。 |
| `FixedTimeCounter.cs` | `Runtime/Lockstep/Frame/FrameClock.cs` | 原名来自 ET，可以识别。`FrameClock` 更直接表达帧号到到期时刻的映射，以及倍速调整时保留时间锚点。 |
| `BattleFrameBuffer.cs` | `Runtime/Lockstep/Frame/FrameBuffer.cs` | 对齐 ET 的缓存含义。现实现同时保留待提交输入和已确认的环形帧历史。 |
| `BattleFrameInputs.cs` | `Runtime/Lockstep/Frame/FrameInputs.cs` | 一帧全体玩家输入的同步只读视图，调用方按玩家 ID 查值。 |
| `BattleInput.cs` | `Runtime/Lockstep/Frame/PlayerFrameInput.cs` | 一名玩家、一帧输入，当前载荷是定点方向和按钮，R 键、倍速等宿主快捷键另由流程处理。 |
| `BattleWorld.cs` | `Runtime/Lockstep/World/LockstepWorld.cs` | 本项目的确定性 Entitas 世界，负责单帧执行、稳定 ID、随机状态与快照。仍具体依赖 `BattleEntity` 和 `BattleContext`。 |
| `BattleWorldSetup.cs` | `Runtime/Lockstep/World/LockstepWorldSetup.cs` | 世界的装配合同，提供 Context、快照注册、初始状态、系统树和输入投递。玩法侧提供实现。 |
| `BattleWorldSnapshot.cs` | `Runtime/Lockstep/World/WorldSnapshot.cs` | 指定帧的演算前状态、帧号和 hash。 |
| `BattleSnapshotComponents.cs` | `Runtime/Lockstep/World/SnapshotComponentCodecs.cs` | 用稳定键登记组件实际字段的读写方式。 |
| `BattleRecording.cs` | `Runtime/Lockstep/ReplayRecording.cs` | 作为完整录像数据，由 Room 记录并用于回放；同文件的 `BattleRecordedFrame` 可同步改成 `RecordedFrame`。 |
| `BattleRecordingFile.cs` | `Runtime/Battle/BattleReplayFile.cs` | 当前 V3 文件的编解码和异步读写属于本地宿主接线。现阶段整个类一起搬，等存在第二个 V3 编解码调用方再评估拆分。 |

`Runtime/Battle/BattleManager.cs` 和 `State/` 有清楚的现有语义。初始化态等场景，开始态设时钟，进行态轮询，结束态退局。后续只有当状态的实际职责变动时再调整这些名字。`Runtime/Entitas/Generated/Battle` 仍按 `Jenny.properties` 管理，`Battle` 在这里表示 ECS 状态集合的名称。定点、随机和 hash 公用工具继续复用 `Module/Utility`。 [战斗状态](../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/State) · [Jenny 配置](../../Jenny.properties#L8) · [通用工具](../../Assets/GameScripts/HotFix/GameLogic/Module/Utility)

## 实施范围和验收

- [x] **核对命名和移动引用。** 已定位正式调用方、两个 `.csproj` 的旧目录引用及 Demo 对 `Room`、`Clock`、`_fsm` 等成员的反射调用。按源脚本 `.meta` 的 13 个 GUID 搜索，未在场景、Prefab、`.asset`、程序集定义和 JSON 配置中发现直接引用。迁移仍以保留原 GUID 为准。伪代码 `旧文件 → 目标文件与原 GUID；旧类型 → 新类型与调用者`。
- [x] **同步类型和调用。** 已在原文件内更名，并同步正式入口、Demo 调用和 `GameLogic.BattleReplayFile` 的反射类型名。`Room`、`Clock`、`World`、`_fsm` 等成员名沿用现状。Pipeline 实例不可发现时先完成此项。伪代码 `RunBattleState → LockstepRoom.Update → RoomFrameUpdater → LockstepRoom.Tick → LockstepWorld.Tick`。
- [x] **通过 Unity 归位文件。** Pipeline 已完成 1 个目录和 13 个脚本的移动。已逐项核对原目录和脚本 GUID，移动前后的脚本内容一致。`ReplaySeek` 和 `ReplaySpeeds` 已更新为递归链接 `Runtime/Lockstep`，本地录像 I/O 归到 `Runtime/Battle/BattleReplayFile.cs`。伪代码 `旧目录 → Runtime/Lockstep；录像 I/O → Runtime/Battle；宿主源码链接 → Runtime/Lockstep/**/*.cs`。
- [x] **核对改名涉及的源码与配置。** 正式代码、Demo 源码、工程文件和 Demo 说明已同步新命名，脚本改动限定于类型及调用引用。`battle-last-v3.replay` 文件名、V3 二进制布局、稳定组件键、50 ms 基准以及帧前快照与回放推进逻辑沿用当前实现。伪代码 `原类型与调用 → 新类型与调用；旧回放格式 → 现有 V3`。
- [ ] **按需执行运行验证。** 旧录像读取、实时和回放同路径推进、独立宿主编译与正式菜单进退场待单独验证。伪代码 `同一初始数据和输入 → 同一帧序、快照 hash、V3 数据`。

Pipeline 恢复连接后完成迁移。未主动执行编译、测试或 Play Mode 验证。

[et-package]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/package.json
[et-room]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/Room.cs
[et-buffer]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/FrameBuffer.cs
[et-clock]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/FixedTimeCounter.cs
[et-input]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/LSInput.cs
[et-replay]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/Replay.cs
[et-room-system]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Share/RoomSystem.cs
[et-server]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Server/Room/LSServerUpdaterSystem.cs
[et-client]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSClientUpdaterSystem.cs
[et-replay-updater]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSReplayUpdaterSystem.cs
[et-world]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lsentity/Scripts/Core/Share/LSWorld.cs
[et-updater]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lsentity/Scripts/Core/Share/LSUpdater.cs
[et-scene]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSSceneChangeHelper.cs
[et-movement]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Share/LSInputComponentSystem.cs
[et-client-helper]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSClientHelper.cs
[et-confirm]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/OneFrameInputsHandler.cs
[et-replay-model]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Client/LSReplayUpdater.cs
[et-client-model]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Client/LSClientUpdater.cs
[et-server-model]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Server/Room/LSServerUpdater.cs
