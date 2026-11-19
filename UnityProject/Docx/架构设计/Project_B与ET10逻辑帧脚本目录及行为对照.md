# Project B 与 ET10 逻辑帧脚本、目录及行为对照

本文记录脚本结构改造前的对照基线。当前目录、实现与验收结果见 [按 ET10 改造并补齐单机逻辑帧框架执行方案](Project_B按ET10改造并补齐单机逻辑帧框架执行方案.md)。

2026-11-19。Project B 以当前工作区源码为准，包含 `5abd4ad` 之后的本地目录迁移。ET10 固定为项目选定的 `743c635dd5b0f6f6bab549c0093382c85f3f8307`。本次核对房间、进退场、帧调度、世界、快照、录像与 ET 示例中的联机机制。`LSInputComponentSystem` 仅对照脚本层次和调用位置。 [ET10 固定提交][et-commit] · [此前命名评审](Project_B逻辑帧运行时命名与目录分类评审.md)

## 一、哪些已经对上

- **逻辑一致。** 双方基础帧长为 50 ms，也就是 20 逻辑帧每秒。帧到期时刻使用同样的锚点公式，修改间隔时保留切换帧的到期时刻。实时权威路径每次轮询最多推进一帧，缺少新值时沿用已有的输入值。实时步进的关键顺序都是投递帧输入、保存帧前状态、记录权威输入、执行世界。双方都每 1,200 帧保存一个录像检查点。 [ET 常量][et-const] · [ET 时钟][et-clock] · [ET 服务端更新][et-server] · [ET 单帧入口][et-room-system] · [Project B 时钟][pb-clock] · [Project B 单帧入口][pb-tick] · [Project B 录像][pb-record]
- **部分对上。** Room 管世界、时钟和帧历史的边界一致，脚本拆分方式不同。Project B 把 ET 的 `Room` 与 `RoomSystem` 合进 `LockstepRoom`，实时和回放都挂在同一个 `RoomFrameUpdater` 下。世界内调度、回放开局、检查点恢复后的下一帧、hash 停步和文件格式也有实质差异。 [ET Room][et-room] · [ET 回放更新][et-replay-update] · [Project B 调度][pb-updater] · [Project B 定位][pb-seek] · [Project B 录像文件][pb-file]
- **当前缺少的 ET 对应内容。** 独立的回放更新脚本、客户端预测更新器、服务端权威广播与进场握手、客户端权威帧确认与回滚、联机时钟校正和跨端 hash 对账、重连入口。独立回放脚本是结构差异，其余主要来自 ET 示例含联机运行端，Project B 当前走本地实时和本地录像。 [ET 客户端更新][et-client] · [ET 权威输入处理][et-confirm] · [ET 服务端进场][et-ready] · [ET 时钟校正][et-adjust] · [ET 场景与重连入口][et-scene]

## 二、当前目录和脚本对照

Project B 路径相对于 `Assets/GameScripts/HotFix/GameLogic/`。ET 的 `Model`、`Hotfix`、`HotfixView` 路径相对于 `Packages/cn.etetet.lockstep/Scripts/`。ET 同时按执行端划分 `Share`、`Client`、`Server`。本项目的 `Runtime/Battle`、`Runtime/Lockstep` 和 `Runtime/Entitas` 都由同一个 `GameLogic.asmdef` 编译。 [ET 包清单][et-package] · [GameLogic.asmdef](../../Assets/GameScripts/HotFix/GameLogic/GameLogic.asmdef)

| Project B 当前路径 | ET 里最接近的脚本 | 结构判断及具体职责 |
| --- | --- | --- |
| `Runtime/Battle/BattleManager.cs`、`State/InitializeBattleState.cs`、`State/StartBattleState.cs`、`State/RunBattleState.cs` | `Hotfix/Client/LSSceneChangeHelper.cs` 与 ET 的实体更新机制 | **部分对应。** Project B 由 Manager 持有当局，三态负责等待当前场景、建世界、启时钟及轮询。ET 在场景根挂 Room，按实时或回放挂 Updater 组件，并发布进场事件。 [Project B 管理器][pb-manager] · [ET 进场][et-scene] |
| `Runtime/Battle/State/EndBattleState.cs`、`BattleManagerState.cs` | ET 的场景或房间释放路径 | **宿主实现不同。** `EndBattleState` 把退出交回 Manager，公共基类定义 TEngine FSM 类型。ET 的场景切换通过移除旧 Room 组件替换当局。 [Project B 状态目录][pb-state] · [ET 场景切换][et-scene] |
| `Runtime/Battle/BattleReplayFile.cs` | `Hotfix/Client/LSClientHelper.cs` 的 `SaveReplay` 和 ET 的 `Replay` 序列化 | **职责相近，文件格式不同。** Project B 把同步编码与异步文件读写收在一个脚本。Manager 决定本地文件路径。ET 的保存入口以 MemoryPack 编码 `Replay`。 [Project B 录像文件][pb-file] · [ET 回放工具][et-helper] |
| `Runtime/Lockstep/LockstepRoom.cs` | `Model/Share/Room.cs` 与 `Hotfix/Share/RoomSystem.cs` | **两文件对应一文件。** Project B 持有房间状态、处理建世界、执行共同帧、定位和释放。ET 的房间实体持有状态，配套扩展方法完成初始化、步进、快照和记录。 [Project B 房间][pb-room] · [ET Room][et-room] · [ET RoomSystem][et-room-system] |
| `Runtime/Lockstep/RoomStartData.cs` | `RoomSystem.Init()` 接收的 `LockStepUnitInfo`、开战时间与起始帧 | **部分对应。** Project B 开局合同携带本地玩家 ID、参与玩家的固定槽顺序和随机种子，时钟稍后从本地采样。ET 的初始化输入还承载示例单位初值、服务端开战时间及起始帧。 [Project B 开局数据][pb-start] · [ET 开局参数][et-room-system] · [ET 开战消息][et-ready] |
| `Runtime/Lockstep/Frame/RoomFrameUpdater.cs` | `Hotfix/Server/Room/LSServerUpdaterSystem.cs`、`Hotfix/Client/LSReplayUpdaterSystem.cs`、`LSClientUpdaterSystem.cs` | **实时与回放部分合并，预测缺少对应脚本。** Project B 的实时分支相当于服务端更新器的本地推进部分，回放分支接管录像时钟和分批重演。ET 按模式挂不同 Updater 组件。 [Project B 调度][pb-updater] · [ET 服务端调度][et-server] · [ET 回放调度][et-replay-update] · [ET 预测调度][et-client] |
| `Runtime/Lockstep/Frame/FrameClock.cs` | `Model/Share/FixedTimeCounter.cs` 与 `LSConstValue.cs` | **时钟公式一致。** Project B 用本进程 `Stopwatch` 采样整数毫秒，ET 调度入口使用 `TimeInfo.ServerNow()`。 [Project B 时钟][pb-clock] · [ET 时钟][et-clock] · [ET 常量][et-const] |
| `Runtime/Lockstep/Frame/FrameBuffer.cs` | `Model/Share/FrameBuffer.cs`，加上服务端更新器的一部分补帧职责 | **保存的数据概念一致。** 双方有输入、快照和 hash。Project B 还在此收集待提交值并封帧，以精确帧号识别仍保留的环形槽。ET 的缓冲还服务于可写的预测帧和网络确认帧。 [Project B 帧缓存][pb-buffer] · [ET 帧缓存][et-buffer] · [ET 权威输入处理][et-confirm] |
| `Runtime/Lockstep/Frame/PlayerFrameInput.cs`、`FrameInputs.cs` | `LSInput`、`OneFrameInputs` | **数据层次一致。** 两者都区分单人单帧与全体玩家整帧输入。Project B 使用固定槽和只读视图，ET 的整帧输入按玩家 ID 存放并可通过消息流转。 [Project B 单人输入][pb-player-input] · [Project B 整帧输入][pb-frame-inputs] · [ET 输入][et-input] · [ET 整帧消息入口][et-confirm] |
| `Runtime/Lockstep/World/LockstepWorld.cs`、`Runtime/Entitas/Generated/Battle/*` | `cn.etetet.lsentity` 的 `LSWorld`、`LSEntity`、`LSUpdater` | **世界职责对应，执行模型不同。** 两侧有世界帧、ID、随机和单步更新。ET 的 `LSUpdater` 位于世界内部，按稳定实体 ID 更新。Project B 跑 Entitas 系统树，系统有顺序需求时显式调用 `GetEntitiesInOrder()`。生成目录由 Jenny 管理。 [Project B 世界][pb-world] · [Project B Jenny](../../Jenny.properties#L8) · [ET 世界][et-world] · [ET 世界内调度][et-world-update] |
| `Runtime/Lockstep/World/LockstepWorldSetup.cs` | `RoomSystem.Init()`、`RoomSystem.Update()` 与 ET 的实体系统注册 | **Project B 装配接口。** 把创建 Context、组件编解码、初始化、系统装配与输入投递作为回调接入。ET 的 `LSInputComponentSystem` 在世界内消费输入，其对应位置是 Entitas 系统树。`ApplyInputs` 对应上一层的输入投递。 [Project B 装配][pb-setup] · [ET 整帧投递][et-room-system] · [ET 世界内消费][et-input-system] |
| `Runtime/Lockstep/World/WorldSnapshot.cs`、`SnapshotComponentCodecs.cs` | `RoomSystem.SaveLSWorld()` 与 `GetLSWorld()`、ET 实体的序列化契约 | **快照能力对应，编码不同。** Project B 以世界 ID、组件稳定键和显式字段编码恢复新 Context。ET 通过 MemoryPack 序列化并反序列化 `LSWorld`。 [Project B 世界快照][pb-world] · [Project B 组件编解码][pb-codecs] · [ET 世界序列化][et-room-system] |
| `Runtime/Lockstep/ReplayRecording.cs` | `Model/Share/Replay.cs`，由 `RoomSystem.Record()` 填充 | **录像职责对应。** 双方都保存开局相关数据、逐帧输入与定期快照。Project B 额外随每帧保存帧前世界 hash。 [Project B 录像][pb-record] · [ET 录像模型][et-replay] · [ET 记录入口][et-room-system] |

## 三、实际逻辑是否对得上

| 环节 | ET10 行为 | Project B 当前行为 | 判断 |
| --- | --- | --- | --- |
| 开局和第 0 帧 | 实时客户端等场景事件和开战消息。服务端在玩家就绪后给 `StartTime`，`Room.Init()` 默认房间权威帧和预测帧为 `-1`、世界帧为 `0`。 | Manager 用 TEngine FSM 等当前活动场景就绪，然后建世界，开跑前用本地单调时钟取锚点。房间权威帧从 `-1` 开始，初始世界待执行帧为 `0`。 | **首帧编号一致，开战同步部分缺失。** ET 的 `MatchCount = 1` 仍走客户端和服务端消息。 [ET 常量][et-const] · [ET 开局握手][et-ready] · [ET Room 初始化][et-room-system] · [Project B 开始态][pb-start-state] |
| 实时到期和封帧 | 服务端取 `AuthorityFrame + 1`，未到期直接返回。该帧缺人时先找上一帧该玩家的输入，否则使用默认值，推进权威帧并广播。 | 同样取 `AuthorityFrame + 1` 并按到期时刻门控。本地输入进入下一帧的待提交槽，同槽取最后一次提交，缺值沿用最近确认输入，初值默认。 | **本地推进原则一致，输入归帧和传播不同。** ET 按消息帧号收集各玩家输入，本项目入口提交给下一帧。 [ET 服务端更新][et-server] · [Project B 调度][pb-updater] · [Project B 帧缓存][pb-buffer] |
| 确认帧的执行次序 | `Room.Update()` 将整帧输入写入单位，非回放时保存 `LSWorld` 并尝试记录该帧，然后调用 `LSWorld.Update()`。世界推进后 `Frame` 加一。 | `LockstepRoom.Tick()` 调用 `ApplyInputs`，捕获当前帧快照，实时记到录像并写帧历史，再调用 `LockstepWorld.Tick()` 执行和清理系统，最后 `Frame` 加一。 | **实时帧的关键顺序一致。** 两边快照都在输入投递之后、当帧规则执行之前。快照字节布局和世界内调度独立。 [ET RoomSystem][et-room-system] · [ET LSWorld][et-world] · [Project B 单帧][pb-tick] · [Project B 世界][pb-world] |
| 帧历史和录像检查点 | `FrameBuffer` 按帧号映射环形槽，默认按 60 秒容量设置。录像记录权威整帧输入，每 1,200 帧保存一次快照。 | 帧历史也默认按 60 秒容量设置，每个槽额外记录实际帧号。录像为每帧留输入与 hash，每 1,200 帧附快照，包括第 0 帧。 | **窗口容量和检查点间隔一致。** 有效槽判断、预测历史与录像记录结构有差异。 [ET FrameBuffer][et-buffer] · [ET 常量][et-const] · [ET 录像写入][et-room-system] · [Project B 帧缓存][pb-buffer] · [Project B 录像][pb-record] |
| 普通回放的开局与追帧 | `SceneChangeToReplay()` 用 `Replay.UnitInfos` 初始化世界和时钟，表现准备后挂回放更新器。更新器按到期时间用已录输入连续推进，源码在单帧完成后检查本轮是否已超过约 5 ms。 | 回放建世界时读第 0 帧检查点，准备后启动时钟。回放分支同样按到期时间消费录像输入，并在单帧完成后检查约 5 ms 的预算。 | **正常播放调度原则一致。** 世界的开局来源、时钟锚定阶段和每帧校验存在差异。两边的时间检查都在单帧完成后，单帧本身可以超过预算。 [ET 回放进场][et-scene] · [ET 回放更新][et-replay-update] · [Project B 建世界][pb-init-world] · [Project B 追帧][pb-replay-update] |
| 回放倍速 | 在 1、2、4、8 倍之间循环，用 `50 / speed` 得到整数毫秒间隔，在当前权威帧锚定。 | 支持相同四档，使用相同的整数除法。Room 的接口可直接设指定倍率，切换帧使用 `max(0, AuthorityFrame)`。 | **基础数学一致。** 四档间隔都是 50、25、12、6 ms。入口和首帧前锚点处理不同。 [ET 倍速][et-replay-update] · [Project B 倍速][pb-speed] |
| 回放定位与检查点边界 | 跨区间或向后跳时，`JumpReplay()` 恢复目标区间的快照，将 `AuthorityFrame` 设为该区间首帧 `F`，并把时钟重设到请求目标。回放更新器用 `AuthorityFrame + 1` 取下一份输入。 | 向后跳、跨区间或从分歧恢复时重建世界，将 `AuthorityFrame` 设为 `F - 1`。追帧会先消费 `F` 的输入，并按预算追到目标，完成后再锚定时钟。同区间健康正跳复用当前世界。 | **机制相近，帧边界和追帧时点不同。** 例如恢复检查点 `F = 1200` 后，ET 这条源码路径下一次取录像输入 `1201`，Project B 先取 `1200`。这是直接读到的源码差异，运行影响待实测。 [ET JumpReplay][et-helper] · [ET 录像下一帧][et-replay-update] · [Project B 定位][pb-seek] · [Project B 追帧][pb-replay-update] |
| 世界 hash 与回放分歧 | ET 非回放推进时保存帧前快照并计算 hash。联机客户端提交已确认帧 hash，服务端发现不一致时返回用于诊断的世界数据。普通回放分支跳过 `SaveLSWorld()`，继续执行世界。 | 实时录像保存帧前 hash。回放先投递输入并捕获快照，和录像中的同帧 hash 比较。若不一致，记下分歧帧并撤销待定位目标，该帧的世界系统不会执行。 | **检测用途和失败行为不同。** ET 这条示例链路做跨端诊断。Project B 在本地播放时执行逐帧校验和停步。 [ET 房间快照][et-room-system] · [ET 服务端 hash 对账][et-hash] · [ET 客户端分歧诊断][et-hash-fail] · [Project B 单帧][pb-tick] |
| 录像文件与恢复 | `Replay` 以 MemoryPack 保存单位信息、整帧输入和快照。`GetLSWorld()` 反序列化世界。 | `BattleReplayFile` 读写项目自己的 V3 文件，包含版本、帧输入、hash、检查点和文件校验。`LockstepWorld` 用稳定键恢复组件并重新装配系统。 | **能力对应，文件与快照字节不可互读。** [ET 录像模型][et-replay] · [ET SaveReplay][et-helper] · [Project B V3][pb-file] · [Project B 恢复][pb-world] |

## 四、欠缺项及其所属范围

| 欠缺项 | ET 入口 | 对当前 Project B 的意义 |
| --- | --- | --- |
| 实时与回放更新器各自独立 | `LSServerUpdaterSystem`、`LSReplayUpdaterSystem`，各自有 Room 组件与更新回调 | **唯一直接影响本次脚本分类的缺口。** 当前回放行为已在 `RoomFrameUpdater` 和 `LockstepRoom` 中。若继续贴近 ET 的职责边界，可让开局选定 `LocalFrameUpdater` 或 `ReplayFrameUpdater`，保留共同的 `LockstepRoom.Tick()`。 [ET 服务端更新][et-server] · [ET 回放更新][et-replay-update] · [Project B 当前分支][pb-updater] |
| 独立权威端、玩家就绪和广播 | `C2Room_ChangeSceneFinishHandler`、`LSServerUpdaterSystem` | **联机缺口。** 本地权威推进已覆盖到期和封帧。要对齐 ET 联机路径，还需要按目标帧收远端输入、发开战参数、广播权威整帧。 [ET 开战握手][et-ready] · [ET 权威更新][et-server] |
| 客户端预测、确认和回滚重演 | `LSClientUpdaterSystem`、`OneFrameInputsHandler`、`LSClientHelper.Rollback()` | **联机缺口。** 需要独立维护预测帧和权威帧，确认后用权威输入纠偏，再重演预测区间。当前房间的录像定位属于另一条调用链。 [ET 预测][et-client] · [ET 确认][et-confirm] · [ET 回滚][et-helper] |
| 联机时钟校正和跨端状态对账 | `Room2C_AdjustUpdateTimeHandler`、`C2Room_CheckHashHandler`、`Room2C_CheckHashFailHandler` | **联机缺口。** 当前能调回放时钟并比较本地录像 hash。ET 另有服务器时间差校正、客户端发送帧 hash 与差异快照诊断。 [ET 时钟校正][et-adjust] · [ET hash 对账][et-hash] · [ET 分歧诊断][et-hash-fail] |
| 远端场景进场与重连 | `LSSceneChangeHelper` 的实时及重连入口 | **联机宿主缺口。** 本地进退场已有 Manager 和 FSM。完整对齐 ET 需要远端开战消息与重连建房流程。 [ET 场景与重连][et-scene] · [Project B 进场][pb-manager] |

`Room` 与 `RoomSystem` 的两文件分法，以及 `Model/Hotfix/HotfixView` 的包结构，由 ET 的实体与热更模型驱动。Project B 现有的 `LockstepRoom`、宿主 FSM 和 Entitas 世界已经各有明确所有者。按本次范围，进一步归类的收益集中在**实时和回放更新器的模式边界**。若目标提高到 ET 联机示例的完整行为，优先补齐上表中的网络收发、预测和纠偏链路。 [ET Room][et-room] · [ET RoomSystem][et-room-system] · [Project B 房间][pb-room]

本次为固定版本的源码对照，未修改 C#、目录或配置，未运行 Unity、编译或测试。关于帧号、时钟和顺序的判断来自源码，跨项目逐帧一致性与行为回归尚未实测。

[pb-manager]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/BattleManager.cs#L68
[pb-state]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/State
[pb-start-state]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/State/StartBattleState.cs#L13
[pb-file]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/BattleReplayFile.cs
[pb-room]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs
[pb-init-world]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L148
[pb-speed]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L179
[pb-tick]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L194
[pb-seek]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L234
[pb-start]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/RoomStartData.cs
[pb-updater]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/RoomFrameUpdater.cs
[pb-replay-update]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/RoomFrameUpdater.cs#L30
[pb-clock]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/FrameClock.cs
[pb-buffer]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/FrameBuffer.cs
[pb-player-input]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/PlayerFrameInput.cs
[pb-frame-inputs]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Frame/FrameInputs.cs
[pb-world]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/World/LockstepWorld.cs
[pb-setup]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/World/LockstepWorldSetup.cs
[pb-codecs]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/World/SnapshotComponentCodecs.cs
[pb-record]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/ReplayRecording.cs
[et-commit]: https://github.com/egametang/ET/commit/743c635dd5b0f6f6bab549c0093382c85f3f8307
[et-package]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/package.json
[et-const]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/LSConstValue.cs
[et-clock]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/FixedTimeCounter.cs
[et-room]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/Room.cs
[et-room-system]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Share/RoomSystem.cs
[et-buffer]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/FrameBuffer.cs
[et-input]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/LSInput.cs
[et-replay]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/Replay.cs
[et-server]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Server/Room/LSServerUpdaterSystem.cs
[et-client]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSClientUpdaterSystem.cs
[et-replay-update]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSReplayUpdaterSystem.cs
[et-scene]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSSceneChangeHelper.cs
[et-ready]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Server/Map/C2Room_ChangeSceneFinishHandler.cs
[et-helper]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSClientHelper.cs
[et-confirm]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/OneFrameInputsHandler.cs
[et-adjust]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/Room2C_AdjustUpdateTimeHandler.cs
[et-hash]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Server/Room/C2Room_CheckHashHandler.cs
[et-hash-fail]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/Room2C_CheckHashFailHandler.cs
[et-input-system]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Share/LSInputComponentSystem.cs
[et-world]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lsentity/Scripts/Core/Share/LSWorld.cs
[et-world-update]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lsentity/Scripts/Core/Share/LSUpdater.cs
