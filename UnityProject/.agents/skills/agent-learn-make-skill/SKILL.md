---
name: agent-learn-make-skill
description: 把成熟专业来源学成能实际动手的制作能力：先取用户点名的参照、写可检验目标，尽早做出完整粗版并对照返修，再把方法沉淀成可复用的 Skill。支持新能力学习、已有方法应用、续作和 Skill 维护；普通问答不扩成学习工程。锁定 GPT-6.1-SOL。
metadata:
  version: "1.9.18"
---

# 学到能做，再用到新需求上

本 Skill 交付的是能做出合格作品的能力，不是笔记、报告或参数清单。检验标准：换一个条件不同的新需求，后继能照着方法重新选做法、实际改源、做出合格结果。本 Skill 不改模型权重、不在后台运行，研究、制作、保存都由当前 Agent 真实执行。

使用 `gpt-6.1-sol` / `xhigh`（用户明确指定的强度优先）；`gpt-5.6-sol` 已被服务端拒绝，不用。模型不可用时如实说明，不静默降档。

## 先选模式和第一批

先读 [learning-control 的模式与预算](references/learning-control.md)，在一处写清本批要交的结果、当前步骤、预计投入、已用和在途、下一位使用者。有效授权和旧账直接继承；状态未知的操作先查原作业，不重放写入或付费。预算约束做法，不降低目标。

| 模式 | 先做什么 |
| --- | --- |
| 普通应用 | 用已有有据的方法完成作品，只核变化了的条件，按 [production-learning](references/production-learning.md) 制作。 |
| 新能力 / 深学 / 反证后换法 | 读 [workflow-learning](references/workflow-learning.md)；要靠看/听判断品质的，同时读 [reference-acquisition](references/reference-acquisition.md)。缺专业依据按 [来源覆盖](references/scope-and-selection.md#source-coverage) 补。 |
| 恢复 / 续作 | 按 [task-continuity](references/task-continuity.md) 找回原位置、唯一写入者、现行方法、原失败和在途，核到真实终态再做下一动作。 |
| 创建 / 维护 Skill | 新建读 [skill-design](references/skill-design.md)，维护读 [skill-maintenance](references/skill-maintenance.md)。 |

## 主线：先看到目标，尽早做出完整粗版

八个步骤是证据依赖，不是固定流水线：定目标 → 查源比较 → 拆解范例 → 原条件重现 → 带质疑的判别 → 异需整合 → 回归 → 沉淀再调用。每步的进入条件和产物见 [learning-control](references/learning-control.md)；已成立的部分可复用、交错执行，新能力不能跳过这些证据。

0. **先写 `INTENT.md`，第一张粗图时向用户回读，每波查漂移**，见 [intent-and-drift](references/intent-and-drift.md)；核心名词是主角。
1. **取参照、写 `TARGET.md`**：点名参照不可替换，用 `scripts/refgrab.py` 取，按[看图方法](references/visual-judgment.md)选和比；写代码前在 TARGET 里填[路线表](references/route-selection.md)：每个特征用哪种风格做法产生。每个点名对象有 1 张实机图就开工。三个来源都失败才问用户。
2. **尽早出第一张完整粗版**，和参照并排对比，排出差距最大的 3 处；参照暂缺就用本地参照并标出缺口。
3. **每轮开头写明推进 `TARGET.md` 哪一条差距**，查源和实验只为它服务，无关小修进待办。每版要么新增一个特征，要么修掉主机位上看得见的问题；连续两版主机位没变化，停掉这条技术线，按路线表重选做法。
4. **最小场景最多用一波**：只用来定位技术问题，修完回完整作品复核，没变好不算修好。
5. **Skill 草稿从第一轮就写**，中断时草稿就是交付物。

下一件作品按 [next-author-work](references/workflow-learning.md#next-author-work) 选：完整目标里最弱的是哪一处，改哪个源、用哪项成熟工艺或供给、预期怎样变、谁来用。先拿到专业作者“为什么这样设计、怎样改、怎样判断、何时失效”的依据；工具说明只证明工具能用。关键未知先写可推翻的预测，再做能区分原因的干预，不做全参数扫描。

## 首次结果不可直接采用

自己或其它 AI 第一次给出的解释、方案、判断、产物都是候选，须由另一个真实 AI 对同版原需和原件实际查证后，才能在查过的范围内采用；不加第三层审查。细则见 [首次结果独立核验](references/comparison-and-regression.md#independent-first-result)。

## 用结果改变下一步

- 实现或接线错了：修出错的位置，核回后立即回到主体品质。
- 设计、表示或供给被反证：撤回依赖它的生产，补对应能力，不靠追加规则或换题名掩盖。
- 方法有据、只缺本次组合：直接做完整首件。

每次实质改变按 [comparison-and-regression](references/comparison-and-regression.md) 核原坏例和正常用法，不删弱断言求绿。按工序再读：[source-to-automation](references/source-to-automation.md)、[engineering](references/engineering.md)、[nonengineering](references/nonengineering.md)、[ai-assisted-production](references/ai-assisted-production.md)。

## 沉淀到后继真的会读的位置

目标领域 Skill 按“目标效果由哪几层构成 → 每层的做法和参数 → 怎么和参照对照判断”来写，每轮修进对应层，写清为什么有效、何时成立、副作用和反例，分清作者说的、实测证实的、经验性的和推断的；踩过的坑放附录，见 [写法](references/skill-design.md#target-layers)。迁移要用条件真不同的新需求证明，只换颜色或重跑 Demo 不算。

## 写法、工具与停止

- 给人看的内容用普通开发者能读懂的中文，先说看到什么、差多少，再说下一步。机器键名保持原合同；按需读 [tool-checks](references/tool-checks.md)，工具绿灯不认证品质。
- 配置里写了联网搜索不等于真有这个工具，先看工具列表。
- 目标没达到、还有授权内可做的动作就继续。真正停止按 [continue-or-stop](references/task-continuity.md#continue-or-stop) 核完整目标和许可。
