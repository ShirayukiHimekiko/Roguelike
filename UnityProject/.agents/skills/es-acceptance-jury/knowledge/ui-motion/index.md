# 游戏UI动效：按问题定位

<a id="issues"></a>
## 十二个具体用途

按当前问题读一个叶段；下面链接不要求通读。本批原件读取于2026-10-15，规范/API事实与用于游戏UI的工程推导分别说明。来源成立、离线逻辑正确和额外AI收益各保范围；不代Unity实际画面、帧耗、输入或玩家感知验证。

| 问题 / 触发 | 准确正文 |
| --- | --- |
| K1 抽屉途中反向时跳到端点 | [反向保进度](interaction.md#retarget-progress) |
| K2 连续改选中项时惯性重新蓄力 | [二阶状态续接](interaction.md#spring-state) |
| K3 面板淡出时按钮、背景点击和手柄焦点交接 | [输入与可见性](interaction.md#input-presence) |
| K6 连发奖励使余额偏小、显示动画倒写模型 | [权威值与展示](interaction.md#authority-display) |
| K4 子补间设了unscaled，暂停页仍不动 | [实际时钟所有者](runtime.md#sequence-clock) |
| K5 替换/取消提示条时，新内容被旧完成回调归池 | [完成与取消归属](runtime.md#completion-ownership) |
| P1 图标脉冲挤动兄弟，静止Idle仍持续更新 | [布局与脏链](runtime.md#layout-dirty) |
| P2 想给每行加Canvas，或静态大HUD被频繁重建 | [共同变化分组](runtime.md#canvas-cohorts) |
| P3 列表、圆头像和跨行高亮的裁剪边界不同 | [形状与裁剪祖先](presentation.md#clip-boundaries) |
| P4 同格式数字更新时内部列位游移 | [字形advance与固定槽](presentation.md#numeric-advance) |
| P5 减少动态后Ready、选中或获奖结果也消失 | [等效状态反馈](presentation.md#reduced-motion) |
| P6 整秒桶、普通亮度或开关选项被用来放行闪烁 | [往返、滑动窗与面积](presentation.md#flash-analysis) |

<!-- jury-read-continue: knowledge/index.md#scope -->
