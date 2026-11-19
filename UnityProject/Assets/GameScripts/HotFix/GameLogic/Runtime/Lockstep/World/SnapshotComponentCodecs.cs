using System;
using System.Collections.Generic;
using System.IO;
using Entitas;

namespace GameLogic
{
    /// <summary>定义确定性组件的稳定录像键和字段编码。</summary>
    public sealed class SnapshotComponentCodecs
    {
        private readonly SortedDictionary<ushort, ComponentCodec> _codecs = new SortedDictionary<ushort, ComponentCodec>();
        private readonly HashSet<int> _registeredIndices = new HashSet<int>();
        private readonly Type[] _componentTypes;

        /// <summary>由当前 Context 的组件类型表解析 Entitas 下标。</summary>
        internal SnapshotComponentCodecs(Type[] componentTypes)
        {
            _componentTypes = componentTypes;
        }

        /// <summary>开局或恢复时登记当前 Context 的组件，录像键不随组件下标变化。</summary>
        /// <param name="key">持久化键，已发布的键不得改作其他类型。</param>
        /// <param name="write">按确定顺序写入该组件的逻辑字段。</param>
        /// <param name="read">依相同顺序重建组件。</param>
        public void Register<T>(ushort key, Action<BinaryWriter, T> write, Func<BinaryReader, T> read)
            where T : IComponent
        {
            int index = Array.IndexOf(_componentTypes, typeof(T));
            if (index < 0 || _registeredIndices.Contains(index))
            {
                throw new ArgumentException($"{typeof(T).Name} 不属于当前战斗 Context 或已登记。");
            }

            _codecs.Add(key, new ComponentCodec(index, (writer, component) => write(writer, (T)component),
                reader => read(reader)));
            _registeredIndices.Add(index);
        }

        /// <summary>按稳定录像键保存实际挂载的组件。</summary>
        internal void Write(BinaryWriter writer, BattleEntity entity)
        {
            int count = entity.GetComponentIndices().Length;
            writer.Write(count);
            foreach (KeyValuePair<ushort, ComponentCodec> pair in _codecs)
            {
                ComponentCodec codec = pair.Value;
                if (entity.HasComponent(codec.Index))
                {
                    writer.Write(pair.Key);
                    codec.Write(writer, entity.GetComponent(codec.Index));
                    count--;
                }
            }

            if (count != 0)
            {
                throw new InvalidOperationException("战斗实体包含未登记快照编码的组件。");
            }
        }

        /// <summary>用稳定录像键恢复实际挂载的组件。</summary>
        internal void Read(BinaryReader reader, BattleEntity entity)
        {
            int count = reader.ReadInt32();
            for (int index = 0; index < count; index++)
            {
                ComponentCodec codec = _codecs[reader.ReadUInt16()];
                entity.AddComponent(codec.Index, codec.Read(reader));
            }
        }

        private readonly struct ComponentCodec
        {
            internal readonly int Index;
            internal readonly Action<BinaryWriter, IComponent> Write;
            internal readonly Func<BinaryReader, IComponent> Read;

            /// <summary>关联当前组件下标及其读写方法。</summary>
            internal ComponentCodec(int index, Action<BinaryWriter, IComponent> write, Func<BinaryReader, IComponent> read)
            {
                Index = index;
                Write = write;
                Read = read;
            }
        }
    }
}
