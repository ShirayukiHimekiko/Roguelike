# Project B 按 ET10 对齐逻辑帧脚本结构方案

后续实施和验收结果见 [按 ET10 改造并补齐单机逻辑帧框架执行方案](Project_B按ET10改造并补齐单机逻辑帧框架执行方案.md)。本文保留改造前的脚本和提案。

2026-11-19。状态为待确认。基线为当前 Project B 工作区和 ET10 `743c635dd5b0f6f6bab549c0093382c85f3f8307`。本方案将前一轮的职责对照进一步落实到目录、类型和方法归属。范围是锁步框架的组织和调用边界。已有联机差距和运行行为差异见前一份源码对照。 [当前脚本与行为对照](Project_B与ET10逻辑帧脚本目录及行为对照.md)

## 一、为什么现在会不同

| 当前脚本 | 当初这样做的原因 | 按 ET 组织时的判断 |
| --- | --- | --- |
| `Runtime/Battle/BattleReplayFile.cs` | 按宿主 I/O 分类，因为本地 V3 读写依赖 UniTask。搬出 `Runtime/Lockstep` 后，两个独立 .NET Demo 可以递归链接演算源码。`BattleManager` 负责选本地文件，`ReplayRecording` 保存数据，`LockstepRoom` 和更新器才负责推进回放。 | 文件确实属于锁步客户端的回放工具。可以用 ET 的 **`LSClientHelper`** 命名并移到 `Hotfix/Client`。独立 Demo 的源码链接可以排除客户端 I/O 文件，宿主依赖无需决定整个模块的目录归属。ET 的 `LSClientHelper` 还负责 `JumpReplay`，客户端回滚与 hash 上报也在其中。Project B 对齐现有的录像存读与定位入口即可。 [本地录像读写][pb-file] · [两个宿主之一][pb-demo-project] · [ET LSClientHelper][et-helper] |
| `Runtime/Lockstep/LockstepRoom.cs` | 普通 C# 对象当时同时持有状态和实例操作，写入边界通过私有字段和属性集中。外层 FSM 与独立 Demo 都可以直接调用。 | `LockstepRoom` 目前还同时承载构造、时钟启动、共同帧、回放和释放。按 ET 对齐时应明确拆成 **`Model/Share/Room.cs`** 和 **`Hotfix/Share/RoomSystem.cs`**。共享状态由 Room 持有，房间操作放入 `RoomSystem`。这样后来添加不同更新器时，各更新器可以共用一个明确的单帧入口。 [Project B 房间][pb-room] · [ET Room][et-room] · [ET RoomSystem][et-room-system] |
| `Runtime/Lockstep/RoomStartData.cs` | 这个类同时服务于创建本地房间和 V3 录像存读，实际字段为本地玩家 ID、玩家槽顺序和随机种子。Project B 的时间锚点在 `StartSimulation()` 才取，世界由 `LockstepWorldSetup` 初始化或从快照恢复。 | ET 的 `RoomSystem.Init(room, unitInfos, startTime, frame)` 直接收单位信息、开战时间和起始帧，并用单位信息构建世界。Project B 对应到了两个阶段和几处数据。建议拆除独立 `RoomStartData`，本地创建入口接收本地玩家 ID、玩家序列及种子，初始化或启动入口接收此阶段使用的时间。录像需要的字段归 `Replay`，所以 V3 仍能读写；ET 的 `LockStepUnitInfo` 带单位初值，本轮无需引入空壳类型。 [Project B 开局数据][pb-start] · [Project B V3][pb-file] · [ET 初始化][et-room-system] · [ET 开局消息][et-ready] |

## 二、建议目录和脚本职责

以下路径以 `GameLogic/` 为根。`Model` 和 `Hotfix` 在这里表达状态与行为的源码归属，沿用项目现有 `GameLogic.asmdef`。`World` 下保留 Entitas 派生的世界和快照实现，与 ET 放在 `cn.etetet.lsentity` 的世界职责相对应。

```text
Runtime/
├─ Battle/
│  ├─ BattleManager.cs                  游戏入口、当前房间、场景就绪和退场
│  └─ State/                            TEngine 流程状态
└─ Lockstep/
   ├─ Model/
   │  ├─ Share/
   │  │  ├─ Room.cs                     共享房间状态、世界、时钟、缓存、录像引用
   │  │  ├─ Replay.cs                   录像开局字段、每帧输入与检查点
   │  │  ├─ FrameBuffer.cs              输入封帧与历史
   │  │  ├─ FixedTimeCounter.cs         帧号到到期时间的映射
   │  │  ├─ LSInput.cs                  单人单帧输入
   │  │  └─ OneFrameInputs.cs           整帧输入视图
   │  └─ Client/
   │     └─ LSReplayUpdater.cs          回放倍率、定位目标和分歧状态
   ├─ Hotfix/
   │  ├─ Share/
   │  │  └─ RoomSystem.cs                创建、初始化、共同单帧推进和释放
   │  ├─ Local/
   │  │  └─ LocalFrameUpdater.cs        到期判断、封帧和本地权威推进
   │  └─ Client/
   │     ├─ LSReplayUpdaterSystem.cs    正常播放与限时追帧
   │     ├─ LSClientHelper.cs           录像定位入口与回放控制编排
   │     └─ LSClientHelper.ReplayFile.cs  同一类型的异步 V3 存读与编解码
   └─ World/
      ├─ LockstepWorld.cs                Entitas 世界与单帧执行
      ├─ LockstepWorldSetup.cs           系统、组件、初值及输入投递装配
      ├─ WorldSnapshot.cs                帧前快照数据
      └─ SnapshotComponentCodecs.cs       稳定组件键与字段编解码
```

- `RoomSystem` 管共享的帧推进。它接收 `Room` 和 `OneFrameInputs`，投递输入、保存帧前状态、根据模式记录或校验，再推进世界。保持单一权威帧写入路径。Room 模型保存当局状态，更新器通过共享操作推进它。 [ET 共有单帧入口][et-room-system] · [Project B 当前单帧][pb-tick]
- `LSReplayUpdater` 是回放模式的数据，`LSReplayUpdaterSystem` 按已有时钟和预算推进，`LSClientHelper` 接收跳转请求并负责存读。恢复快照本身由共享房间操作完成。`LSClientHelper.ReplayFile.cs` 可用 `partial` 同属 `LSClientHelper`，让独立 .NET 工程链接纯演算、回放定位和更新逻辑，同时从源码列表排除 UniTask 文件 I/O。 [ET 回放更新器][et-replay] · [ET 客户端工具][et-helper] · [Project B 追帧与定位][pb-room]
- `LocalFrameUpdater` 对应 ET 服务端更新器的本地职责。它跟随现有宿主轮询。远端权威上线后再建立 `Hotfix/Server` 的更新和广播入口，客户端预测上线后再建立 `LSClientUpdaterSystem` 和权威帧处理。 [ET 服务端更新][et-server] · [ET 客户端预测][et-client]
- `LSSceneChangeHelper` 的现有对应职责在 `BattleManager` 和 TEngine 状态中。当前场景只需要就绪检查，新增同名助手只有在需要共享的锁步场景切换或重连流程时才有独立职责。`LSInputComponentSystem` 的调用位置对应 Entitas 世界内的输入消费系统，整帧投递仍在 `RoomSystem`。 [ET 场景切换][et-scene] · [ET 世界内输入消费][et-input] · [Project B 宿主][pb-battle]

## 三、执行顺序与验收

- [ ] **先拆 Room 和初始化数据。** 将房间状态与共同操作迁到 `Room.cs` 和 `RoomSystem.cs`，撤掉独立的 `RoomStartData`。按调用阶段归还数据，统一冻结玩家槽顺序和本地身份，给 `Replay` 保留已有开局字段。保留准备期可提交首帧输入和世界就绪后才取时间锚点的顺序。伪代码 `CreateLocal(localPlayerId, playerIds, seed, setup) → SceneReady → InitWorld(room) → Start(room, nowMs)`。
- [ ] **分开两种更新并归位客户端工具。** 当局启动时选好本地推进或回放推进。将回放状态、调度、定位入口和文件操作放到上表位置，让两个更新器共用一份 `RoomSystem.Tick`。保持第 `F` 帧快照恢复后先执行 `F` 帧，hash 不一致停在演算前，倍速和追帧预算沿用当前约定。伪代码 `LocalUpdater → Seal → Tick`，`ReplayUpdater → ReadRecordedInputs → Tick`，`ClientHelper.JumpReplay → RequestSeek → RestoreCheckpoint → ReplayUpdater`。
- [ ] **迁移文件并同步引用。** 用 Unity 工作流保留原有脚本 GUID，更新 `BattleManager`、状态、Demo 的类型和反射引用，给两个独立宿主链接所需的共享和回放源码。保留 V3 文件名、字段顺序、组件键以及 Entitas 生成配置。伪代码 `旧文件及 GUID → 目标路径`，`旧 V3 字段 → 现有 V3 字段顺序`。
- [ ] **按授权验证逻辑。** 验收准备期输入、实时首帧、正常播放、四档倍速、跨 1,200 帧定位、回放分歧停步及旧 V3 文件读取。伪代码 `相同初态和输入 → 相同确认帧序与每帧 hash`。

当前只记录设计。开局时钟来源、快照恢复帧边界和回放失败处理采用 Project B 的现有合同。若要把这些行为一并替换成 ET 的示例行为，需要单独确认兼容性目标。

[pb-file]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/BattleReplayFile.cs
[pb-demo-project]: ../../Tools/BattleFrameworkDemo/ReplaySeek/ReplaySeek.csproj
[pb-room]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs
[pb-start]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/RoomStartData.cs
[pb-tick]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/LockstepRoom.cs#L194
[pb-battle]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Battle/BattleManager.cs#L68
[et-room]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Model/Share/Room.cs
[et-room-system]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Share/RoomSystem.cs
[et-helper]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSClientHelper.cs
[et-ready]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Server/Map/C2Room_ChangeSceneFinishHandler.cs
[et-replay]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSReplayUpdaterSystem.cs
[et-server]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Server/Room/LSServerUpdaterSystem.cs
[et-client]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSClientUpdaterSystem.cs
[et-scene]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSSceneChangeHelper.cs
[et-input]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Share/LSInputComponentSystem.cs
