# Project B 按 ET10 改造并补齐单机逻辑帧框架执行方案

日期为 2026-11-19。状态为已实施，正式菜单 Play Mode 验收待确认。基线采用当前 Project B 工作区及 ET10 `743c635dd5b0f6f6bab549c0093382c85f3f8307`。本方案将 [脚本结构提案](Project_B按ET10对齐逻辑帧脚本结构方案.md) 落到具体接口和迁移步骤，并接续 [单机未完成项](单机战斗框架未完成项清单.md) 里的框架工作。当前行为和 ET 的源码依据见 [脚本、目录及行为对照](Project_B与ET10逻辑帧脚本目录及行为对照.md)。

## 一、范围与完成标准

本轮交付 ET 式脚本组织和单机框架闭环。实时局使用一份本地权威世界，回放从本地录像建局和重演。现有正式菜单、主场景和 TEngine FSM 继续承载流程。范围截止于单机框架，实际单位规则、设备映射、相机与表现资源、胜负和结算、新场景资源、独立 Player 发布、网络权威、预测、纠偏和重连分属后续任务。

| 内容 | 当前事实 | 本轮完成标准 |
| --- | --- | --- |
| ET 对应脚本 | `LockstepRoom` 既持有数据也做初始化、执行和定位，`RoomFrameUpdater` 每次按模式分支。 | `Room` 和 `RoomSystem` 分开，`LocalFrameUpdater` 和 `ReplayUpdaterSystem` 开局时按模式选定，共用一个 `RoomSystem.Tick()`。 |
| 单机进场 | `BattleManager.IsSceneReady()` 每次检查当前活动场景是否已加载。 | 将本场活动场景、就绪判断和结束边界收口到 `SceneChangeHelper` 和 Manager。场景就绪后只初始化一次，准备取消或场景失效后走同一退场，旧局没有后续启动机会。 |
| 录像客户端工具 | V3 读写在 `BattleReplayFile`，定位和倍率操作在 Room。 | `ClientHelper` 提供本地存读、跳转和倍速入口，`ReplayUpdaterSystem` 推进，`RoomSystem` 负责快照恢复、世界替换与共同帧。 |
| 世界替换 | 回放重建可以替换 `World` 和 Context，宿主缺少明确的替换通知。 | 从检查点重建后可观察新 World 已就位。开局建世界、同区间复用与真正替换具有可区分的边界，独立 Demo 可断言，不接实际视图。 |
| 自然结束 | 当前正式流程支持手工退出和应用释放。 | 世界内系统可以请求结束，当前帧执行和 Cleanup 完成后停步，外层只收尾一次。结束由框架转交，胜负规则留给玩法。 |
| 末帧结果对账 | V3 每帧保存帧前 hash，最终执行结果没有下一帧可以对账。 | 新录像保存一次末帧执行后的 hash。正常播放与定位到末尾都通过同一个帧后入口执行终局校验。V3 可读取并走原帧前校验。 |
| 已有单机能力 | 50 ms 步长、首帧 0、封帧、帧前快照、1,200 帧检查点、四档倍速、分批定位、同区间复用、帧前分歧停步均有实现。 | 结构迁移前后结果保持一致，从菜单进入、退出落盘、回放、定位和重开能走通。 |

自然结束和终局 hash 属于 Project B 的单机框架补齐。ET 示例提供的 `LSReplayUpdaterSystem`、`LSClientHelper.JumpReplay()` 和场景准备流程用于对照职责。ET 在检查点边界设 `AuthorityFrame = F` 的行为与本项目不同，本轮沿用恢复到 `F - 1` 后重演 `F` 的语义。 [ET RoomSystem][et-room] · [ET 场景切换][et-scene] · [ET 客户端工具][et-helper] · [ET 回放调度][et-replay] · [共同单帧][pb-room] · [回放定位][pb-seek]

## 二、目标目录与所有权

目录相对于 `Assets/GameScripts/HotFix/GameLogic/`。`Model` 和 `Hotfix` 表示源码职责，两者仍属于 `GameLogic.asmdef`。说明中的方法名为实施目标，不代表已存在。

```text
Runtime/
├─ Battle/
│  ├─ BattleManager.cs
│  └─ State/
│     ├─ BattleManagerState.cs
│     ├─ InitializeBattleState.cs
│     ├─ StartBattleState.cs
│     ├─ RunBattleState.cs
│     └─ EndBattleState.cs
└─ Lockstep/
   ├─ Model/
   │  ├─ Share/Room.cs, Replay.cs, FrameBuffer.cs, FixedTimeCounter.cs
   │  ├─ Share/PlayerFrameInput.cs, OneFrameInputs.cs
   │  └─ Client/ReplayUpdater.cs
   ├─ Hotfix/
   │  ├─ Share/RoomSystem.cs
   │  ├─ Local/LocalFrameUpdater.cs
   │  └─ Client/ReplayUpdaterSystem.cs, ClientHelper.cs
   │     Client/ClientHelper.ReplayFile.cs, SceneChangeHelper.cs
   └─ World/LockstepWorld.cs, LockstepWorldSetup.cs
      World/WorldSnapshot.cs, SnapshotComponentCodecs.cs
```

| 所有者 | 写入与对外职责 |
| --- | --- |
| `BattleManager` 与 FSM | 唯一活动 Room 所有者，选择本地最新录像路径，管理场景准备、状态跳转、退出和保存。完成和退出检查在 Room 更新返回以后。 |
| `SceneChangeHelper` | 在本地实时和回放入口捕获目标活动场景，轮询该场景是否可用，判定目标失效并通知外层走取消路径。它由 FSM 使用，独立 .NET 宿主可以直接调用 Room 进行无场景验收。 |
| `Room` | 持有玩家槽、模式、当前确认帧、世界、缓存、时钟、录像及按模式安装的更新入口。已确认帧、世界更换和关闭状态只由 `RoomSystem` 写入。 |
| `RoomSystem` | `CreateLocal()`、`CreateReplay()`、`InitializeWorld()`、`Start()`、`Update()`、`Tick()`、`RestoreCheckpoint()`、`SealReplay()`、`Release()`。从帧输入到世界执行的共同规则集中在这里。 |
| `LocalFrameUpdater` | 到期取 `AuthorityFrame + 1`，封存本地输入后调用共同 Tick。每轮最多一步。 |
| `ReplayUpdater`、`ReplayUpdaterSystem` | 前者持有播放倍率、定位目标和回放停步状态。后者根据时钟或显式定位目标选择输入，按预算调用共同 Tick，并处理播放、定位完成与终局对账。 |
| `ClientHelper` | `JumpReplay()` 提交定位请求，`ChangeReplaySpeed()` 设置倍率和锚点，`SaveReplayAsync()`、`LoadReplayAsync()` 处理本地文件。从 `RoomSystem` 使用恢复能力。文件入口不参与每帧调度。 |
| `LockstepWorld`、`LockstepWorldSetup` | 持有和装配 Entitas 世界，执行和 Cleanup 后递增世界帧。新增帧内 `RequestFinish()`，结束请求是当前帧的瞬时信号。 |

## 三、分步执行

### 第 1 步。拆共享房间与开局合同

- [x] **`LockstepRoom.cs` 迁为 `Model/Share/Room.cs`，增加 `Hotfix/Share/RoomSystem.cs`。** Room 保存共享状态和当局对象，RoomSystem 接管工厂、世界初始化、启动、帧输入与历史查询、单帧推进、快照恢复和释放。保持 `AuthorityFrame = -1`、初始世界待执行帧 `0`。伪代码 `room = CreateLocal(id, playerIds, seed, setup); InitializeWorld(room); Start(room, nowMs); Update(room, nowMs)`。
- [x] **删除 `RoomStartData.cs` 这个包装，更新它的四处数据流。** `RoomSystem.CreateLocal` 直接接收本地玩家、玩家顺序、种子和装配；`Replay` 保存已有开局字段；`LockstepWorld` 只接建局实际需要的玩家表和随机种子；V3 解码直接构建 `Replay`。冻结玩家槽顺序、空玩家局和准备期输入语义沿用原代码。伪代码 `playerIds = freeze(ids); slots = buildSlots(playerIds); replay = createRecording(localId, playerIds, seed)`。
- [x] **归位共享模型。** `ReplayRecording` 改 `Replay`，单玩家输入采用 `PlayerFrameInput`，`FrameInputs` 改 `OneFrameInputs`，`FrameClock` 改 `FixedTimeCounter`，`FrameBuffer` 保留名称。迁入 `Model/Share`。为 V3 保留出入流的字段顺序、定点原始值及检查点布局。伪代码 `oldInputs → newInputType → same raw direction and button`。
- [x] **同步正式调用和独立宿主。** `BattleManager`、四态使用 RoomSystem，`ReplaySeek`、`ReplaySpeeds` 和 Play Mode Demo 迁移到新类型与调用入口。仅更改类型、引用和路径，跟随迁移的成员和反射访问同步更新。保留 Unity 脚本原 GUID，新增脚本和目录由 Unity 管理元数据。伪代码 `old path and GUID → Unity move → new path; consumers → RoomSystem`。

验收目标为外层只持有一个 Room，原实时和回放都能通过同一个单帧入口，旧 V3 样本解码和基础帧行为与迁移前一致。

### 第 2 步。分开本地权威与回放更新，归位客户端工具

- [x] **拆除 `RoomFrameUpdater.cs` 的双分支调度。** 实时路径迁到 `Hotfix/Local/LocalFrameUpdater.cs`，回放路径迁到 `Model/Client/ReplayUpdater.cs` 和 `Hotfix/Client/ReplayUpdaterSystem.cs`。RoomSystem 在 `Start()` 一次选定当局更新入口，仍只有 TEngine FSM 一处正式轮询。伪代码 `room.UpdateFrame = isReplay ? replayUpdate : localUpdate; RoomSystem.Update → room.UpdateFrame`。
- [x] **归位定位与倍速入口。** `ClientHelper.JumpReplay()` 只提交有效定位请求，保留目标替换、同区间健康正跳复用、跨区间/退跳/分歧后的检查点恢复。回放更新器按预算追帧，在达到目标后以当前倍速重锚。每次单帧完成后检查约 5 ms 的预算，保持 1/2/4/8 倍和整数毫秒的约定。伪代码 `request(F); if needRestore: restore(checkpoint), authority = checkpoint.frame - 1; pursue(F); resetClock`。
- [x] **将 `BattleReplayFile` 迁入 `ClientHelper.ReplayFile.cs`。** 码流编码和 UniTask 文件 I/O 先按原 V3 保持行为，文件仍用临时文件和替换实现存盘。`ClientHelper.cs` 保持纯回放逻辑，两个独立 `.csproj` 显式排除文件 I/O 和 Unity 场景助手。`BattleManager` 继续选择文件路径和消费读取结果。伪代码 `manager resolves path → ClientHelper.LoadReplayAsync(path) → CreateReplay(recording)`。
- [x] **保留单帧的实时与回放差异。** 实时确认后记录帧输入、帧前指纹和周期检查点。回放仍先投递输入并对帧前 hash，对不上则跳过该帧的世界系统、保留最后确认帧并等待恢复请求。伪代码 `applyInputs → capturePreTick → recordOrCheck → commitFrame → world.Execute/Cleanup`。

验收目标为实时一轮最多推进一帧，回放所有输入来自录像，定位不会重复或越过目标。重点覆盖检查点 1,200、目标替换、同区间正跳、不同检查点重建和分歧前停步。

### 第 3 步。补本地进场、世界版本与自然结束

- [x] **新增 `SceneChangeHelper.cs`，改 `BattleManager` 与初始化状态。** 实时和回放共用一条本地进场路径。接管当局时捕获当前活动场景。初始化态检查该场景实例已加载并仍是本场选定场景，再初始化世界并进入开始态。准备中退出或场景已失效时交给同一个结束态。当前 `main` 复用且不卸载。伪代码 `enterRoom → bindActiveScene; waiting → pollScene; ready → InitWorld; invalid/cancel → EndState`。
- [x] **给房间提供一次明确的世界替换观察点。** `RoomSystem.RestoreCheckpoint()` 先用快照建立并装配新世界，提交世界、帧号和缓存后更新 `WorldRevision`。Manager 在一次 `Update` 返回后比较版本，按需转发当前世界变化。初始化和真正换世界推进版本，同区间复用维持版本。独立 Demo 直接断言版本及世界引用。伪代码 `restored = createWorld(snapshot); swapWorldAndBuffer(); ++WorldRevision; releaseOldWorld()`。
- [x] **在 `LockstepWorld` 增加 `RequestFinish()` 并接 `RoomSystem.Tick()`。** 同帧多次请求合并。世界仍完整执行剩余系统和 Cleanup，再递增 `World.Frame`。房间读取并清除本帧请求。实时房间在帧末进入已完成状态，后续更新停步。回放仍按已录帧结束，重演中同一系统发出的结束请求不会让宿主提前退场。伪代码 `request → executeRest → cleanup → frame++ → consumeFinish; if live && requested: room.finished = true`。
- [x] **打通 `RunBattleState`、`EndBattleState` 和 Manager 的唯一退出路径。** 每次 `RoomSystem.Update()` 返回后检查自然结束和手动退出，命中就进入同一结束态。Manager 取走当前房间，取得有帧的实时录像，释放世界后回菜单并保存。准备中取消及回放退出不会覆盖最新实时录像。异步读档返回继续使用现有释放与忙状态保护。伪代码 `Update returns → completedOrExit → detachRoom → takeLiveReplay → release → menu → saveOnce`。下一步在 `takeLiveReplay` 前加入终局封存。

验收目标为准备中无首帧，取消后无法启动旧局，世界替换通知对应真实的重建。一局自然结束时，系统与 Cleanup 仍在最后一帧各走一次，下一帧不执行，流程与存盘只触发一次。此处新增的是完成信号，由可移除 Demo 在指定帧发出。

### 第 4 步。补终局 hash 和 V3 兼容

- [x] **新增终局封存点。** `RoomSystem.SealReplay()` 在自然或手动退出的公共收尾路径里处理有帧的实时局。最后一帧 `F` 执行并清理后，`World.Frame == F + 1`。释放前复用确定性快照编码取一次终局 hash，`Replay` 增加可选的 `TerminalHash`，末帧号由 `FrameCount - 1` 推导。伪代码 `if live && FrameCount > 0: replay.TerminalHash = world.CaptureSnapshot().Hash`。
- [x] **`ClientHelper.ReplayFile.cs` 支持新写 V4、读 V3 和 V4。** 建议新文件名 `battle-last-v4.replay`。保留帧输入和检查点字段布局，在原文件校验值前增加 64 位终局 hash，V4 校验包含新字段。读最新局先尝试 V4，文件缺失时回读 `battle-last-v3.replay`。V4 无法解码时报告读取失败，避免无声切到旧档。旧 V3 保留原位，解码后 `TerminalHash` 为空。伪代码 `readVersion → decodeCommon; if V4: readTerminalHash; validateChecksum`。
- [x] **正常回放和定位到末尾走同一终局判断。** 已确认帧 `F` 实际执行后，若是录像末帧且有终局 hash，比较帧后状态并标记完成或终局分歧。保留帧前分歧和终局分歧两种状态。帧前分歧该帧未执行，终局分歧该帧已经执行。回放到末尾后停在最终画面，仍可主动定位或退出，下一次健康重演可重新对账。伪代码 `tickCommitted(F); if F == last && hasTerminal: checkHash(postTick); setPlaybackResult()`。
- [x] **处理预期文件失败。** 旧录像缺失继续走现有提示。读取截断、版本错误和校验失败时保持菜单可用并释放读档忙状态。保存失败保留旧档的原有保护，由宿主报告失败。伪代码 `try loadOrSave → report expected data/IO failure → clearBusy`。

验收目标为 V3 仍可播放并通过已有帧前校验，V4 在普通播放和定位到末尾时都完成终局比较。构造一个只在最后一帧 Cleanup 改变世界的用例，之前各帧 hash 应通过，终局检测应报不一致。空局和回放退出不改写最新录像。

### 第 5 步。核对源码引用和单机闭环

- [x] **源码与资源引用检查。** 更新 Demo 的两个 `.csproj`、反射引用和运行说明，排除宿主文件，确认正式代码无 Demo 依赖。核对迁移目标和 GUID，保留 GameLogic 程序集与 Entitas 生成目录。伪代码 `find stale type/path → update active caller → compare GUID map`。
- [x] **独立回归。** 复用 `ReplaySeek` 和 `ReplaySpeeds`，以可控时钟验证首帧、已封存输入、快照 hash、定位与四档倍率。自然结束和终局校验可在独立宿主中用内存录像覆盖。V3/V4 文件读写、坏档和保存失败由 Unity 内的可移除 Demo 验收，符合两个独立宿主的源码边界。伪代码 `live trace → replay/seek trace → compare frames and hashes`。
- [ ] **菜单链路验收。** 经授权后通过 Unity Pipeline 验证 `StartUI → 开局 → 首帧 → 自然/手动结束 → 回菜单 → 最新录像 → 定位或变速 → 退出重开`。使用独立验收文件路径避免覆盖用户录像。编译、测试和 Play Mode 结果按实际执行单独记录。伪代码 `real menu lifecycle → save → replay → exit → start again`。

## 四、执行决策

步骤 1–2 先完成文件和职责对齐，保留当前 V3 行为作为基线。步骤 3–4 增加单机框架能力并写入 V4。若只动结构即可通过原用例，再逐步加入生命周期和文件变化，有利于定位差异。

本方案的两个明确选择是复用现有 `main`，以及新增 V4 文件并兼容读取 V3。独立场景资源与构建配置需要另行选择实际场景和交付目标。以下记录已完成的实现和实际验收。

## 五、实施与验收结果

项目内锁步脚本已统一去除 `LS` 前缀。单人单帧输入使用 `PlayerFrameInput`，与 Unity 的 `Input` 类型区分。ET 上游源码名称按原样记录。

| 阶段 | 实际完成内容 |
| --- | --- |
| 共享房间 | `RoomSystem` 接管创建、建世界、启动、推进、帧历史、恢复和释放。共享模型按目标目录归位，`RoomStartData` 已由 Unity 删除。录像持有原开局字段，房间工厂冻结输入槽。 |
| 分模式推进 | `RoomSystem.Start()` 为当局选择一次更新入口。独立回放模型和更新器管理预算、定位和分歧，`ClientHelper` 承接跳转、倍速和文件存读。 |
| 单机流程 | 当局绑定发起时的活动场景。初始化或恢复完成后增加世界版本，宿主在更新返回后通知新世界。帧末完成信号经过原结束态，统一封存、释放和回菜单。 |
| 终局录像 | 写 V4 时增加帧后 hash，加载优先 V4、缺失才读 V3。正常播放和定位都由回放更新器在末帧执行后校验，终局分歧与帧前分歧各有状态。 |
| 源码与导入 | Unity Pipeline 完成 8 个脚本及原帧目录的归位，原 GUID 全部一致。5 个新增脚本由 Unity 生成元数据。正式调用与 Demo 路径已同步。导入中出现的暂时类型解析错误已消失，最终编译状态无失败。Pipeline 曾有一次主线程超时，复查确认所有目标已导入。 |
| 回归 | `ReplaySeek` 通过 1,200 帧边界、同区间复用与世界版本、分批定位、恢复、帧前分歧、自然结束和终局分歧。 `ReplaySpeeds` 通过 40 帧四档切速、到期、逐帧指纹与随机样本。Unity 编辑模式的临时文件用例通过 V3 读取和播放、V4 往返、保存失败保留原档和坏档拒绝。 |
| 待验收 | 正式 `StartUI` 到首帧、自然及手动退出、持久化目录读写和重开的完整 Play Mode 闭环。Editor 已回到就绪的编辑模式，运行中的项目场景与用户录像未被修改。 |

[pb-room]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Hotfix/Share/RoomSystem.cs
[pb-seek]: ../../Assets/GameScripts/HotFix/GameLogic/Runtime/Lockstep/Hotfix/Client/ReplayUpdaterSystem.cs
[et-room]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Share/RoomSystem.cs
[et-scene]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSSceneChangeHelper.cs
[et-helper]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSClientHelper.cs
[et-replay]: https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSReplayUpdaterSystem.cs
