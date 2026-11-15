# 复杂动作：原始来源定位

<a id="issues"></a>
## 按实际问题取源

2026-10-15已核十四个专业用途。本轮四组定向首轮的主要决定均正确，未证明专题知识带来额外行为或成本收益；依用户既有筛选要求，这里仅保来源定位，不收入十四段补差方法正文。题面已给症状/正常对照，Spine与检索组还提供必要原件，不冒无提示检出或无源先验能力。

| 问题 | 准确原件与定位 |
| --- | --- |
| B1 高轨混合下沉、hold后缺键属性跳回 | [Spine 4.2 AnimationState](https://github.com/EsotericSoftware/spine-runtimes/blob/e7dc1435fa4a0083ab431f1b28e083c14a1f5c68/spine-ts/spine-core/src/AnimationState.ts#L725)：computeHold、holdPrevious、propertyIds。 |
| B2 附件早切、旧draw order迟交还 | [同固定源码](https://github.com/EsotericSoftware/spine-runtimes/blob/e7dc1435fa4a0083ab431f1b28e083c14a1f5c68/spine-ts/spine-core/src/AnimationState.ts#L169)：apply/applyMixingFrom；附件有效alpha与mix门槛、draw order资格。 |
| B3 混出命中、首帧/回绕/同刻事件 | [Spine EventTimeline](https://github.com/EsotericSoftware/spine-runtimes/blob/e7dc1435fa4a0083ab431f1b28e083c14a1f5c68/spine-ts/spine-core/src/Animation.ts#L1621)及[混出事件](https://github.com/EsotericSoftware/spine-runtimes/blob/e7dc1435fa4a0083ab431f1b28e083c14a1f5c68/spine-ts/spine-core/src/AnimationState.ts#L269)。 |
| B4 walk/run触地错相、脚步重复或被吞 | [Epic Animation Sync Groups](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-sync-groups-in-unreal-engine)：Marker-Based Syncing、共同marker、leader/notifies。 |
| B5 惯性化后必要源notify消失 | [Epic Blend Nodes](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-blueprint-blend-nodes-in-unreal-engine)：Inertialization、源停止求值与notify。 |
| B6 换单位/特征后检索选择改变 | [OrangeDuck固定database.h](https://github.com/orangeduck/Motion-Matching/blob/57b7250e0d34a4e456a34d47e24c2f05fdcc711e/database.h#L100)与[controller](https://github.com/orangeduck/Motion-Matching/blob/57b7250e0d34a4e456a34d47e24c2f05fdcc711e/controller.cpp#L529)：训练offset/scale、root-local、权重约定。 |
| B7 错玩法候选、断尾、重选抖动与素材缺速 | [Epic Motion Matching](https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-matching-in-unreal-engine)：Continuing Pose Cost Bias、Block Transition、Exclude From Database、Schema。 |
| C1 两骨过近/过远、伸直时弯向退化 | [OrangeDuck Simple Two Joint IK](https://theorangeduck.com/page/simple-two-joint)；[Unity Two Bone IK 1.2](https://docs.unity3d.com/Packages/com.unity.animation.rigging@1.2/manual/constraints/TwoBoneIKConstraint.html)及[官方1.2.1源码包](https://packages.unity.com/com.unity.animation.rigging/-/com.unity.animation.rigging-1.2.1.tgz)：AnimationRuntimeUtils.cs。 |
| C2 转动环境上的接触点漂移 | [Unity TransformPoint](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Transform.TransformPoint.html)与[InverseTransformPoint](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Transform.InverseTransformPoint.html)：点/方向、缩放语义。接触状态设计另属工程推导。 |
| C3 IK后祖先调整使最终末端再次偏离 | [Unity Rigging Workflow 1.2](https://docs.unity3d.com/Packages/com.unity.animation.rigging@1.2/manual/RiggingWorkflow.html)：ordered jobs、RigBuilder/Rig层级与深度优先收集。 |
| C4 MatchTarget重发、过期排下圈、上层失效 | [Unity6 Animator.MatchTarget](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Animator.MatchTarget.html)：基层、单槽、循环时间与applyRootMotion；实际重载按项目版本核。 |
| C5 根到socket但手偏、环境目标移动 | [Epic Motion Warping](https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-warping-in-unreal-engine)：None/Static/Bone provider；[FMotionWarpingTarget](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/MotionWarping/FMotionWarpingTarget)：bFollowComponent与offset。 |
| C6 Facing/目标旋转混淆、根增量重复与受阻后覆盖 | [Epic Motion Warping](https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-warping-in-unreal-engine)：Rotation Type/Window；[Root Motion](https://dev.epicgames.com/documentation/en-us/unreal-engine/root-motion-in-unreal-engine)：Movement与模式。差分核算另属工程推导。 |
| C7 刹停被挡仍播完、混用距离与时间/候选 | [Epic Distance Matching](https://dev.epicgames.com/documentation/en-us/unreal-engine/distance-matching-in-unreal-engine)：节点参考、曲线轴/Compression/Sequence Evaluator。 |

Epic为本次实读的滚动快照，不认证任意安装版本。Spine及Motion-Matching源码固定到上述提交；Unity 1.2.1官方包只下载核源，未安装。来源事实、几何/调度推导和真实引擎执行分开；数值切片不证明完整骨架、接触碰撞、自然度、性能或玩家体验。

<!-- jury-read-continue: knowledge/index.md#scope -->
