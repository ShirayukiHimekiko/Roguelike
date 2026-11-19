using System;
using System.Buffers.Binary;
using System.IO;
using Cysharp.Threading.Tasks;

namespace GameLogic
{
    /// <summary>版本化的单机录像文件。数据按玩家输入槽和帧号排列。</summary>
    public static partial class ClientHelper
    {
        private const uint MAGIC = 0x31525442;
        private const int LEGACY_REPLAY_VERSION = 3;
        private const int REPLAY_VERSION = 4;
        private const int HEADER_SIZE = 28;
        private const int INPUT_SIZE = 20;

        /// <summary>异步写入临时文件，写完后替换上一次录像。</summary>
        internal static async UniTask SaveReplayAsync(string path, Replay recording)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            string temporaryPath = path + ".tmp";
            await File.WriteAllBytesAsync(temporaryPath, Encode(recording));
            if (File.Exists(path))
            {
                File.Replace(temporaryPath, path, null);
            }
            else
            {
                File.Move(temporaryPath, path);
            }
        }

        /// <summary>读入最后一局录像。文件不存在时返回空。</summary>
        internal static async UniTask<Replay> LoadReplayAsync(string path)
        {
            byte[] data;
            try
            {
                data = await File.ReadAllBytesAsync(path);
            }
            catch (FileNotFoundException)
            {
                return null;
            }
            catch (DirectoryNotFoundException)
            {
                return null;
            }

            return Decode(data);
        }

        /// <summary>依次编码参与玩家、帧输入、周期快照和 V4 的终局指纹。</summary>
        internal static byte[] Encode(Replay recording)
        {
            if (recording.FrameCount == 0 || !recording.TerminalHash.HasValue)
            {
                throw new InvalidDataException("录像还没有可保存的终局状态。");
            }

            using var stream = new MemoryStream();
            using var writer = new BinaryWriter(stream);
            writer.Write(MAGIC);
            writer.Write(REPLAY_VERSION);
            writer.Write(recording.LocalPlayerId);
            writer.Write(recording.RandomSeed);
            writer.Write(recording.PlayerIds.Count);
            writer.Write(recording.FrameCount);
            foreach (long playerId in recording.PlayerIds)
            {
                writer.Write(playerId);
            }

            foreach (RecordedFrame frame in recording.Frames)
            {
                writer.Write(frame.Hash);
                foreach (PlayerFrameInput input in frame.Inputs)
                {
                    writer.Write(input.Direction.X.RawValue);
                    writer.Write(input.Direction.Y.RawValue);
                    writer.Write(input.Button);
                }
            }

            foreach (WorldSnapshot snapshot in recording.Checkpoints)
            {
                writer.Write(snapshot.Data.Length);
                writer.Write(snapshot.Data);
            }

            writer.Write(recording.TerminalHash.Value);
            writer.Write(StableBytesHash.Compute(stream.GetBuffer().AsSpan(0, (int)stream.Length)));
            return stream.ToArray();
        }

        /// <summary>在读取文件入口校验版本、长度和检查点归属。</summary>
        internal static Replay Decode(byte[] data)
        {
            if (data.Length < HEADER_SIZE + sizeof(ulong))
            {
                throw new InvalidDataException("录像头不完整。");
            }

            using var stream = new MemoryStream(data);
            using var reader = new BinaryReader(stream);
            uint magic = reader.ReadUInt32();
            int version = reader.ReadInt32();
            if (magic != MAGIC || (version != LEGACY_REPLAY_VERSION && version != REPLAY_VERSION))
            {
                throw new InvalidDataException("录像格式或版本不匹配。");
            }

            bool hasTerminalHash = version == REPLAY_VERSION;
            long localPlayerId = reader.ReadInt64();
            uint randomSeed = reader.ReadUInt32();
            int playerCount = reader.ReadInt32();
            int frameCount = reader.ReadInt32();
            if (playerCount < 0 || playerCount > (data.Length - HEADER_SIZE) / sizeof(long) ||
                frameCount < 0 || frameCount > (data.Length - HEADER_SIZE) / sizeof(ulong) ||
                (hasTerminalHash && frameCount == 0))
            {
                throw new InvalidDataException("录像的玩家或帧数量无效。");
            }

            int checkpointCount = (int)((frameCount + (long)Replay.CHECKPOINT_INTERVAL - 1) /
                Replay.CHECKPOINT_INTERVAL);
            long minimumPayloadLength = HEADER_SIZE + (long)playerCount * sizeof(long) +
                frameCount * (sizeof(ulong) + (long)playerCount * INPUT_SIZE) +
                (long)checkpointCount * (sizeof(int) + WorldSnapshot.HEADER_SIZE);
            int checksumOffset = data.Length - sizeof(ulong);
            int framesAndSnapshotsEnd = checksumOffset - (hasTerminalHash ? sizeof(ulong) : 0);
            if (framesAndSnapshotsEnd < minimumPayloadLength)
            {
                throw new InvalidDataException("录像数据长度不匹配。");
            }

            ulong checksum = BinaryPrimitives.ReadUInt64LittleEndian(data.AsSpan(checksumOffset));
            if (StableBytesHash.Compute(data.AsSpan(0, checksumOffset)) != checksum)
            {
                throw new InvalidDataException("录像校验值不匹配。");
            }

            var playerIds = new long[playerCount];
            for (int slot = 0; slot < playerCount; slot++)
            {
                playerIds[slot] = reader.ReadInt64();
            }

            var recording = new Replay(localPlayerId, Array.AsReadOnly(playerIds), randomSeed);
            for (int frame = 0; frame < frameCount; frame++)
            {
                ulong hash = reader.ReadUInt64();
                var inputs = new PlayerFrameInput[playerCount];
                for (int slot = 0; slot < playerCount; slot++)
                {
                    var direction = new FixedVector2(FixedPoint.FromRaw(reader.ReadInt64()),
                        FixedPoint.FromRaw(reader.ReadInt64()));
                    inputs[slot] = new PlayerFrameInput(direction, reader.ReadInt32());
                }

                recording.Frames.Add(new RecordedFrame(inputs, hash));
            }

            for (int index = 0; index < checkpointCount; index++)
            {
                int frame = index * Replay.CHECKPOINT_INTERVAL;
                int length = reader.ReadInt32();
                long remainingHeaders = (long)(checkpointCount - index - 1) *
                    (sizeof(int) + WorldSnapshot.HEADER_SIZE);
                if (length < WorldSnapshot.HEADER_SIZE ||
                    length > framesAndSnapshotsEnd - stream.Position - remainingHeaders)
                {
                    throw new InvalidDataException("录像检查点长度无效。");
                }

                var snapshot = new WorldSnapshot(reader.ReadBytes(length));
                if (snapshot.Frame != frame || snapshot.Hash != recording.Frames[frame].Hash)
                {
                    throw new InvalidDataException("录像检查点与记录帧不一致。");
                }

                recording.Checkpoints.Add(snapshot);
            }

            if (stream.Position != framesAndSnapshotsEnd)
            {
                throw new InvalidDataException("录像末尾包含未读取的数据。");
            }

            if (hasTerminalHash)
            {
                recording.TerminalHash = reader.ReadUInt64();
            }

            return recording;
        }
    }
}
