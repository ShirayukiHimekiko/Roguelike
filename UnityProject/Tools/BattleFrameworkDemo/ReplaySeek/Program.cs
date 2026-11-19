using System;
using System.Collections.Generic;
using System.Diagnostics;
using Entitas;
using GameLogic;

var trace = new List<int>();
const long player = 1;
var setup = new LockstepWorldSetup(
    createSystems: world => new Systems().Add(new Probe(world, trace)),
    applyInputs: (world, inputs) =>
    {
        Require(inputs.TryGetInput(player, out PlayerFrameInput input) && input.Button == Math.Max(0, world.Frame),
            $"Wrong input at frame {world.Frame}");
    });
Room room = RoomSystem.CreateLocal(player, new[] { player }, worldSetup: setup);
Enter();
const int lastFrame = 1205;
var hashes = new ulong[lastFrame + 1];
Require(room.TryGetFrameHash(0, out hashes[0]), "Missing live frame 0 hash");
while (room.CurrentFrame < lastFrame)
{
    Require(room.SubmitLocalInput(new PlayerFrameInput(default, room.CurrentFrame + 1)), "Input not accepted");
    room.Update(long.MaxValue);
    Require(room.TryGetFrameHash(room.CurrentFrame, out hashes[room.CurrentFrame]), "Missing live hash");
}
Replay recording = room.Replay;
room.Release();

room = RoomSystem.CreateReplay(recording, worldSetup: setup);
Enter();
Measure(100, 1, true);
Measure(105, 101, true);
Measure(1200, 1200, false);
Measure(1199, 0, false, true);
LockstepWorld previousWorld = room.World;
Require(room.JumpReplay(6), "Backward seek not accepted");
room.Update(FixedTimeCounter.ReadMilliseconds() - 6);
Require(room.CurrentFrame == 0 && room.ReplaySeekTargetFrame == 6 && room.World != previousWorld,
    "Backward seek did not yield after restoring");
Measure(3, 1, true);
Require(room.ChangeReplaySpeed(8), "Set speed failed");
Require(room.JumpReplay(1203) && room.JumpReplay(1202), "Replacing seek failed");
room.Update(long.MaxValue);
Require(room.CurrentFrame == 1202 && room.ReplaySeekTargetFrame == -1 && room.Clock.Interval == 6,
    "Latest target, end frame or replay rate was lost");
long due = room.Clock.FrameTime(1203);
room.Update(due - 1);
Require(room.CurrentFrame == 1202, "Playback resumed before the next deadline");
room.Update(due);
Require(room.CurrentFrame == 1203, "Playback did not resume at the next deadline");
room.Update(long.MaxValue);
Require(room.CurrentFrame == lastFrame && room.TryGetFrameHash(lastFrame, out ulong tailHash) &&
    tailHash == hashes[lastFrame], "Playback overshot or did not match the last frame");
room.Release();

RecordedFrame saved = recording.Frames[3];
recording.Frames[3] = new RecordedFrame(saved.Inputs, saved.Hash ^ 1UL);
trace.Clear();
room = RoomSystem.CreateReplay(recording, worldSetup: setup);
Enter();
foreach (bool duringSeek in new[] { false, true })
{
    if (duringSeek)
    {
        Require(room.JumpReplay(3), "Faulted seek was not accepted");
    }
    room.Update(long.MaxValue);
    room.Update(long.MaxValue);
    Require(room.ReplayDivergedFrame == 3 && room.CurrentFrame == 2 && room.World.Frame == 3 &&
        trace[^1] == 2 && !trace.Contains(3) && room.ReplaySeekTargetFrame == -1 &&
        !room.TryGetFrameHash(3, out _) && !room.TryGetFrameInput(3, player, out _),
        "Diverged frame was executed, committed or remained pending");
    LockstepWorld old = room.World;
    Measure(2, 0, false);
    Require(room.World != old && room.ReplayDivergedFrame == -1, "Recovery did not rebuild the halted world");
    Console.WriteLine($"mismatch during {(duringSeek ? "seek" : "play")}: frame 3 blocked; recovery to 2 passed");
}
room.Release();
VerifyNaturalFinishAndTerminalHash();
Console.WriteLine("PASS: seek, budget, frame hashes, resumed playback, recovery and terminal hash");

void Enter()
{
    room.InitializeWorld();
    room.Start(FixedTimeCounter.ReadMilliseconds());
    room.Update(room.Clock.FrameTime(0));
}

void Measure(int target, int first, bool reuse, bool forceBudget = false)
{
    int previous = room.CurrentFrame;
    LockstepWorld old = room.World;
    int previousRevision = room.WorldRevision;
    trace.Clear();
    Stopwatch watch = Stopwatch.StartNew();
    Require(room.JumpReplay(target) && trace.Count == 0 && room.CurrentFrame == previous,
        "Seek request ran frames synchronously");
    double requestMs = watch.Elapsed.TotalMilliseconds;
    int polls = 0;
    double maxPollMs = 0;
    while (room.ReplaySeekTargetFrame >= 0)
    {
        watch.Restart();
        long now = FixedTimeCounter.ReadMilliseconds();
        room.Update(forceBudget && polls == 0 ? now - 6 : now);
        maxPollMs = Math.Max(maxPollMs, watch.Elapsed.TotalMilliseconds);
        polls++;
        if (forceBudget && polls == 1)
        {
            Require(trace.Count == 1 && room.ReplaySeekTargetFrame == target, "Seek ignored the expired polling budget");
        }
        Require(polls <= target - first + 1 && room.CurrentFrame <= target, "Seek stalled or went past target");
    }

    Require(room.CurrentFrame == target && room.World.Frame == target + 1 && (old == room.World) == reuse &&
        room.WorldRevision == previousRevision + (reuse ? 0 : 1) &&
        trace.Count == target - first + 1, "Wrong seek end state, world or tick count");
    for (int i = 0; i < trace.Count; i++)
    {
        int frame = first + i;
        Require(trace[i] == frame && room.TryGetFrameHash(frame, out ulong hash) && hash == hashes[frame],
            $"Seek trace or hash mismatch at frame {frame}");
    }
    Console.WriteLine($"{previous}->{target}: request={requestMs:F3} ms, max poll={maxPollMs:F3} ms, polls={polls}, ticks={trace.Count}, reused={reuse}");
}

void VerifyNaturalFinishAndTerminalHash()
{
    var cleanupFrames = new List<int>();
    var matching = new LockstepWorldSetup(
        createSystems: world => new Systems().Add(new FinishProbe(world, cleanupFrames, false)));
    var differentTail = new LockstepWorldSetup(
        createSystems: world => new Systems().Add(new FinishProbe(world, cleanupFrames, true)));
    Room live = RoomSystem.CreateLocal(0, Array.Empty<long>(), worldSetup: matching);
    live.InitializeWorld();
    live.Start(0);
    for (int poll = 0; poll < FinishProbe.LAST_FRAME + 3; poll++)
    {
        live.Update(long.MaxValue);
    }

    Require(live.IsFinished && live.CurrentFrame == FinishProbe.LAST_FRAME &&
        live.Replay.FrameCount == FinishProbe.LAST_FRAME + 1 &&
        cleanupFrames.Count == FinishProbe.LAST_FRAME + 1 && cleanupFrames[^1] == FinishProbe.LAST_FRAME,
        "Natural finish skipped cleanup, committed twice or allowed another frame");
    Replay sealedReplay = live.SealReplay();
    Require(sealedReplay.TerminalHash.HasValue && sealedReplay == live.SealReplay(),
        "Natural finish did not seal the final world");
    live.Release();

    foreach (bool duringSeek in new[] { false, true })
    {
        foreach (bool diverges in new[] { false, true })
        {
            cleanupFrames.Clear();
            Room playback = RoomSystem.CreateReplay(sealedReplay, diverges ? differentTail : matching);
            playback.InitializeWorld();
            playback.Start(0);
            if (duringSeek)
            {
                Require(playback.JumpReplay(FinishProbe.LAST_FRAME), "Tail seek was rejected");
            }

            playback.Update(long.MaxValue);
            playback.Update(long.MaxValue);
            var expected = diverges ? ReplayPlaybackStatus.TerminalDiverged : ReplayPlaybackStatus.Completed;
            Require(playback.PlaybackStatus == expected && playback.CurrentFrame == FinishProbe.LAST_FRAME &&
                playback.World.Frame == FinishProbe.LAST_FRAME + 1 && playback.ReplaySeekTargetFrame == -1 &&
                !playback.IsFinished && cleanupFrames.Count == FinishProbe.LAST_FRAME + 1 &&
                playback.TryGetFrameHash(FinishProbe.LAST_FRAME, out ulong preTickHash) &&
                preTickHash == sealedReplay.Frames[FinishProbe.LAST_FRAME].Hash,
                "Replay did not distinguish terminal divergence from a pre-frame stop");
            playback.Release();
        }
    }
}

void Require(bool condition, string message)
{
    if (!condition)
    {
        throw new InvalidOperationException(message);
    }
}

internal sealed class Probe : IExecuteSystem
{
    private readonly LockstepWorld _world;
    private readonly List<int> _trace;

    internal Probe(LockstepWorld world, List<int> trace)
    {
        _world = world;
        _trace = trace;
    }

    public void Execute()
    {
        _trace.Add(_world.Frame);
        _world.NextRandom();
    }
}

internal sealed class FinishProbe : IExecuteSystem, ICleanupSystem
{
    internal const int LAST_FRAME = 2;

    private readonly LockstepWorld _world;
    private readonly List<int> _cleanupFrames;
    private readonly bool _differentTail;

    internal FinishProbe(LockstepWorld world, List<int> cleanupFrames, bool differentTail)
    {
        _world = world;
        _cleanupFrames = cleanupFrames;
        _differentTail = differentTail;
    }

    public void Execute()
    {
        if (_world.Frame == LAST_FRAME)
        {
            _world.RequestFinish();
            _world.RequestFinish();
        }
    }

    public void Cleanup()
    {
        _cleanupFrames.Add(_world.Frame);
        if (_world.Frame == LAST_FRAME && _differentTail)
        {
            _world.NextRandom();
        }
    }
}
