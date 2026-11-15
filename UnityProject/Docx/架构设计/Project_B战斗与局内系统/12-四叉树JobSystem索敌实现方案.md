# Project B 四叉树与 Job System 索敌实现方案

评审稿。本方案把四叉树和 Unity Job System 作为首版索敌实现，具体化 [RVO2 移动与索敌方案](11-战斗寻路与索敌实现方案.md) 的候选索引选型。覆盖召唤单位找敌塔、攻击塔与暴露核心找玩家单位。交付结果为稳定目标身份，战斗模块继续负责目标保持、接敌、射程复核和攻击请求。

## 1. 选型与参考实现

**采用数组化二维点区域四叉树。目标按锚点只入一个叶节点，节点用整棵子树的受击盒并集剪枝。批量建树用 Burst IJob，批量选敌用 Burst IJobParallelFor。** 一条查询对应一个请求，执行中只写自己的结果槽位。

| 阅读材料 | 查到的实现 | 本项目采用方式 |
| --- | --- | --- |
| marijnz/NativeQuadtree | AddBulkJob 调用 ClearAndBulkInsert。树根据点的 Morton 编码批量填充，示例 RangeQueryJob 用同一个 Job 和结果列表循环查询。 | 沿用批量建树思路。查询按多个索敌者并行，每个请求只输出一个赢家。首版用稳定四路分区形成连续叶区间，省去全局排序和遍历时扩容。 [建树源码](https://github.com/marijnz/NativeQuadtree/blob/master/Assets/NativeQuadTree.cs#L102) · [Job 源码](https://github.com/marijnz/NativeQuadtree/blob/master/Assets/QuadTreeJobs.cs) |
| bartofzo/NativeTrees | NativeQuadtree 支持点和浮点 AABB。范围遍历调用 visitor，由 visitor 精筛对象边界。跨象限 AABB 可能重复登记，扩展提供去重查询。 | 保留遍历时过滤和归约的做法。索敌树每个目标只登记一次，用子树的定点受击盒并集覆盖跨象限形状。 [插入源码](https://github.com/bartofzo/NativeTrees/blob/main/Packages/NativeTrees/Runtime/Quadtree/NativeQuadtree.cs#L111) · [遍历源码](https://github.com/bartofzo/NativeTrees/blob/main/Packages/NativeTrees/Runtime/Quadtree/NativeQuadtreeRangeQuery.cs) · [去重扩展](https://github.com/bartofzo/NativeTrees/blob/main/Packages/NativeTrees/Runtime/Quadtree/NativeQuadtreeExtensions.cs#L64) |
| CSDN 四叉树案例 | Unity 场景裁剪文章的公开部分演示按层分区。C++ 碰撞案例讨论最大深度、跨区对象和聚团开销。 | 将跨区和聚团纳入本项目回归。文章中的场景规模和性能描述不作为 Project B 数据。 [Unity 场景分区](https://blog.csdn.net/mobilebbki399/article/details/79491544) · [C++ 碰撞案例](https://bbs.csdn.net/weixin_33430573/article/details/100217473) |
| nezix/NeighborSearchGridBurst | 作者用 Jobs 和 Burst 批量完成网格邻域查询。 | 性能对照也使用 Batch Job 和相同定点规则，单独比较索引成本，避免把并行收益误算为四叉树收益。 [网格实现](https://github.com/nezix/NeighborSearchGridBurst) |

## 2. 战场数据与两棵树的生命周期

| 存储 | 字段与有效范围 |
| --- | --- |
| TargetGeometry | 稳定几何槽位、分区锚点、定点受击 AABB。目标只存一条记录。若有多个受击盒，用外包盒做建树边界，叶内对每个盒求距离并取最小值，整目标仍只评一次。首版单盒。 |
| TargetState | 同一个槽位上的 BattleEntityId、Generation、阵营、类别、存活与期限、可索敌资格、权重、塔所属层和方向。每个查询阶段固定业务状态，叠层、保护和资格从编排提供。 |
| QuadNode | ContentBounds、FirstChild、ChildMask 或 LeafStart、LeafCount。ContentBounds 覆盖子树内所有受击盒。非空直接子节点连续，依据 ChildMask 定位。叶区间指向连续 TargetIndex 数组。子象限 q 的槽位为 FirstChild 加上 ChildMask 中低于 q 的置位数。 |
| TargetQuery | 寻敌者 ID/代际、瞄准点、索敌半径平方、可接受目标类别/阵营、方向逐层资格和本次临时排除。空请求批无需建树或调度查询。 |
| TargetResult | 一个请求槽位对应 Found 或 NoTarget，成功时返回目标 ID/代际和选敌排序键。批次包含 BattleId、Tick、Phase、GeometryRevision 和 EligibilityRevision。树内位置只供本批。 |

- **敌塔树**由布局投影生成。准备完成后构建，只有锚点、形状或几何成员集合改变才标脏。仍保留几何槽位的塔在破损后由状态投影标记失去资格，暴露、权重或单纯资格变化只刷新状态。复活身份按最新代际读取。几何重排时同批重建槽位映射，禁止把上版叶索引配到新版状态。若准备阶段缓存塔树，进入战斗时核对几何修订号。
- **移动单位树**在移动提交后按当前单位投影批量重建，供攻击塔与核心查询。无实际索敌请求时可跳过当步建树。创建、离场、传送和半径变化都通过新快照体现。
- **两阶段调用**分别使用 PreMove 和 PostMove。N 步结算破损后，N+1 才使用更新的保护资格。到期单位在开步撤销资格。索敌树、ORCA 邻居和 HitResolver 拥有各自的调用合同。 [战斗编排](00-战斗编排与集成方案.md) · [单位](04-单位实现方案.md) · [建筑](03-建筑实现方案.md)

## 3. 数组四叉树的构建

### 分区和容量

1. 关卡提供覆盖全部合法锚点的根区域。取定点 Raw 整数上的二次幂边长，按 [min, max) 约定包含正式地图的最大合法坐标。中线上的锚点固定归高坐标侧，象限顺序固定。根区域仅用于分区。节点剪枝只看真实 ContentBounds。
2. 每个节点先扫本段目标并合并受击盒，记录锚点最小和最大坐标。若符合叶容量，达到深度或最小边长限制，或锚点完全重合，则写一个叶节点。叶容量是分裂阈值，超出时保留完整区间。
3. 若所有锚点落在同一个象限，在当前节点内下探分区范围，计入逻辑深度。直到遇到至少两个非空象限或达到终止条件。这样不会为单子路径反复扫描目标，也不会占用额外节点。
4. 对有分叉的节点按四象限计数和算偏移，再把索引稳定写到另一块临时数组的相同区间。一次预留所有非空直接子节点槽位，再将子区间逆序压栈，继续处理。两块临时分区数组轮用，叶索引写入独立的叶区间数组。各分支写自己的区间。树由一个写者构建。

跳过单子分支后，非叶至少有两个子节点。对 N 个有效目标，叶数最多 N，节点上限为 2N−1，N=0 时发布空根。建树上界 O(N·D)，其中 D 为配置的最大逻辑深度，空间按 O(N) 预留节点和索引，建树栈另按深度预留。按四叉 DFS，每下降一层最多留下三个待访问兄弟，节点索引栈按 1+3D 验算。构建栈条目还含节点槽位、区间、分区范围和源数组编号，单独预置容量。初始叶阈值 16、逻辑深度 8 是基准点，真实地图测量后再定。

~~~text
BuildTree(targets, root, buffers)
    空集合 → 发布 Empty
    初始化索引序列，压入根区间
    逐项弹出区间
        统计锚点范围，合并本区间的受击盒
        若可继续，跳过单象限直到分叉或达到深度/边长限制
        能分叉 → 按象限稳定分区、写父节点、预留并入栈非空子节点
        应成叶 → 保存完整索引区间并写叶节点
    发布节点数及有效批次
~~~

主线程在准备与快照采集时校验根覆盖、输入几何和容量。根外锚点是地图配置或移动结果错误，报告失败和目标身份。构建器用批次状态报告失败，查询跳过任何不完整的树。战斗预检硬容量。若配置允许增长，只在旧句柄完成后、调度前按确定的目标数扩容。有效请求超过硬容量时报告本批失败，沿用战斗失败批隔离规则。

## 4. 并行查询和确定性规则

### 几何及筛选

初版沿用共享定点提案，攻击者瞄准点到候选受击盒最近点的距离平方，用 Raw 坐标和闭边界比较。节点的盒包含子树所有真实受击盒，点到并集外包盒的距离平方是子树距离的下界。**剪枝条件为 nodeDistanceSq > searchRadiusSq。** 即使目标锚点在查询范围外，受击盒的边缘进入范围仍能找到。目标的受击盒可以跨越分区的中线，甚至宽出所属叶区。 [共享定点数值域](../03-HitResolver独立模块方案.md#2-定点相交与数值边界)

原型以点与盒边界各轴限在 ±1000 世界单位、半径 ≤1000 为起点。在百万分之一 Raw 刻度下，两轴差平方和至多 8×10¹⁸，装在有符号 64 位整数内。范围和边界提前校验。树分区尺寸及中线计算用长整型并独立核上界。查询距离不用分区根的填充边界。几何合同变化时重新核算数值域，尤其是形状外伸、攻击起点偏移和多盒。

- **锁定复核**由单位和建筑按 ID/代际直接取本阶段值。合法保持的旧目标无需遍历四叉树。丢失资格、超出保持距离、策略指定重评时生成索敌请求。初次索敌和定期重评按固定 Tick 口径推进，定期重评可按稳定 ID 错峰。塔在移动后复验自己的锁定和射程，再决定是否请求当步重选。首版建议自动开火重选只在可攻击目标内排序。塔的索敌半径和攻击半径若同为同源点的圆形距离，可在该次请求用两者的较小值。若配置另有攻击几何或允许塔在射程外锁定，编排应明确对应的筛选和锁定策略，避免射程外的高权重对象始终压住射程内对象。
- **逐层资格**由战斗规则按寻敌者位置、地图入口和保护快照生成。可用 8 个方向的可索敌层值或层掩码表达。候选必须至少在一个共同方向上满足该方向的层规则，不能把 A 方向允许的层与 B 方向允许的入口拼接。核心暴露资格作为独立值传入。树无需知道外围塔为何被判为屏障。
- **排序**沿用单位方案的评审口径，先权重降序，再距离平方升序，最后 BattleEntityId 升序。整个查询保持初始半径。发现较近低权重目标时，仍继续查剩余合格分支。遍历、分区顺序、Job 批大小和线程完成顺序均不影响赢家。距离优先和合成权重均可在确定口径后作为另一套对照策略。 [单位索敌规则](04-单位实现方案.md#帧阶段索敌与移动)
- **排除候选**由当前战斗规则与地图资格明确提供，批请求可带排除 ID/代际。RVO2 的局部停滞留给行为层处理，索敌继续独立按资格和权重排序。

~~~text
FindTargetJob.Execute(i)
    q = Queries[i]
    best = None
    若根有效，将根索引写入本次查询的局部栈
    栈非空时
        node = 弹栈
        若点到 node.ContentBounds 的距离平方 > q.半径平方 → 跳过
        若有子节点 → 将非空子节点压栈
        否则逐个读取叶区间对应的目标
            校验阵营、身份、期限、资格、排除、方向层及核心保护
            计算真实受击盒距离平方，超出范围则跳过
            用 权重、距离、稳定 ID 归约到 best
    Results[i] = best
~~~

树、目标态、查询均为只读 NativeArray。结果 NativeArray 按请求位置写入，常量和遍历栈为 Execute 局部值，例如 FixedList512Bytes<int>，启动时按 Capacity 核对应深度上界。每个请求只输出一个结果，不共享计数器或候选链，不依靠关闭安全检查。性能计数如需调试，写每请求固定槽位，批尾归并。 [Unity IJobParallelFor](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Unity.Jobs.IJobParallelFor.html) · [Collections 固定容量列表](https://docs.unity3d.com/Packages/com.unity.collections@2.6/api/Unity.Collections.FixedList512Bytes-1.html)

## 5. Job 调度、内存和热更

~~~text
Tick N
    提交开步命令和到期状态，固定本步保护与状态
    采集召唤单位索敌请求；如需要，调度敌塔 BuildQuadTreeJob
    FindTargetJob.Schedule(请求数, batchSize, enemyTreeBuildHandle)
    在移动消费前 Complete，按请求顺序提交单位目标

    计算目标点和停步意图，执行 RVO2，量化并提交移动结果

    采集移动后单位与塔的请求
    playerBuildHandle = BuildQuadTreeJob.Schedule()
    towerQueryHandle = FindTargetJob.Schedule(请求数, batchSize, playerBuildHandle)
    在攻击意图消费前 Complete，提交塔目标、复核攻击范围
    进入 HitResolver 和结算
~~~

- 每个需要 Job 的阶段只在消费者入口等待一次。建树和查询用 JobHandle 相连。可在等待前做规则允许且不读写这批容器的工作。由于移动依赖第一次目标结果，两个阶段有实质顺序，性能统计分别计算调度、工作线程耗时、Complete 等待和写回。不能按 Job 恰好何时完成来决定这个 Tick 是否用新目标。 [依赖调度](https://docs.unity3d.com/6000.0/Documentation/Manual/job-system-job-dependencies.html) · [JobHandle.Complete](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Unity.Jobs.JobHandle.Complete.html)
- 各树的输入、节点、索引、BuildHeader、队列工作区、结果采用由 BattleWorld 生命周期持有的 Persistent 缓冲。同批执行中禁止修改、扩容或释放。复用前完成所有读写句柄。使用 BuildHeader 的有效长度读取节点，无需每 Tick 清空全部容量。退场/异常收尾先关闭调度，完成持有的句柄，再释放缓冲。主线程预检世界、Tick、阶段及代际后走 Entitas 1.14.1 生成接口写回。一批出错不应用部分结果。 [Collections 分配器](https://docs.unity3d.com/Packages/com.unity.collections@2.6/manual/allocator-overview.html) · [战斗世界生命周期](00-战斗编排与集成方案.md)
- **程序集方向是 GameLogic 热更层 → 主包索敌 Job 程序集。** Battle/Targeting 保留实体投影、资格/层规则、丢锁和结果提交。主包提供可直接引用的具体 Job、定点 Raw 几何、数组四叉树、公开值结构和批调度。权重与范围由热更数据驱动，新增需要 Job 认识的排序算法或几何类型属于主包变更。主包不依赖 GameLogic、Entitas 或热更侧 Fixed64 类型。相同定点几何在落地时确定单一共用实现，避免命中与索敌出现不同的 Raw 边界规则。
- 仓库记录 Unity 6000.0.69f1、Burst 1.8.28、Collections 2.6.2、Mathematics 1.3.2。主包建立明确的非热更 asmdef，使用具体类型调度 Job 并形成 AOT 可达引用。目标 IL2CPP Player 用实际热更入口验收 Burst、裁剪及必要的 AOT 泛型，不用 Editor JIT 推断真机结果。Unity 官方区分 Editor JIT 和 Player AOT，HybridCLR 文档指出普通热更代码的 Burst 段可能走解释执行。 [Unity Burst 编译](https://docs.unity.com/en-us/engine/6000.0/manual/programming-environment/script-compilation/burst) · [HybridCLR 限制](https://www.hybridclr.cn/en/docs/7.10.0/basic/notsupportedfeatures) · [项目锁文件](../../../Packages/packages-lock.json) · [TEngine 热更规约](../../../.agents/skills/tengine-dev/references/hotfix-workflow.md)

建议主包源码归入 Assets/GameScripts/Main/BattleSpatial/，用 BattleSpatial.asmdef、值结构与定点几何、BuildQuadTreeJob、FindTargetJob 和批次所有者实现。GameLogic/Battle/Targeting 增加战斗阶段适配器。适配器调用准备写入、调度、完成读取和释放入口，结果视图只在当前批次有效。具体路径和程序集引用随实现评审确定。

## 6. 分步实施

- [ ] **定义快照和标量基准。** 对齐形状、状态和锁定合同，按「本步投影 → 完整枚举 → 同一个排序比较器」产出索敌参考结果。以建造/破损/复活和移动前后的位置变更构造有效输入。先用值数据跑通，正式写回依赖 Battle Context 生成。
- [ ] **构建数组树。** 完成根边界、稳定分区、节点布局、内容盒、容量预检。实现「有效目标 → 不重不漏的叶区间 → 子树内容盒」。对重合和深度上限保留完整叶区间。
- [ ] **实现批量 Job。** 完成建树句柄、只读视图、独立结果槽和批次状态。实现「Build IJob → Query IJobParallelFor → Complete → 主线程申请写回」。在不同批大小和输入顺序下与全扫描比对。
- [ ] **接入战斗两个阶段。** 用单位、塔和编排的快照装配请求。实现「开步资格/先选塔 → 移动 → 塔从新位置选人 → 攻击复核」。覆盖目标保持、资格失效重选与抵抗塔代际。 
- [ ] **核目标平台和调优。** 确认 AOT/Burst 实际生效、异常释放、内存预算和整步耗时。按数据决定叶阈值、深度、batchSize。仅当动态 BuildJob 成为主瓶颈并使整步超预算时，再评估 Morton 编码与并行构建。基线首先统计完整开销。

## 7. 验收及性能对照

| 场景 | 判定标准 |
| --- | --- |
| 空树、根上界、负坐标和象限中线 | 空树正常返回无目标，合法边界目标唯一落叶。 |
| 锚点在象限或查询范围外，受击盒跨线并与搜索圆相切 | 不漏候选。用点 (0,0)、半径 5、目标锚点 (5.4,0)、受击盒 X=5 到 5.8 且 Y 含 0 作为确定用例。多盒目标只评一次。 |
| 最近目标低权重、同权同距分属不同子树、八方向与保护冲突 | 较远但高权重的合法目标能够胜出，等距选低稳定 ID，逐层与核心权限与全扫描一致。 |
| 全部锚点重合、树满、成批出生或回收 | 重合目标构成完整叶。容量不足有明确批次状态，无部分写回。记录大叶中的候选数及波峰内存。 |
| 玩家单位本步移入塔索敌半径、开步到期、N 步拆塔、下回合复活 | 塔发现移动后进入者。到期单位不可选，N+1 才读新保护状态，旧代际锁定失效。 |
| 塔可攻击近目标，但另有射程外高权目标 | 采用首版自动开火重选口径时，塔按攻击过滤和本步位置选中合法近目标。 |
| 同一输入下改变线程执行顺序、batchSize 和宿主帧率 | 每个已提交 Tick 的索敌结果与战斗摘要保持一致。Editor 与目标 Player 分别记录结果。 |

**同口径对照三组。** 全扫描批查询、上一案的均匀格桶批查询、四叉树批查询，使用相同快照、资格、排序和输出约束。比较四叉树的总阶段时间、主线程等待和用量。首轮合成样本可用移动单位 128 / 512 / 2,048 / 8,192，另带实际关卡数与真实塔查询数。各样本覆盖均匀、稀疏、围塔聚团、完全重合、短距离和全场范围，分别看静态缓存命中和每步重建。样本数字用于找退化点，正式容量按玩法定。

记录快照填充、静态/动态构建、调度、查询、等待和提交的 P50/P95/P99，另外记录每查询访问节点数、候选数、最大叶尺寸、峰值原生内存、托管 GC 和超预算 Tick。关闭统计后的生产路径单独测。对大半径覆盖全地图的情况，四叉树仍可能逐一检查所有目标。性能目标以实测设备的整步预算为准，稳定热路径目标为 0 B 托管分配/Tick。

实施前需确认目标设备与峰值单位/塔数、方向保护与正式排序、锁定保持与刷新节奏。本次交付为源码调研和设计，Unity、编译、构建、回放和性能对照均未执行。
