# 设计知识与来源

<a id="principles"></a>
## 能改变判断的四条依据

2026-09-26核对网页/官方源码的转述；未看内嵌录像，未附原媒体。以下是本包提炼的设计线索，不代表全行业共识或本项目实测。

| 卡点 | 可借用的结论 | 适用与反例 | 已读来源 |
| --- | --- | --- | --- |
| 重要信息被表现挤掉 | 关键事件、身份与交互需要相称注意力；音画同时争峰值会削弱辨识 | 可从竞争区找取舍，不推出所有游戏都低饱和、少特效 | [Riot：Clarity in League](https://www.leagueoflegends.com/en-us/news/dev/clarity-in-league/)，The Unbreakable Vows / Filling Up Buckets |
| 反馈拖操作或节奏无峰值 | 高频任务重响应，关键时刻可重表达；曲线和时长服务目的 | 可区分输入反馈、内容组织和表达峰值；Carbon禁弹跳是企业品牌取向，不是游戏禁令，文本不证视频观感 | [Carbon：Motion](https://carbondesignsystem.com/elements/motion/overview/)、[官方源码](https://github.com/carbon-design-system/carbon-website/blob/main/src/pages/elements/motion/overview.mdx)，Style / Easing / Duration |
| 文字在目标画面难读 | 字号、字形、间距与显示/观看条件共同影响可读性 | 实际字体和长文案比统一像素值更能定位问题；具体XAG要求取决于项目承诺/受众 | [Xbox XAG 101](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/101)，Goal / Overview / Implementation |
| 文字不动仍难阅读 | 背景运动、闪烁、自动更新也会竞争注意力；降低竞争、阅读底板或可控动效是可能手法 | 有动画不等于必须删除；已采用标准的控制义务仍由当前规则核定 | [Xbox XAG 117](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/117)，Overview / Implementation |

当前诊断与标准采用见[04/02](../../references/constraints/04-visual.md#design-basis)；缺参考见[补源](../../references/evidence-recovery.md#joint-source-search)。此处没有验证项目效果、实时页面内容或素材许可。
