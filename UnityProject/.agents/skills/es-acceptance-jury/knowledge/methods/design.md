# 设计与玩法方法

<a id="issues"></a>
## 按问题定位

| 问题 | 选段 |
| --- | --- |
| G1：均速排期看似够用，承诺日期却不稳 | [工期分布与范围](#delivery-forecast) |
| G2：追加持续效果反而变弱，或合并凭空增减伤害 | [剩余效力](#remaining-effect) |
| flow：队友仍承压又刷怪，尾战吞掉休息窗 | [退潮与休整](#encounter-recovery) |
| 可玩性：大厅分接近，却未必是合适对手 | [配对不确定性](#match-quality) |

<!-- jury-read-continue: knowledge/index.md#scope -->

<a id="delivery-forecast"></a>
## 工期分布与范围

有同执行者的估计/实工记录时，Spolsky的EBS方法保留每项历史速度`v=estimate/actual`：每个未来情景为各剩余任务抽取该人的历史v，用时为`estimate/v`；汇总成完成时间分布，再比较保留必要内容的scope组合。小数据可精确枚举，不必蒙特卡洛。一个均速日期不能代到期概率；历史恒定速度应退化为确定日期。

这是依赖历史可比、逐任务抽样等假设的条件预测，有限记录不证明真实80%已校准。缺失任务、集成/复验、相关停工和人员变化另核；历史已计入的日常打断不重复乘系数，不把不同执行者混成一锅。

来源：[Joel Spolsky, Evidence Based Scheduling](https://www.joelonsoftware.com/2007/10/26/evidence-based-scheduling/)，2007，§2–4及打断/scope说明；2026-10-15实读。

<a id="remaining-effect"></a>
## 线性持续效果的剩余效力

合并同类线性毒伤时先扣已流逝部分，保未结算总量`B=P1*D1_remaining+P2*D2`。只保B仍可能使追加命中后的即时DPS变小。若设计希望追加不削弱即时反馈，一个选项是`P=max(P1,P2), D=B/P`；同强度自然延长剩余时长。独立stack时间线也是候选，需核总量、即时反馈和正常到期后重施。

最大强度法会把弱效果的伤害提前，影响击杀时点；它是作者的设计取舍，不能套到非线性交互、免疫、上限或产品明确选择的其它叠加规则。不用全局加伤掩盖合并损失。

来源：[Lars Doucet, A Status Effect Stacking Algorithm](https://www.fortressofdoors.com/a-status-effect-stacking-algorithm/)，2011，Conservation of PotencyDuration / Match Highest Potency / Final Considerations；2026-10-15实读。

<a id="encounter-recovery"></a>
## 合作遭遇的退潮与完整休整

Valve的L4D导演以逐玩家强度的最大值保护高压个体：Build Up→短暂Sustain Peak→减少新威胁的Peak Fade，等自然交战间歇后才起Relax。尾战时间直接算进休息会吞掉恢复窗口；已有少量敌人不等于仍在直接交战，不能一律等地图清零才起休息。保既存敌人和既定boss例外，调新威胁频率，不靠降敌人伤害或冻结AI实现。

原作续峰3–5秒、休整30–45秒或推进距离是实例参数，不是通用标准；其它游戏可用等效个体保护。强度是代理，阈值与真实体验仍需本项目验证；无峰段的正常低压推进不应永久休息。

来源：[Michael Booth, The AI Systems of Left 4 Dead](https://cdn.akamai.steamstatic.com/apps/valve/2009/ai_systems_of_l4d_mike_booth.pdf)，Valve AIIDE 2009，PDF p79–82、92；2026-10-15实读整页。

<a id="match-quality"></a>
## 配对保留不确定性

已有独立Gaussian技能信念的1v1模型中，`c²=2β²+σA²+σB²`，作者的配对量`q=sqrt(2β²/c²)*exp(-(μA-μB)²/(2c²))`。q是和局容差趋近0时归一化的假想和局概率比，不是胜率。相同μ可都有50%预测胜率，却因σ不同而有不同q；榜单保守显示分`μ-kσ`不能直接替代配对量。

只在相应模型/参数下比较。无和局时`P(A胜)=Φ((μA-μB)/sqrt(c²))`也与q不同；网络、等候、队伍和真实技能校准另核，不为最大q无限排队，也不签整款游戏好玩。

来源：[Microsoft TrueSkill作者维护页](https://www.microsoft.com/en-us/research/project/trueskill-ranking-system/)，How to Match Players / Leaderboard / FAQ及原公式图；[Herbrich等，2006论文](https://www.microsoft.com/en-us/research/wp-content/uploads/2007/01/NIPS2006_0688.pdf)p1–2模型；2026-10-15实读。
