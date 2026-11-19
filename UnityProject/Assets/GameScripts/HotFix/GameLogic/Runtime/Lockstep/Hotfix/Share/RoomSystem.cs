using System;
using System.Collections.Generic;

namespace GameLogic
{
    /// <summary>创建和推进当局，集中维护帧号、快照与世界的生命周期。</summary>
    public static class RoomSystem
    {
        /// <summary>创建尚未启动的本地权威房间，并冻结玩家的输入槽顺序。</summary>
        public static Room CreateLocal(long localPlayerId, IReadOnlyList<long> playerIds,
            LockstepWorldSetup worldSetup = null, uint randomSeed = 5489u)
        {
            if (playerIds == null)
            {
                throw new ArgumentNullException(nameof(playerIds));
            }

            var ids = new long[playerIds.Count];
            for (int slot = 0; slot < ids.Length; slot++)
            {
                ids[slot] = playerIds[slot];
            }

            var replay = new Replay(localPlayerId, Array.AsReadOnly(ids), randomSeed);
            return Create(replay, worldSetup, false);
        }

        /// <summary>用既有录像建立尚未启动的回放房间。</summary>
        public static Room CreateReplay(Replay replay, LockstepWorldSetup worldSetup = null)
        {
            if (replay == null)
            {
                throw new ArgumentNullException(nameof(replay));
            }

            if (replay.FrameCount == 0)
            {
                throw new ArgumentException("录像没有可回放的帧。", nameof(replay));
            }

            return Create(replay, worldSetup, true);
        }

        /// <summary>为两种模式建立一致的玩家 ID 到输入槽的映射。</summary>
        private static Room Create(Replay replay, LockstepWorldSetup worldSetup, bool isReplay)
        {
            IReadOnlyList<long> playerIds = replay.PlayerIds;
            var slots = new Dictionary<long, int>(playerIds.Count);
            int localPlayerSlot = -1;
            for (int slot = 0; slot < playerIds.Count; slot++)
            {
                long playerId = playerIds[slot];
                if (!slots.TryAdd(playerId, slot))
                {
                    throw new ArgumentException("玩家 ID 重复。", nameof(replay));
                }

                if (playerId == replay.LocalPlayerId)
                {
                    localPlayerSlot = slot;
                }
            }

            if (playerIds.Count != 0 && localPlayerSlot < 0)
            {
                throw new ArgumentException("玩家列表中缺少本地玩家。", nameof(replay));
            }

            return new Room(replay, slots, localPlayerSlot, worldSetup ?? new LockstepWorldSetup(), isReplay);
        }

        /// <summary>实时局建立初始世界，回放局从第零帧检查点恢复。</summary>
        public static void InitializeWorld(this Room room)
        {
            WorldSnapshot snapshot = room.IsReplay ? room.Replay.Checkpoints[0] : null;
            room.World = CreateWorld(room, snapshot);
            room.WorldRevision++;
        }

        /// <summary>在世界就绪后锚定第零帧，并为当局选定一次更新入口。</summary>
        public static void Start(this Room room, long nowMs)
        {
            room.Clock = new FixedTimeCounter(nowMs);
            if (room.IsReplay)
            {
                room.UpdateFrame = ReplayUpdaterSystem.Update;
            }
            else
            {
                room.UpdateFrame = LocalFrameUpdater.Update;
            }
        }

        /// <summary>由宿主使用同一单调时钟轮询当局。自然结束后停止实时推进。</summary>
        public static void Update(this Room room, long nowMs)
        {
            if (!room.IsFinished)
            {
                room.UpdateFrame?.Invoke(room, nowMs);
            }
        }

        /// <summary>提交本地玩家下一帧的输入。准备中也可提交，回放输入来自录像。</summary>
        public static bool SubmitLocalInput(this Room room, PlayerFrameInput input)
        {
            if (room.FrameBuffer == null || room.IsReplay || room.IsFinished || room.LocalPlayerSlot < 0)
            {
                return false;
            }

            room.FrameBuffer.Submit(room.LocalPlayerSlot, input);
            return true;
        }

        /// <summary>投递输入、保存帧前状态并执行一帧。回放指纹分歧时返回 false。</summary>
        internal static bool Tick(this Room room, int frame, OneFrameInputs inputs)
        {
            if (!room.IsReplay)
            {
                room.AuthorityFrame = frame;
            }

            room.WorldSetup.ApplyInputs?.Invoke(room.World, inputs);
            WorldSnapshot snapshot = room.World.CaptureSnapshot();
            if (room.IsReplay)
            {
                if (snapshot.Hash != room.Replay.Frames[frame].Hash)
                {
                    return false;
                }

                room.FrameBuffer.Store(frame, inputs);
                room.AuthorityFrame = frame;
            }
            else
            {
                room.Replay.Record(inputs, snapshot);
            }

            room.FrameBuffer.StoreSnapshot(snapshot);
            room.World.Tick();
            if (room.World.ConsumeFinishRequest() && !room.IsReplay)
            {
                room.IsFinished = true;
            }

            return true;
        }

        /// <summary>提交一个从帧前检查点恢复的世界。下一次推进会执行检查点这一帧。</summary>
        internal static void RestoreCheckpoint(this Room room, WorldSnapshot checkpoint)
        {
            var history = new FrameBuffer(room.PlayerSlots);
            LockstepWorld nextWorld = CreateWorld(room, checkpoint);
            LockstepWorld previousWorld = room.World;
            room.World = nextWorld;
            room.AuthorityFrame = checkpoint.Frame - 1;
            room.FrameBuffer = history;
            room.WorldRevision++;
            previousWorld.Release();
        }

        /// <summary>为当前房间装配新世界，已有快照时直接恢复其状态。</summary>
        private static LockstepWorld CreateWorld(Room room, WorldSnapshot snapshot)
        {
            return new LockstepWorld(room.Replay.PlayerIds, room.Replay.RandomSeed, room.WorldSetup, snapshot);
        }

        /// <summary>在释放有帧的实时局之前封存一次末帧执行后的指纹。</summary>
        public static Replay SealReplay(this Room room)
        {
            if (room.IsReplay || room.Replay.FrameCount == 0)
            {
                return null;
            }

            room.Replay.TerminalHash ??= room.World.CaptureSnapshot().Hash;
            return room.Replay;
        }

        /// <summary>读取仍在历史中的已封存输入。</summary>
        public static bool TryGetFrameInput(this Room room, int frame, long playerId, out PlayerFrameInput input)
        {
            if (room.FrameBuffer != null && room.PlayerSlots.TryGetValue(playerId, out int slot))
            {
                return room.FrameBuffer.TryGetInput(frame, slot, out input);
            }

            input = default;
            return false;
        }

        /// <summary>读取仍在历史中的帧前状态指纹。</summary>
        public static bool TryGetFrameHash(this Room room, int frame, out ulong hash)
        {
            if (room.FrameBuffer != null && room.FrameBuffer.TryGetSnapshot(frame, out WorldSnapshot snapshot))
            {
                hash = snapshot.Hash;
                return true;
            }

            hash = 0;
            return false;
        }

        /// <summary>停止调度，释放当局世界与环形帧历史。</summary>
        public static void Release(this Room room)
        {
            room.Clock = null;
            room.UpdateFrame = null;
            room.World?.Release();
            room.World = null;
            room.FrameBuffer = null;
            room.AuthorityFrame = -1;
            if (room.ReplayUpdater != null)
            {
                room.ReplayUpdater.SeekTargetFrame = -1;
                room.ReplayUpdater.PrepareSeek = false;
            }
        }
    }
}
