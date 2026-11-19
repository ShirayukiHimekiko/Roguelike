# 战斗框架进场与可移除验收 Demo

实现范围为当局准备与首帧之间的时序、正式玩法系统的接入点，以及一个独立的验收 Demo。`BattleRoom` 仍持有 FSM、帧容器、时钟和更新器。玩法数据、规则和视图后续由项目在 `Runtime/Battle` 编写。

## 实施清单

- [x] **区分建房、准备和开帧。** `StartBattle` 和 `StartReplay` 已接入当局就绪条件。房间初始化时先建立输入槽，通过 FSM 更新轮询条件。就绪后建立 Entitas 世界、初始化系统，再进入开战状态建立时钟。默认开始菜单使用现有活动场景的就绪状态。
- [x] **暴露 Entitas 系统装配入口。** 实时和回放可为各自的 `BattleContext` 装配同一规则的系统树。系统由世界管理初始化、逻辑帧执行及退场释放。正式入口默认使用空系统树，供后续玩法装配。
- [x] **放置独立 Demo。** `Tools/BattleFrameworkDemo` 中的临时移动系统、输入序列和视图标记由 Unity Pipeline 运行，正式程序集和资源无 Demo 引用。
- [x] **验收。** 在 Unity `6000.0.69f1` 隔离副本的 `main` 场景，Demo 在连续 12 个宿主帧内保持未就绪，逻辑帧保持 `-1`。放行后第 `0` 帧消费预先提交的输入。实时和回放经过 25 帧后，定点位置与最后记录帧的帧前 hash 均一致。回放准备期拒绝跳帧和换速，实时与回放结束后均可重新建房。移除副本中的 Demo 脚本后，原有开始按钮仍能创建房间并从第 `0` 帧推进。

```text
StartBattle(开局数据, 当局就绪条件, 系统装配)
  → Room / Initialize：创建帧输入槽
  → FSM 更新：条件为真时创建 Entitas 世界、初始化系统并切到 Start
  → Start：以当前时间锚定第 0 帧
  → Run：更新器到点后调用 Room.Tick
```

时序参照上游房间准备完成后再开帧的流程，系统装配使用项目已有的 Entitas 1.14.1 生命周期。[上游进场代码](https://github.com/egametang/ET/blob/743c635dd5b0f6f6bab549c0093382c85f3f8307/Packages/cn.etetet.lockstep/Scripts/Hotfix/Client/LSSceneChangeHelper.cs) · [Entitas 1.14.1](https://github.com/sschmid/Entitas/releases/tag/1.14.1)

`isReady` 由游戏流程提供，FSM 在主线程读取它。后续可以用实际场景或资源加载操作的完成状态作为条件。`createSystems` 为每局装配自己的系统树，回放传入同一套规则。当前验收覆盖进场、首帧、系统驱动和回放。战斗结果到结算、回放终局校验和 Player 打包仍在框架后续清单上。

## Demo 的运行和移除

在 Unity 打开 `main` 场景，进入 Play Mode 后停留在开始菜单。用 Unity Pipeline 在项目根目录执行以下命令，可在 Scene 窗口看到临时标记。Demo 自行创建和关闭房间，录像只保存在内存。

```powershell
unity command --project-path . run_script --file Tools/BattleFrameworkDemo/BattleFrameworkDemo.cs --entry BattleFrameworkDemo.Run
```

Demo 结束时释放测试房间、移除 Scene 视图绘制回调。正式玩法开始前，删除 `UnityProject/Tools/BattleFrameworkDemo/` 整个目录即可。正式开始按钮使用空战斗世界，Demo 独立持有测试单位、固定输入序列、临时移动系统和显示标记。 [框架归位与复验](战斗框架文件归位方案.md)
