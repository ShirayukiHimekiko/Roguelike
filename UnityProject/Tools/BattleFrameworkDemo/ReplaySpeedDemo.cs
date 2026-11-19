using System;
using System.Collections.Generic;
using System.Reflection;
using System.Threading.Tasks;
using Entitas;
using GameLogic;
#if !BATTLE_STANDALONE
using UnityEditor;
#endif

/// <summary>使用同一组断言验收 Unity 和独立宿主中的回放倍速。</summary>
public static class ReplaySpeedDemo
{
    private const BindingFlags INSTANCE_INTERNAL = BindingFlags.Instance | BindingFlags.NonPublic;

#if BATTLE_STANDALONE
    /// <summary>在独立宿主中验收房间的倍速和帧序。</summary>
    public static void Main()
    {
        Console.WriteLine(RunChecks());
    }
#else
    /// <summary>在 Unity 中用独立房间验收，不占用正式战斗流程。</summary>
    public static Task<string> Run()
    {
        Require(EditorApplication.isPlaying, "请先在 main 场景进入 Play Mode。");
        return Task.FromResult(RunChecks());
    }
#endif

    /// <summary>以可控到期时间验收回放切速、追帧和末帧停止。</summary>
    private static string RunChecks()
    {
        const int frameCount = 40;
        var executed = new List<(int Frame, int Sample)>();
        var setup = new LockstepWorldSetup(createSystems: world => new Systems().Add(new ReplayProbeSystem(world, executed)));
        PropertyInfo clockProperty = typeof(Room).GetProperty("Clock", INSTANCE_INTERNAL);
        Room room = RoomSystem.CreateLocal(0, Array.Empty<long>(), worldSetup: setup, randomSeed: 123);

        try
        {
            Enter(room);
            while (room.CurrentFrame < frameCount - 1)
            {
                room.Update(long.MaxValue);
            }

            Replay recording = room.Replay;
            var expectedTrace = executed.ToArray();
            var expectedHashes = new ulong[frameCount];
            Require(recording.FrameCount == frameCount && expectedTrace.Length == frameCount, "录制帧数不符。");
            for (int frame = 0; frame < frameCount; frame++)
            {
                Require(expectedTrace[frame].Frame == frame && room.TryGetFrameHash(frame, out expectedHashes[frame]),
                    $"录制第 {frame} 帧缺少演算或指纹。");
            }

            room.Release();
            executed.Clear();
            room = RoomSystem.CreateReplay(recording, worldSetup: setup);
            Enter(room);
            object clock = clockProperty.GetValue(room);
            var deadline = (Func<int, long>)clock.GetType().GetMethod("FrameTime", INSTANCE_INTERNAL)
                .CreateDelegate(typeof(Func<int, long>), clock);

            foreach ((int speed, int interval) in new[] { (1, 50), (2, 25), (4, 12), (8, 6), (1, 50) })
            {
                int anchor = room.CurrentFrame;
                long anchorTime = deadline(anchor);
                Require(room.ChangeReplaySpeed(speed) && room.ReplaySpeed == speed && deadline(anchor) == anchorTime,
                    $"{speed}× 切速改变了已执行帧的时钟锚点。");

                for (int offset = 1; offset <= 2; offset++)
                {
                    int frame = anchor + offset;
                    long due = deadline(frame);
                    Require(due == anchorTime + offset * interval, $"{speed}× 的第 {frame} 帧间隔不符。");
                    room.Update(due - 1);
                    Require(room.CurrentFrame == frame - 1 && executed.Count == frame, $"第 {frame} 帧提前执行。");
                    room.Update(due);
                    Require(room.CurrentFrame == frame && executed.Count == frame + 1, $"第 {frame} 帧到期后未执行一次。");
                }
            }

            // 一次迟到轮询应补跑多个已到期帧，但不能越过录像尾帧。
            room.Update(long.MaxValue);
            room.Update(long.MaxValue);
            Require(room.CurrentFrame == frameCount - 1 && room.ReplayDivergedFrame == -1 && executed.Count == frameCount,
                "回放追帧没有恰好停在末帧，或发生了分歧。");
            for (int frame = 0; frame < frameCount; frame++)
            {
                Require(executed[frame] == expectedTrace[frame] && room.TryGetFrameHash(frame, out ulong hash) &&
                    hash == expectedHashes[frame], $"第 {frame} 帧的帧序、随机样本或指纹不一致。");
            }

            return $"PASS · {frameCount} 帧；1× → 2× → 4× → 8× → 1×；到期、追帧、末帧、逐帧指纹及随机样本一致";
        }
        finally
        {
            room.Release();
        }
    }

    /// <summary>建立世界和当局时钟，再用确定的到期点推进首帧。</summary>
    private static void Enter(Room room)
    {
        room.InitializeWorld();
        room.Start(FixedTimeCounter.ReadMilliseconds());
        object clock = typeof(Room).GetProperty("Clock", INSTANCE_INTERNAL).GetValue(room);
        long due = (long)clock.GetType().GetMethod("FrameTime", INSTANCE_INTERNAL).Invoke(clock, new object[] { 0 });
        room.Update(due);
    }

    private sealed class ReplayProbeSystem : IExecuteSystem
    {
        private readonly LockstepWorld _world;
        private readonly List<(int Frame, int Sample)> _executed;

        public ReplayProbeSystem(LockstepWorld world, List<(int Frame, int Sample)> executed)
        {
            _world = world;
            _executed = executed;
        }

        /// <summary>记录系统实际执行的帧及对应的确定性随机样本。</summary>
        public void Execute()
        {
            _executed.Add((_world.Frame, _world.NextRandom()));
        }
    }

    /// <summary>验收条件失败时停止并报告第一个问题。</summary>
    private static void Require(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }
}
