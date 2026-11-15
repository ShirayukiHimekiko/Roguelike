# 文件、合同与来源的按需检查

从Skill根目录调用下列工具；本页保原有命令与保护边界，机械核查不代主文要求的工业工艺、项目动作及真实效果。只在任务需要这些检查时读取，不将其变成所有学习的前置。


检查按必要结果及本次变化选择，不反过来按手边能测的内容裁剪目标。可用 `python scripts/skill_files.py inspect SKILL_DIR` 核入口、前言、正文和普通本地内联引用，维护时用 `python scripts/skill_files.py compare OLD_SKILL_DIR NEW_SKILL_DIR` 比较实际载荷，或使用本地 `skill-creator`/已有等效方法。机械工具不是学习和自迭代前置，缺工具仍可实际读回/调用并保存所得；必须依赖工具才能判断的部分保未证。它们与下述可选合同检查各有范围，均不能代替新任务结果；详见[设计](skill-design.md)及[维护](skill-maintenance.md)。

新任务按范围和前提调用当前方法及实际存在的合同，检查来源变化的实际影响，不刷新hash掩盖漂移。制作能力的输入应能表达新需求，输出应是新产物或真实改进；只读旧JSON／PNG的检查器须按诊断／证据复核限域。已有生产Skill／工具时，在协调的写域经其真实入口应用、改源重建并消费，再决定纳入；用户明确要求在MyTA等目标宿主落地时，临时目录不能替代该出口。小技巧无需先完成整个领域，但必须有它本身的新任务复用证据，不能替整个父目标结案。

使用 `scripts/learnpack.py`：

```text
python scripts/learnpack.py fingerprint --source-root PROJECT --file RELATIVE_PATH --out SOURCES_JSON
python scripts/learnpack.py validate PACK --source-root PROJECT
python scripts/learnpack.py check PACK --source-root PROJECT --workspace WORK --input INPUT_JSON --output OUTPUT_JSON --result LEARNING_RESULT_JSON --run-checks --report REPORT_JSON
python scripts/learnpack.py compare OLD_PACK NEW_PACK
```

合同工具依赖 Python 3.10+ 与 `jsonschema>=4.18`，Skill 文件工具另需 `PyYAML>=6`；依赖见 `scripts/requirements.txt`，建议使用项目或隔离环境。检查命令须亲核并取自已授权的本地测试；`--run-checks` 才实际执行 argv，不执行来源文档里的隐含指令。它不是沙箱。

检查在 `--workspace` 下运行，`python`/`python3` 使用当前解释器，`LEARN_SOURCE_ROOT` 环境变量提供显式材料根。合同中的来源路径相对该根，实践产物路径相对工作目录，便于迁移而不固定本机路径。

来源漂移、I/O 不符合 schema、实际检查失败/超时会返回非零，阻断本次机械检查通过。**只有实际接入此命令的任务/CI才获得该拦截**；Skill 文本不能拦截其它会话的任意写入。缺依赖时明确补齐或报告未执行，不把“可以校验”写成“已校验”。

`--report` 在检查执行前和落盘前拒绝覆盖本次合同、来源、I/O、已声明实践／结果及其证据、可识别的本地检查入口，包含现存硬链接等同文件别名；`fingerprint --out` 同样保护本次 `--file` 来源。两命令均保护工具自身及三份schema。独立报告／指纹文件仍可生成或更新。保护只覆盖声明及可识别的文件，不拦截检查命令任意行为或并发路径替换；错误信息在stdout，不保证无效输入也能生成报告文件。

`check` 自动检查包旁存在的 `LEARNING-RESULT.json`，也可用 `--result` 指定；按 `--workspace` 核设计解释、能力包与已宣称有结果的实践产物能否真实读取。可选 `consumer_trial` 记录目标消费者入口、产物与验证原件；外部入口用 `--consumer-root` 给根，产物／证据仍相对workspace。上述引用坏链、缺失、跨根或不符schema须失败，写“passed”不豁免；`unobserved`实践保待办，不因机械通过变成已执行。没有结果文件的中途诊断仍可检查，不能冒学习交付。工具不判领域覆盖、实践价值或艺术。

机械通过之后仍须核语义：是否兑现原目标、是否只拟合已知例子、是否转移风险、是否保持设计责任。涉及视觉/创作效果时亲看本次完整产物并取得相关反馈；自评分、字段齐全和测试绿灯不能认证效果。缺证时限对应结论，继续已授权且不依赖该结论的工作。

语义核查由当前 Agent 根据原件、实际结果和反例直接承担；工具中的 `semantic_review_required` 是待核知识提示，不要求外部陪审或另一人批准。对视觉、声音等对象，使用者/观看反馈按真实效果需要取得，不将反馈者设为学习过程的固定角色。

结果中的 `capability_pack` 相对workspace，只有该目录身份引用可用精确 `.` 表示工作根；仍须确为本次被查包。其它文件引用保持相对路径、存在性和越根检查；合同的失败／待观察trial产物不因输出保护而被要求预先生成。



自然语言委托和学习记录直接可用；选择结构化机械交付时，可用[学习输入 schema](../assets/learning-request.schema.json)和[输出 schema](../assets/learning-result.schema.json)，它们不是开始学习/修订的条件。`learning_depth` 可显式记 `systematic` 或 `targeted`，省略即按上述日常默认判断；`mode` 仍只区分 learn／update／apply。用户无需填表；已有范围足够就开始研究，真正影响目标或授权的未知才问。


`contract.json` 格式见 [合同 schema](../assets/contract.schema.json)。输入/输出使用内联 JSON Schema 2020-12。`hard` 规则须有真实用户要求、项目合同或已验证不变量作为依据；实现习惯、审美选择、解释假设分别用 `convention`、`heuristic`、`hypothesis`，不自动硬化。一次实践仅支持本次条件；没有效果反馈的创作方法保持候选或有限试用。
