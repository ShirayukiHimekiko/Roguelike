using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Cysharp.Threading.Tasks;
using Entitas;
using GameLogic;
using TEngine;
using UnityEditor;
using UnityEngine;

/// <summary>可移除的 Editor 验收脚本。由 Pipeline 临时加载，用于验证战斗框架。</summary>
public static class BattleFrameworkDemo
{
    private const long UNIT_ID = 1;
    private const BindingFlags INSTANCE_INTERNAL = BindingFlags.Instance | BindingFlags.NonPublic;
    private const BindingFlags STATIC_INTERNAL = BindingFlags.Static | BindingFlags.NonPublic;
    private static readonly FixedPoint STEP = FixedPoint.FromInt(1) / FixedPoint.FromInt(4);
    private const int POSITION = 0;
    private const int ROTATION = 1;
    private const int PLAYER = 2;
    private const int INPUT = 3;
    private static readonly IMatcher<BattleEntity> PositionMatcher = Matcher<BattleEntity>.AllOf(POSITION);
    private static readonly IMatcher<BattleEntity> PlayerMatcher = Matcher<BattleEntity>.AllOf(PLAYER);

    /// <summary>通过正式菜单验证唯一房间所有权、首帧和应用释放，不写玩家录像。</summary>
    public static async Task<string> RunManagerMenu()
    {
        Require(EditorApplication.isPlaying, "请先在 main 场景进入 Play Mode。");
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        PropertyInfo roomProperty = typeof(BattleManager).GetProperty("Room", INSTANCE_INTERNAL);
        FieldInfo fsmField = typeof(BattleManager).GetField("_fsm", INSTANCE_INTERNAL);
        FieldInfo startButton = typeof(StartUI).GetField("m_btn_Start", INSTANCE_INTERNAL);
        BattleManager manager = null;

        try
        {
            StartUI menu = await GameModule.UI.GetUIAsyncAwait<StartUI>(timeout.Token);
            Require(menu != null, "正式菜单未就绪。");
            ((UnityEngine.UI.Button)startButton.GetValue(menu)).onClick.Invoke();
            manager = BattleManager.Instance;
            var room = (Room)roomProperty.GetValue(manager);
            Require(room != null && room.CurrentFrame == -1, "菜单应只创建待准备的房间。");
            manager.StartBattle();
            Require(ReferenceEquals(room, roomProperty.GetValue(manager)), "重复开始替换了当前局。");
            while (room.CurrentFrame < 0)
            {
                await UniTask.NextFrame(timeout.Token);
            }

            Require(room.TryGetFrameHash(0, out _), "正式房间未从第 0 帧开始。");
            var fsm = (IFsm<BattleManager>)fsmField.GetValue(manager);
            manager.Release();
            manager = null;
            Require(fsm.IsDestroyed && room.CurrentFrame == -1, "应用释放没有清理战斗 FSM 或 Room。");

            menu = await GameModule.UI.ShowUIAsyncAwait<StartUI>();
            ((UnityEngine.UI.Button)startButton.GetValue(menu)).onClick.Invoke();
            manager = BattleManager.Instance;
            var nextRoom = (Room)roomProperty.GetValue(manager);
            Require(nextRoom != null && !ReferenceEquals(room, nextRoom) && nextRoom.CurrentFrame == -1,
                "重新点击开始没有创建全新的房间。");
            return "PASS · 正式开始按钮、唯一当前 Room、FSM 开第 0 帧、应用释放和重开";
        }
        finally
        {
            if (manager != null)
            {
                manager.Release();
                GameModule.UI.ShowUIAsync<StartUI>();
            }
        }
    }

    /// <summary>不传任何样例接入配置，验收正式空房间的真实调度与录像。</summary>
    public static async Task<string> RunEmptyRoom()
    {
        Require(EditorApplication.isPlaying, "请先在 main 场景进入 Play Mode。");
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var driver = new DemoRoomDriver();
        string path = Path.Combine(Application.temporaryCachePath, $"battle-empty-{Guid.NewGuid():N}.replay");
        PropertyInfo worldProperty = typeof(Room).GetProperty("World", INSTANCE_INTERNAL);
        bool ready = false;
        Room room = driver.StartLive(0, Array.Empty<long>(), () => ready);
        try
        {
            await UniTask.NextFrame(timeout.Token);
            Require(room.CurrentFrame == -1 && worldProperty.GetValue(room) == null, "空房间提前创建了世界。");
            ready = true;
            while (room.CurrentFrame < 5)
            {
                await UniTask.NextFrame(timeout.Token);
            }

            var live = (LockstepWorld)worldProperty.GetValue(room);
            int target = room.CurrentFrame;
            Require(live.Context.count == 0 && live.Context.totalComponents == 0 &&
                !room.SubmitLocalInput(default), "生产 Battle Context 留有样例组件或空房间接受了输入。");
            Require(room.TryGetFrameHash(target, out ulong expectedHash), "空房间没有记录帧前指纹。");
            Replay recording = room.SealReplay();
            Require(driver.Close(room), "空房间退出失败。");
            room = null;

            Replay restored = await SaveAndReload(path, recording);
            room = driver.StartReplay(restored);
            while (room.CurrentFrame < 0)
            {
                await UniTask.NextFrame(timeout.Token);
            }

            await SeekAndWait(room, target, timeout.Token);
            Require(room.TryGetFrameHash(target, out ulong actualHash) && actualHash == expectedHash &&
                restored.TerminalHash == recording.TerminalHash && room.PlaybackStatus == ReplayPlaybackStatus.Completed &&
                ((LockstepWorld)worldProperty.GetValue(room)).Context.count == 0,
                "空房间的 V4 回放没有还原原始状态。");
            return $"PASS · 空 Battle Context、等待就绪、推进 {restored.FrameCount} 帧、V4 落盘和终局校验";
        }
        finally
        {
            driver.Close(room);
            File.Delete(path);
        }
    }

    /// <summary>延迟开帧、演算定点位移、回放重演并释放测试房间。</summary>
    public static async Task<string> Run()
    {
        Require(EditorApplication.isPlaying, "请先在 main 场景进入 Play Mode。");

        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
        var driver = new DemoRoomDriver();
        LockstepWorld world = null;
        var setup = new LockstepWorldSetup(CreateDemoContext, RegisterComponents, CreatePlayers, next =>
        {
            world = next;
            return new Systems().Add(new MovementSystem(next.Context));
        }, ApplyInputs);
        bool ready = false;
        Room room = driver.StartLive(UNIT_ID, new[] { UNIT_ID }, () => ready, setup);

        // Scene 视图标记单向读取逻辑位姿，退场时随回调一起移除。
        void DrawUnit(SceneView view)
        {
            if (world == null || !world.TryGetEntity(1, out BattleEntity entity))
            {
                return;
            }

            FixedVector3 state = PositionOf(entity);
            float x = (float)((double)state.X.RawValue / FixedPoint.One.RawValue);
            float z = (float)((double)state.Z.RawValue / FixedPoint.One.RawValue);
            var position = new Vector3(x, 0.4f, z);
            using var color = new Handles.DrawingScope(Color.cyan);
            Handles.SphereHandleCap(0, position, Quaternion.identity, 0.35f, EventType.Repaint);
            Handles.Label(position + Vector3.up * 0.4f, $"{(room.IsReplay ? "回放" : "实时")} {room.CurrentFrame}");
        }

        SceneView.duringSceneGui += DrawUnit;
        try
        {
            var input = new PlayerFrameInput(new FixedVector2(FixedPoint.One, FixedPoint.Zero));
            Require(room.SubmitLocalInput(input), "准备阶段应该能接收第 0 帧的输入。");
            for (int frame = 0; frame < 12; frame++)
            {
                await UniTask.NextFrame(timeout.Token);
                Require(room.CurrentFrame == -1 && room.Replay.FrameCount == 0 &&
                    world == null, "未就绪时创建了战斗世界或推进了逻辑帧。");
            }

            ready = true;
            while (room.CurrentFrame < 0)
            {
                await UniTask.NextFrame(timeout.Token);
            }

            Require(room.CurrentFrame == 0 && room.TryGetFrameInput(0, UNIT_ID, out PlayerFrameInput firstInput) &&
                firstInput.Direction.X == FixedPoint.One, "放行后应从第 0 帧消费准备阶段提交的输入。");

            while (room.CurrentFrame < 24)
            {
                SceneView.RepaintAll();
                await UniTask.NextFrame(timeout.Token);
            }

            int lastFrame = room.CurrentFrame;
            Require(world.TryGetEntity(1, out BattleEntity live), "实时单位不存在。");
            FixedPoint liveX = PositionOf(live).X;
            Require(liveX == STEP * FixedPoint.FromInt(lastFrame + 1), "定点移动结果与已执行帧数不一致。");
            Require(room.TryGetFrameHash(lastFrame, out ulong lastHash), "末帧快照缺失。");
            Replay recording = room.Replay;
            Require(driver.Close(room), "实时房间结束失败。");

            ready = false;
            world = null;
            room = driver.StartReplay(recording, () => ready, setup);
            await UniTask.NextFrame(timeout.Token);
            Require(room.CurrentFrame == -1 && !room.JumpReplay(lastFrame) &&
                !room.ChangeReplaySpeed(2), "回放准备完成前不应推进、跳帧或修改时钟。");

            ready = true;
            while (room.CurrentFrame < 0)
            {
                await UniTask.NextFrame(timeout.Token);
            }

            await SeekAndWait(room, lastFrame, timeout.Token);
            Require(world.TryGetEntity(1, out BattleEntity replay) && PositionOf(replay).X == liveX &&
                room.TryGetFrameHash(lastFrame, out ulong replayHash) && replayHash == lastHash, "回放位姿或 hash 不一致。");
            SceneView.RepaintAll();
            await UniTask.Delay(TimeSpan.FromMilliseconds(450), ignoreTimeScale: true, cancellationToken: timeout.Token);

            Require(driver.Close(room), "回放房间结束失败。");
            room = driver.StartLive(UNIT_ID, new[] { UNIT_ID }, () => false, setup);
            Require(driver.Close(room) && room.CurrentFrame == -1, "准备中的房间应当可以直接结束。");
            return $"PASS · 等待就绪、从第 0 帧开帧、{recording.FrameCount} 帧定点演算与回放对账、退场和重开";
        }
        finally
        {
            SceneView.duringSceneGui -= DrawUnit;
            driver.Close(room);
            SceneView.RepaintAll();
        }
    }

    /// <summary>样例使用自己的组件表，生产 Battle Context 无需包含任一样例组件。</summary>
    private static Context<BattleEntity> CreateDemoContext()
    {
        Type[] types = { typeof(DemoPosition), typeof(DemoRotation), typeof(DemoPlayer), typeof(DemoInput) };
        string[] names = { nameof(DemoPosition), nameof(DemoRotation), nameof(DemoPlayer), nameof(DemoInput) };
        return new Context<BattleEntity>(types.Length, 0, new ContextInfo("BattleDemo", names, types),
            entity => new SafeAERC(entity), () => new BattleEntity());
    }

    /// <summary>在接入层定义样例组件的稳定快照键和字段格式。</summary>
    private static void RegisterComponents(SnapshotComponentCodecs registry)
    {
        registry.Register<DemoPosition>(1, (writer, component) =>
        {
            writer.Write(component.Value.X.RawValue);
            writer.Write(component.Value.Y.RawValue);
            writer.Write(component.Value.Z.RawValue);
        }, reader => new DemoPosition { Value = new FixedVector3(FixedPoint.FromRaw(reader.ReadInt64()),
            FixedPoint.FromRaw(reader.ReadInt64()), FixedPoint.FromRaw(reader.ReadInt64())) });
        registry.Register<DemoRotation>(2, (writer, component) =>
        {
            writer.Write(component.Value.X.RawValue);
            writer.Write(component.Value.Y.RawValue);
            writer.Write(component.Value.Z.RawValue);
            writer.Write(component.Value.W.RawValue);
        }, reader => new DemoRotation { Value = new FixedQuaternion(FixedPoint.FromRaw(reader.ReadInt64()),
            FixedPoint.FromRaw(reader.ReadInt64()), FixedPoint.FromRaw(reader.ReadInt64()),
            FixedPoint.FromRaw(reader.ReadInt64())) });
        registry.Register<DemoPlayer>(3, (writer, component) => writer.Write(component.Id),
            reader => new DemoPlayer { Id = reader.ReadInt64() });
        registry.Register<DemoInput>(4, (writer, component) =>
        {
            writer.Write(component.Value.Direction.X.RawValue);
            writer.Write(component.Value.Direction.Y.RawValue);
            writer.Write(component.Value.Button);
        }, reader => new DemoInput { Value = new PlayerFrameInput(new FixedVector2(FixedPoint.FromRaw(reader.ReadInt64()),
            FixedPoint.FromRaw(reader.ReadInt64())), reader.ReadInt32()) });
    }

    /// <summary>仅实时开始时，为每个测试玩家创建一个示例实体。</summary>
    private static void CreatePlayers(LockstepWorld world, IReadOnlyList<long> players)
    {
        foreach (long player in players)
        {
            SpawnUnit(world, player, default);
        }
    }

    /// <summary>生成 Demo 单位并绑定操控玩家。</summary>
    private static BattleEntity SpawnUnit(LockstepWorld world, long playerId, FixedVector3 position)
    {
        BattleEntity entity = world.Context.CreateEntity();
        entity.AddComponent(POSITION, new DemoPosition { Value = position });
        entity.AddComponent(ROTATION, new DemoRotation { Value = FixedQuaternion.Identity });
        entity.AddComponent(PLAYER, new DemoPlayer { Id = playerId });
        entity.AddComponent(INPUT, new DemoInput());
        return entity;
    }

    /// <summary>按当前单位上的归属，把该玩家的封存值写入 Demo 实体。</summary>
    private static void ApplyInputs(LockstepWorld world, OneFrameInputs inputs)
    {
        foreach (BattleEntity entity in world.Context.GetGroup(PlayerMatcher).GetEntities())
        {
            var player = (DemoPlayer)entity.GetComponent(PLAYER);
            if (inputs.TryGetInput(player.Id, out PlayerFrameInput input))
            {
                entity.ReplaceComponent(INPUT, new DemoInput { Value = input });
            }
        }
    }

    /// <summary>从 Demo 的操控绑定查找当前单位。</summary>
    private static BattleEntity FindUnit(LockstepWorld world, long playerId)
    {
        foreach (BattleEntity entity in world.Context.GetGroup(PlayerMatcher).GetEntities())
        {
            if (((DemoPlayer)entity.GetComponent(PLAYER)).Id == playerId)
            {
                return entity;
            }
        }

        return null;
    }

    /// <summary>读取 Demo 单位的逻辑位置。</summary>
    private static FixedVector3 PositionOf(BattleEntity entity)
    {
        return ((DemoPosition)entity.GetComponent(POSITION)).Value;
    }

    /// <summary>验收动态世界、变长录像文件和检查点往返定位。</summary>
    public static async Task<string> RunWorldRebuild()
    {
        Require(EditorApplication.isPlaying, "请先在 main 场景进入 Play Mode。");
        const int lastFrame = 1205;
        const long localId = 71;
        const long otherPlayer = 19;
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(20));
        var driver = new DemoRoomDriver();
        Room room = null;
        LockstepWorld world = null;
        int created = 0;
        int tornDown = 0;
        int seeded = 0;
        string path = Path.Combine(Application.temporaryCachePath, $"battle-demo-{Guid.NewGuid():N}.replay");

        Systems Mount(LockstepWorld next)
        {
            created++;
            world = next;
            return new Systems().Add(new WorldRebuildSystem(next, localId, () => tornDown++));
        }

        var setup = new LockstepWorldSetup(CreateDemoContext, RegisterComponents, (next, players) =>
        {
            seeded++;
            CreatePlayers(next, players);
        }, Mount, ApplyInputs);

        try
        {
            room = driver.StartLive(localId, new[] { localId, otherPlayer }, worldSetup: setup);
            while (room.CurrentFrame < 0)
            {
                await UniTask.NextFrame(timeout.Token);
            }

            // 只在验收脚本里给真实 updater 提供到期时间，免等 60 秒墙上时钟。
            while (room.CurrentFrame < lastFrame)
            {
                int pendingFrame = room.CurrentFrame + 1;
                Require(room.SubmitLocalInput(new PlayerFrameInput(default, pendingFrame)), "本地输入提交失败。");
                room.Update(long.MaxValue);
                if (pendingFrame == 6 || pendingFrame == 8)
                {
                    RequireControl(world, localId, pendingFrame);
                }
            }

            Require(room.Replay.FrameCount == lastFrame + 1 &&
                room.TryGetFrameInput(lastFrame, localId, out PlayerFrameInput actual) && actual.Button == lastFrame &&
                room.TryGetFrameInput(lastFrame, otherPlayer, out PlayerFrameInput otherInput) && otherInput.Button == 0,
                "两个玩家的历史输入槽应分别保存输入。");
            RequireControl(world, localId, lastFrame);
            Require(world.TryGetEntity(4, out BattleEntity survivor) && survivor.HasComponent(POSITION),
                "验收用持久实体应该活过第一个周期检查点。");
            Replay recording = room.SealReplay();
            string expectedState = ReadState(world);
            int expectedRandom = world.NextRandom();
            var expectedHashes = new Dictionary<int, ulong>();
            foreach (int frame in new[] { 6, 1199, 1200, lastFrame })
            {
                Require(room.TryGetFrameHash(frame, out ulong hash), $"实时房间缺少第 {frame} 帧指纹。");
                expectedHashes.Add(frame, hash);
            }

            LockstepWorld liveWorld = world;
            Require(driver.Close(room) && tornDown == 1 && liveWorld.Context.count == 0,
                "实时世界结束后应卸载系统并清空实体。");
            room = null;

            var loaded = await SaveAndReload(path, recording);
            Require(loaded.FrameCount == lastFrame + 1, "重新读入的录像帧数不对。");
            room = driver.StartReplay(loaded, worldSetup: setup);
            while (room.CurrentFrame < 0)
            {
                await UniTask.NextFrame(timeout.Token);
            }

            foreach (int target in new[] { 1200, 6, 1199, lastFrame })
            {
                LockstepWorld previous = world;
                int previousFrame = room.CurrentFrame;
                int previousCreated = created;
                int previousTornDown = tornDown;
                await SeekAndWait(room, target, timeout.Token);
                Require(room.CurrentFrame == target &&
                    world.Frame == target + 1 && room.TryGetFrameHash(target, out ulong hash) &&
                    hash == expectedHashes[target], $"检查点重演至第 {target} 帧失败。");
                if (previousFrame == 6 && target == 1199)
                {
                    Require(world.Context == previous.Context && created == previousCreated && tornDown == previousTornDown,
                        "同一检查点区间向前定位时不应重建世界和系统树。");
                }
                else
                {
                    Require(world.Context != previous.Context && previous.Context.count == 0 &&
                        created == previousCreated + 1 && tornDown == previousTornDown + 1,
                        $"定位第 {target} 帧时没有替换世界和系统树。");
                }
                RequireControl(world, localId, target);
            }

            Require(ReadState(world) == expectedState && world.NextRandom() == expectedRandom,
                "定位后的实体 ID、状态或后续随机序列与连续演算不一致。");
            Require(driver.Close(room) && created == tornDown && seeded == 1,
                "存在未释放的系统树，或回放重复生成了开局实体。");
            room = null;
            return $"PASS · {loaded.FrameCount} 帧 V4 落盘重读，检查点 0/1200，四次定位；输入、ID、随机与系统重建一致";
        }
        finally
        {
            driver.Close(room);
            File.Delete(path);
        }
    }

    /// <summary>用独立临时文件覆盖旧 V3、V4 终局指纹和坏档读取。</summary>
    public static async Task<string> RunReplayFileCompatibility()
    {
        // 旧格式的单帧空世界样本，由 V3 字段布局固定下来的 65 字节。
        const string legacyFixture = "QlRSMQMAAAAAAAAAAAAAAHEVAAAAAAAAAQAAAJ+X99H/TPpNEQAAAAAAAAAAAAAAAAAAAAAAAAAAdW3W602C3xQ=";
        string path = Path.Combine(Application.temporaryCachePath, $"battle-format-{Guid.NewGuid():N}.replay");
        Room room = null;
        try
        {
            await File.WriteAllBytesAsync(path, Convert.FromBase64String(legacyFixture));
            Replay legacy = await LoadReplayForDemo(path);
            Require(legacy.FrameCount == 1 && !legacy.TerminalHash.HasValue, "V3 旧档没有正确读取。");
            room = RoomSystem.CreateReplay(legacy);
            room.InitializeWorld();
            room.Start(0);
            room.Update(0);
            Require(room.CurrentFrame == 0 && room.PlaybackStatus == ReplayPlaybackStatus.Completed,
                "旧 V3 录像未通过帧前校验。");
            room.Release();

            room = RoomSystem.CreateLocal(0, Array.Empty<long>());
            room.InitializeWorld();
            room.Start(0);
            room.Update(0);
            Replay recording = room.SealReplay();
            Replay restored = await SaveAndReload(path, recording);
            Require(restored.TerminalHash.HasValue && restored.TerminalHash == recording.TerminalHash,
                "V4 终局指纹没有往返。");

            bool saveFailed = false;
            try
            {
                await SaveReplayForDemo(Path.Combine(path, "unwritable.replay"), recording);
            }
            catch (IOException)
            {
                saveFailed = true;
            }
            Require(saveFailed && (await LoadReplayForDemo(path)).TerminalHash == restored.TerminalHash,
                "写入失败后应保有原 V4 录像。");

            byte[] bytes = await File.ReadAllBytesAsync(path);
            bytes[bytes.Length - 1] ^= 1;
            await File.WriteAllBytesAsync(path, bytes);
            try
            {
                await LoadReplayForDemo(path);
            }
            catch (InvalidDataException)
            {
                return "PASS · V3 旧档播放、V4 终局指纹往返、保存失败保留旧档、坏档拒绝";
            }

            throw new InvalidOperationException("损坏的 V4 录像被接受。");
        }
        finally
        {
            room?.Release();
            File.Delete(path);
        }
    }

    /// <summary>使用独立的 TEngine FSM 轮询 Demo 房间，不占用正式当前局。</summary>
    private sealed class DemoRoomDriver
    {
        private IFsm<DemoRoomDriver> _fsm;
        private Room _room;
        private Func<bool> _isReady;

        internal Room StartLive(long localPlayerId, IReadOnlyList<long> playerIds, Func<bool> isReady = null, LockstepWorldSetup worldSetup = null)
        {
            return Start(RoomSystem.CreateLocal(localPlayerId, playerIds, worldSetup), isReady);
        }

        internal Room StartReplay(Replay recording, Func<bool> isReady = null,
            LockstepWorldSetup worldSetup = null)
        {
            return Start(RoomSystem.CreateReplay(recording, worldSetup), isReady);
        }

        private Room Start(Room room, Func<bool> isReady)
        {
            _room = room;
            _isReady = isReady;
            _fsm = GameModule.Fsm.CreateFsm($"BattleDemo-{Guid.NewGuid():N}", this, new DriveRoomState());
            _fsm.Start<DriveRoomState>();
            return room;
        }

        internal bool Close(Room room)
        {
            if (_room == null || _room != room)
            {
                return false;
            }

            GameModule.Fsm.DestroyFsm(_fsm);
            _fsm = null;
            _room.Release();
            _room = null;
            return true;
        }

        private sealed class DriveRoomState : FsmState<DemoRoomDriver>
        {
            private bool _started;

            protected override void OnUpdate(IFsm<DemoRoomDriver> fsm, float elapseSeconds, float realElapseSeconds)
            {
                DemoRoomDriver driver = fsm.Owner;
                if (!_started)
                {
                    if (driver._isReady != null && !driver._isReady())
                    {
                        return;
                    }

                    driver._room.InitializeWorld();
                    driver._room.Start(FixedTimeCounter.ReadMilliseconds());
                    _started = true;
                    return;
                }

                driver._room.Update(System.Diagnostics.Stopwatch.GetTimestamp() * 1000 /
                    System.Diagnostics.Stopwatch.Frequency);
            }
        }
    }

    /// <summary>等真实房间更新器执行完目标帧。</summary>
    private static async UniTask SeekAndWait(Room room, int target, CancellationToken token)
    {
        Require(room.JumpReplay(target), $"未接受定位到第 {target} 帧的请求。");
        while (room.ReplaySeekTargetFrame >= 0)
        {
            await UniTask.NextFrame(token);
        }

        Require(room.ReplayDivergedFrame < 0 && room.CurrentFrame == target, $"未能定位到第 {target} 帧。");
    }

    private static async UniTask<Replay> SaveAndReload(string path, Replay recording)
    {
        await SaveReplayForDemo(path, recording);
        return await LoadReplayForDemo(path);
    }

    /// <summary>经正式文件入口在临时路径保存验收录像。</summary>
    private static async UniTask SaveReplayForDemo(string path, Replay recording)
    {
        await (UniTask)typeof(ClientHelper).GetMethod("SaveReplayAsync", STATIC_INTERNAL)
            .Invoke(null, new object[] { path, recording });
    }

    /// <summary>经正式文件入口加载验收录像。</summary>
    private static async UniTask<Replay> LoadReplayForDemo(string path)
    {
        return await (UniTask<Replay>)typeof(ClientHelper).GetMethod("LoadReplayAsync", STATIC_INTERNAL)
            .Invoke(null, new object[] { path });
    }

    /// <summary>读取有稳定 ID 的可比验收状态。</summary>
    private static string ReadState(LockstepWorld world)
    {
        var entities = new List<BattleEntity>();
        world.GetEntitiesInOrder(world.Context.GetGroup(PositionMatcher), entities);
        return string.Join(";", entities.ConvertAll(entity =>
            $"{world.GetEntityId(entity)}:{PositionOf(entity).X.RawValue}"));
    }

    /// <summary>检查更换操控对象前后，原玩家的封存输入仍被正确单位消费。</summary>
    private static void RequireControl(LockstepWorld world, long playerId, int frame)
    {
        BattleEntity entity = FindUnit(world, playerId);
        Require(entity != null && (world.GetEntityId(entity) == 1) == (frame < 7) &&
            ((DemoInput)entity.GetComponent(INPUT)).Value.Button == frame,
            $"第 {frame} 帧的玩家输入未交给当前操控实体。");
    }

    /// <summary>验收条件失败时将失败原因交给 Pipeline。</summary>
    private static void Require(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    /// <summary>仅用于 Demo，每帧按定点输入移动固定距离。</summary>
    private sealed class MovementSystem : IExecuteSystem
    {
        private readonly IGroup<BattleEntity> _units;

        /// <summary>缓存所需位置与输入组件的查询。</summary>
        internal MovementSystem(Context<BattleEntity> context)
        {
            _units = context.GetGroup(Matcher<BattleEntity>.AllOf(POSITION, INPUT));
        }

        /// <summary>以封存输入更新定点位置。</summary>
        public void Execute()
        {
            foreach (BattleEntity unit in _units.GetEntities())
            {
                FixedVector2 direction = ((DemoInput)unit.GetComponent(INPUT)).Value.Direction;
                FixedVector3 step = new FixedVector3(direction.X * STEP, FixedPoint.Zero, direction.Y * STEP);
                unit.ReplaceComponent(POSITION, new DemoPosition { Value = PositionOf(unit) + step });
            }
        }
    }

    /// <summary>只用于 Demo，制造动态实体、分配器空洞和逐帧消耗的随机状态。</summary>
    private sealed class WorldRebuildSystem : IExecuteSystem, ITearDownSystem
    {
        private readonly LockstepWorld _world;
        private readonly IGroup<BattleEntity> _positions;
        private readonly List<BattleEntity> _ordered = new List<BattleEntity>();
        private readonly Action _onTearDown;
        private readonly long _localPlayerId;

        /// <summary>在新 Context 中绑定查询。</summary>
        internal WorldRebuildSystem(LockstepWorld world, long localPlayerId, Action onTearDown)
        {
            _world = world;
            _positions = world.Context.GetGroup(PositionMatcher);
            _localPlayerId = localPlayerId;
            _onTearDown = onTearDown;
        }

        /// <summary>按 ID 顺序推进临时数据，并交替创建和删除实体。</summary>
        public void Execute()
        {
            _world.GetEntitiesInOrder(_positions, _ordered);
            long previousId = 0;
            foreach (BattleEntity entity in _ordered)
            {
                long id = _world.GetEntityId(entity);
                Require(id > previousId, "Group 的演算顺序没有按世界 ID 升序。");
                previousId = id;
                int next = _world.NextRandom();
                if (_world.Frame == 0 && id == 1)
                {
                    Require(next == 1749605806, "首个整数与上游单种子 MT19937 Next 不一致。");
                }

                var delta = new FixedVector3(FixedPoint.FromInt(next % 101), default, default);
                entity.ReplaceComponent(POSITION, new DemoPosition { Value = PositionOf(entity) + delta });
            }

            if (_world.Frame % 2 == 0)
            {
                _world.Context.CreateEntity().AddComponent(POSITION, new DemoPosition());
            }
            else
            {
                // 偶数帧生成的短寿命实体位于有位置的实体末尾。
                _ordered[_ordered.Count - 1].Destroy();
                if (_world.Frame == 1)
                {
                    _world.Context.CreateEntity().AddComponent(POSITION, new DemoPosition());
                }

                _world.Context.CreateEntity().Destroy();
            }

            if (_world.Frame == 7)
            {
                BattleEntity player = FindUnit(_world, _localPlayerId);
                FixedVector3 position = PositionOf(player);
                player.Destroy();
                SpawnUnit(_world, _localPlayerId, position);
            }
        }

        /// <summary>统计旧系统树卸载。</summary>
        public void TearDown()
        {
            _onTearDown();
        }
    }

    private sealed class DemoPosition : IComponent
    {
        internal FixedVector3 Value;
    }

    private sealed class DemoRotation : IComponent
    {
        internal FixedQuaternion Value;
    }

    private sealed class DemoPlayer : IComponent
    {
        internal long Id;
    }

    private sealed class DemoInput : IComponent
    {
        internal PlayerFrameInput Value;
    }
}
