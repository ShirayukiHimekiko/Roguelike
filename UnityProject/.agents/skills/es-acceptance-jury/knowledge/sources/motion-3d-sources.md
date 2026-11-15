# 3D技术知识与来源

<a id="technical"></a>
## 技术线索与合法对照

2026-09-24网页摘要（Epic UE5.8、Unity6.6）；未看嵌入视频、未运行样例，不认证当前页面版本或成品效果。

机制线索是本包从已读网页提炼的查错切入，不冒原文逐条规定。

| 卡点 | 可借用的机制线索 | 不能推出的结论 | 已读来源 |
| --- | --- | --- | --- |
| 网格脱离、结束回弹 | 网格、根、角色和碰撞边界的位移可能未按同一职责提交；根提取/应用及运动状态值得区分 | 全项目必须Root Motion；UE轴向/重力默认值是跨引擎标准 | [Epic Root Motion](https://dev.epicgames.com/documentation/en-us/unreal-engine/root-motion-in-unreal-engine) |
| 位移到了但朝向/接触错 | 匹配目标旋转与朝目标位置转向不同；接触阶段、修正窗口和位置/方向到达是不同关系 | 任意距离/角度扭曲都自然；必须装插件 | [Epic Motion Warping](https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-warping-in-unreal-engine) |
| 过度扭转、步幅/坡度或上下身不协调 | 方向、步幅、坡度与插值过渡各有作用；合法参数不直接证明动作自然 | 默认90度是通用验收线 | [Epic Pose Warping](https://dev.epicgames.com/documentation/en-us/unreal-engine/pose-warping-in-unreal-engine) |
| 起停、急转和落地阶段不匹配 | 姿态阶段可与距离/速度对照；急转不必先完全停下 | 示例采样率是所有任务标准；必须Distance Matching | [Epic Distance Matching](https://dev.epicgames.com/documentation/en-us/unreal-engine/distance-matching-in-unreal-engine) |
| 身体方向与移动方向不同 | 侧移可以合法；Humanoid/Generic根定义、循环漂移和混合足底高度是不同技术关系 | 身体必须始终朝速度方向；Feet选项证明整链通过 | [Unity Root Motion](https://docs.unity3d.com/Manual/RootMotion.html) |
| 算法接好却缺质量/响应 | 成品常速体验与Bones/Movement/Trajectory/Collision诊断回答不同问题 | 已实际玩过示例；Motion Matching保证顶尖表现 | [Epic Game Animation Sample](https://dev.epicgames.com/documentation/en-us/unreal-engine/game-animation-sample-project-in-unreal-engine) |

原网页没有给跨玩法统一毫米/角度/速度门槛。四元数双覆盖、多圈采样、完整父空间和旋转平台相对接触是本包工程推导，不冒网页逐项规定；其适用性仍依项目单位、时钟、所有者和合法对照。

<a id="experience"></a>
## 发现可比参考的入口

[GDC 2016：Simon Clavet / Ubisoft Montreal，Motion Matching and The Road to Next-Gen Animation](https://www.gdcvault.com/play/1023280/Motion-Matching-and-The-Road)：2026-09-24已读介绍，未看演讲/逐字稿。摘要涉及当前姿态、未来运动意图、起停/转向和响应，未证明演示观感或实现。此库尚无已观察的成品片段。

实际参考选择与检查由[13/02原项目依据](../../references/constraints/13-motion-3d.md#basis)承担，缺源见[补源](../../references/evidence-recovery.md#joint-source-search)。
