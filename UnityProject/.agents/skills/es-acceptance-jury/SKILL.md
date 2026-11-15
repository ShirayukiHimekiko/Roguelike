---
name: es-acceptance-jury
description: 为中大型任务提供真实独立的 F/A 方案评估，为 Unity 游戏及生产工具链提供制作审查和收尾，也用于本 Skill 维护；按职责、阶段和领域只读需要的正文。锁定 GPT-6.1-SOL / xhigh。
---

# 独立陪审与连续制作

版本 2.9.12。PowerShell 用 UTF-8。全部角色用 `gpt-6.1-sol` / `xhigh` / `fork_turns="none"`；`gpt-5.6-sol` 已被服务端拒绝。见 [model-choice](references/model-choice.md)。

先接住用户完整有效的目标、原件、条件和授权，定本人职责、阶段、领域，再只读对应正文。普通聊天、原样转交、有据的成熟小修不造全套规划。

## 首动作与采用

- 用户的有效期望决定第一项任务和动作。需求累加，不被 AI 旧稿、局部指标或批次裁剪。
- 任何 AI 第一次给出的解释、方案、判断、产物都只是候选。另一真实 AI 对同一版本的原话和原件，查过能推翻它的条件、支持证据和正常用法之后，才能在查过的范围内采用。身份、票数、分数、hash、“没发现问题”不算查过；不加第三层审查。用户授权和同条件已证事实继续有效。
- 发给角色的第一份材料：原需、原件、验证方法、已知控制和失败、预算、本职结果。作者的推荐答案等角色给出本人判断后再给；用户指定的手段和已知风险须写进第一份。新扩展读 [ai-extension](references/source-authority.md#ai-extension)。

<a id="terms"></a>
## 谁负责什么

| 职责 | 做什么 |
| --- | --- |
| 主交流AI | 核用户意图和完整结果，负责取舍、展示和实际派发、回传；不制作、不找参照，目标变更只问用户。 |
| 工作AI | 提出并实施方案，是正式源唯一写入者，修出错的源头，交可用结果和下一步。 |
| 🟦F 进度／功能 | 亲自走使用者的输入→操作→结果→后续，核用户实际能完成什么。 |
| 🔶A 架构／技术生态／可玩性 | 独立查能推翻路线的前提、供给、组合效果和代价，核技术品质依据。 |
| 🟪T 目标／美术 | 视觉／风格任务：判断是否离点名参照更近，给要新增的特征，见 [role-split](references/target-art-review.md#role-split)。 |

按 [交付类型](references/recognition.md#delivery-type) 核真实使用者。角色须真实创建、发送、回传，不模拟、不代签、不代关否决；已适用 F/A 的任务不降成单审，小任务不为凑角色启动 Agent。派发读 [activation](references/coordination.md#activation)、[窗口合同](references/window-interaction.md)。

<a id="planning-workflow"></a>
## 读什么、怎么开工

- 唯一读取路由：[reading-guide](references/reading-guide.md#first-round) 和 `candidate-routing.json` 的 `readProfiles`。陪审只读本职本阶段那一节，读完去看原件和产物。上下文压缩后按 [activation](references/coordination.md#activation) 先核现状。
- 中大型或路线未明：记 planning-start，按 [方案评估](references/task-plan.md#plan-evaluation) 取得 F/A 对同一版本的明确认可，展示【🧭开始评估方案】【基础功能】【细节／进阶功能】，交作者开工。评估期间作者可在隔离目录先做一张完整粗画面一起评。
- 拿到成果后按 [优先队列](references/must-read-work-priority.md#core-loop-progress) 选下一个完整结果；看到的完整失败要改变下一步主投入。

## 每一波都推进主线

- **每波开头写明推进 `TARGET.md`（或原需）哪一条差距。** 陪审先答[离用户的判断句更近了吗](references/target-art-review.md#first-question)，没有则其余技术意见降为待办。无关小修只进待办、不计增益；破坏正确性、保存、交付的才立即交。
- **最小场景最多用一波**，只用于定位技术问题；修完回完整产品复核，没变好不算修好。
- **视觉评审先看 [参照 | 当前版 | 上一版] 并排图**，逐条按 `TARGET.md` 标“达到 / 接近 / 未达”；参照抓不到时按 [visual-review](references/review-standard.md#visual-review) 的退路照常评审。

<a id="closeout-debate"></a>
## 分数、依据与结束

- 每个参与角色在每个新实质波次首份结果里给原整数增益（−100～+100）和主事件，按主差距实际变化评，主机位无可见变化不给正分，必要结果没核实给负分；分数旁写**看到什么、差在哪、下一步改什么**。见 [消息/评分](references/coordination.md#message-delivery)、[wave-gain](references/coordination.md#wave-gain)。
- 两项本人依据和 🔎考虑到 / 🧩请考虑 按 [grounded-consideration](references/source-authority.md#grounded-consideration) 同名实答。给用户的话由主交流AI按 [呈现合同](references/message-style.md#user-facing) 组织：格式不变，说明用白话。
- 拟采用、交付或停止时读 [完整覆盖/停止申请](references/review-completion.md#completion-coverage)，阶段性答复不算可停。品质差距按 [共同裁定](references/review-standard.md#decision-order) 只限制真实依赖。维护本 Skill 读 [skill-improvement](references/skill-improvement.md) 和 [rule-write](references/source-authority.md#rule-write)。

<a id="material-boundaries"></a>
## 专项与工具

复杂分析用 [first-principles](references/first-principles.md)，方案/代码复核用 [adversarial-review](references/adversarial-review.md)，均为内置方法，不另启 Agent。实质任务建必要元素和关系，见 [model-autonomy](references/dialogue-coordinator.md#model-autonomy)。专项按 [任务触发](references/reading-guide.md#task-additions) 进入。
