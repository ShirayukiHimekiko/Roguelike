using System;
using System.Collections.Generic;
using System.IO;
using Entitas;

namespace GameLogic
{
    /// <summary>持有当局 Entitas 世界、确定性状态和系统树。</summary>
    public sealed class LockstepWorld
    {
        private readonly SnapshotComponentCodecs _components;
        private readonly Systems _systems;
        private readonly Dictionary<BattleEntity, long> _entityIds = new Dictionary<BattleEntity, long>();
        private readonly SortedDictionary<long, BattleEntity> _entities = new SortedDictionary<long, BattleEntity>();
        private readonly Comparison<BattleEntity> _compareEntityIds;
        private readonly uint _randomSeed;
        private long _lastEntityId;
        private DeterministicRandom _random;
        private bool _finishRequested;

        /// <summary>当前世界的查询和实体创建入口。回放定位会替换整个 Context。</summary>
        public Context<BattleEntity> Context { get; }

        /// <summary>世界下一次待执行的帧号。</summary>
        public int Frame { get; private set; }

        /// <summary>由开局数据或帧前快照创建世界，随后装配系统树。</summary>
        internal LockstepWorld(IReadOnlyList<long> playerIds, uint randomSeed, LockstepWorldSetup setup,
            WorldSnapshot snapshot)
        {
            _randomSeed = randomSeed;
            Context = setup.CreateContext == null ? new BattleContext() : setup.CreateContext();
            _components = new SnapshotComponentCodecs(Context.contextInfo.componentTypes);
            if (setup.RegisterComponents != null)
            {
                setup.RegisterComponents(_components);
            }

            _compareEntityIds = (left, right) => GetEntityId(left).CompareTo(GetEntityId(right));
            Context.OnEntityCreated += OnEntityCreated;
            Context.OnEntityWillBeDestroyed += OnEntityWillBeDestroyed;

            if (snapshot != null)
            {
                ReadSnapshot(snapshot);
            }
            else if (setup.InitializeWorld != null)
            {
                setup.InitializeWorld(this, playerIds);
            }

            _systems = setup.CreateSystems == null ? new Systems() : setup.CreateSystems(this);
            _systems.Initialize();
        }

        /// <summary>取实体在本局中不复用、可随快照恢复的 ID。</summary>
        public long GetEntityId(BattleEntity entity)
        {
            return _entityIds[entity];
        }

        /// <summary>用世界 ID 查找当前仍存活的实体。</summary>
        public bool TryGetEntity(long id, out BattleEntity entity)
        {
            return _entities.TryGetValue(id, out entity);
        }

        /// <summary>按世界 ID 升序填充当前 Group 的副本，供依赖更新顺序的系统使用。</summary>
        public void GetEntitiesInOrder(IGroup<BattleEntity> group, List<BattleEntity> buffer)
        {
            group.GetEntities(buffer);
            buffer.Sort(_compareEntityIds);
        }

        /// <summary>推进世界专有的整数随机序列。</summary>
        public int NextRandom()
        {
            if (_random == null)
            {
                _random = new DeterministicRandom(_randomSeed);
            }

            return _random.Next();
        }

        /// <summary>为新实体登记当局递增的世界 ID。</summary>
        private void OnEntityCreated(IContext context, IEntity entity)
        {
            long id = ++_lastEntityId;
            var battleEntity = (BattleEntity)entity;
            _entityIds.Add(battleEntity, id);
            _entities.Add(id, battleEntity);
        }

        /// <summary>将被销毁的实体从世界索引移除。</summary>
        private void OnEntityWillBeDestroyed(IContext context, IEntity entity)
        {
            var battleEntity = (BattleEntity)entity;
            long id = _entityIds[battleEntity];
            _entityIds.Remove(battleEntity);
            _entities.Remove(id);
        }

        /// <summary>请求在当前帧执行和清理全部完成后自然结束。同帧请求会合并。</summary>
        public void RequestFinish()
        {
            _finishRequested = true;
        }

        /// <summary>读取并清除本帧的结束请求。只由房间在帧后调用。</summary>
        internal bool ConsumeFinishRequest()
        {
            bool requested = _finishRequested;
            _finishRequested = false;
            return requested;
        }

        /// <summary>执行并清理一帧，再推进世界帧号。</summary>
        internal void Tick()
        {
            _systems.Execute();
            _systems.Cleanup();
            Frame++;
        }

        /// <summary>按世界 ID 捕获本帧演算前的实体与确定性状态。</summary>
        internal WorldSnapshot CaptureSnapshot()
        {
            using var stream = new MemoryStream();
            using var writer = new BinaryWriter(stream);
            writer.Write(Frame);
            writer.Write(_lastEntityId);
            writer.Write(_random != null);
            if (_random != null)
            {
                _random.Write(writer);
            }

            writer.Write(_entities.Count);
            foreach (KeyValuePair<long, BattleEntity> pair in _entities)
            {
                writer.Write(pair.Key);
                _components.Write(writer, pair.Value);
            }

            return new WorldSnapshot(stream.ToArray());
        }

        /// <summary>在新的 Context 中按快照创建实体，恢复已分配过的最大 ID。</summary>
        private void ReadSnapshot(WorldSnapshot snapshot)
        {
            using var stream = new MemoryStream(snapshot.Data);
            using var reader = new BinaryReader(stream);
            Frame = reader.ReadInt32();
            long lastEntityId = reader.ReadInt64();
            if (reader.ReadBoolean())
            {
                _random = new DeterministicRandom(reader);
            }

            int count = reader.ReadInt32();
            for (int index = 0; index < count; index++)
            {
                // 还原实际 ID。被删除实体留下的空洞并不重新分配。
                _lastEntityId = reader.ReadInt64() - 1;
                _components.Read(reader, Context.CreateEntity());
            }

            _lastEntityId = lastEntityId;
        }

        /// <summary>拆除系统并释放当局实体。</summary>
        internal void Release()
        {
            _systems.DeactivateReactiveSystems();
            _systems.TearDown();
            Context.DestroyAllEntities();
            Context.OnEntityCreated -= OnEntityCreated;
            Context.OnEntityWillBeDestroyed -= OnEntityWillBeDestroyed;
        }
    }
}
