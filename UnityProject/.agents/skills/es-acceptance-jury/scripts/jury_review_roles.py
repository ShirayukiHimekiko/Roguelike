"""Prepare selected roles of the current single-core workflow; never spawn or authorize a host.

inspect reads installed entries. prepare reads declared current host capabilities
and optional explicit user selection on stdin. Outputs are dispatch plans only.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys

import jury_read as reader
import jury_candidates as candidates
from jury_session import visible_text_present

ROLES = (
    ("progress", "progress-correctness.md", "progress_acceptance_jury"),
    ("architecture", "architecture-ecology-playability.md", "architecture_acceptance_jury"),
)
ROLE_FACTS = {"factContractVersion": 1, "presentationOwner": "dialogue",
              "presentationCommand": "jury_session.py probe --audience user"}
INDEPENDENT_JUDGMENT = '本人及其它AI首次形成的需求解释、方案、判断和产物，均是不可信候选；首判一律不可信。未经另一真实AI从原话/原件主动查可推翻条件、正向证据与适用正常并实际核验，不得作为事实/方案采用或任何依赖制作/扩量/放行/交付完成依据；接回者只按已核对象/条件/范围确认。仅无反例/低置信/同意/两票/签名/hash/ready不能释放；作者/F/A/root/旧模型/工具和审者新推断均无例外。读源/调查/隔离验证仅为核候选，不作产品先用；保用户授权/已证原件/独立就绪工作，不全局停工、不设概率、不改原增益或递归第三审。'
REQUIREMENT_MAPPING = '用户需求偏移须解释用户为什么要做、相对现状期望改变什么及保什么、什么结果才算兑现；实际输入/首任务/第一作者动作须承接期望变化与成功信号，不能只划边界或复述已核状态。真实差额核过改与空做；有据已满足/分析委托/必要保留不为凑改动而改。原AI方案/快照/比较控制不冒用户硬项；父前提被反证时核本后继依赖，成熟正常与同条件已核依据保。'

CONTINUITY_REMINDER = '执行优先：有效用户期望进入本次首任务/首动作，首次AI新结果仍待真实独核。活任务适用F/A职责不因completed/一次通过/上下文缩减解除，普通单critic不替F/A。同身份已知压缩、必要上下文不足或摘要冲突，先读原任务明确当前定位，核后到真实修订/作用域/权限/唯一writer、原意见闭权/预算和原operation终态，再做第一合法结果；不据旧摘要重放已完/unknown，不自动重建身份或新角色。实际事件/source/阶段和peer实收分别取证，无暴露仍unknown，不冒广播。同host按需真实followup；跨host按coordination.md#activation实接原意见/未闭/先验/在途，正式写须交域，历史ID/可读文件不认证身份或实收。'


def _inspect_installation(core: Path) -> dict:
    core = core.resolve()
    entry = core / "SKILL.md"
    present = entry.is_file()
    declared_name = None
    if present:
        text = reader.package_bytes(entry,core).decode("utf-8-sig")
        if text.startswith("---\n") or text.startswith("---\r\n"):
            for line in text.split("---", 2)[1].splitlines():
                if line.startswith("name:"):
                    declared_name = line.split(":", 1)[1].strip().strip("\"'")
    core_entry = {"skillPath": str(entry), "present": present,
                  "nameMatches": declared_name == "es-acceptance-jury"}
    roles = []
    for role, filename, task_name in ROLES:
        material = core / "references" / filename
        available = material.is_file() and bool(reader.package_bytes(material,core).decode("utf-8-sig").strip())
        roles.append({"role": role, "roleCardPath": str(material), "present": available,
                      "task_name": task_name, **ROLE_FACTS})
    guide = core / "references" / "unity-candidates.md"
    guide_present = guide.is_file() and bool(reader.package_bytes(guide,core).decode("utf-8-sig").strip())
    guide_readable = False
    guide_issue = None
    if guide_present:
        try:
            guide_readable = visible_text_present(re.sub(r'(?m)^\s*#{1,6}[ \t]+[^\n]*$', '', reader.read_section("references/unity-candidates.md#routing", core)["content"]))
        except (OSError, UnicodeError, ValueError) as exc:
            guide_issue = str(exc)
    judgement = core / "references" / "review-standard.md"
    judgement_present = judgement.is_file() and bool(reader.package_bytes(judgement,core).decode("utf-8-sig").strip())
    judgement_readable = False
    judgement_issue = None
    if judgement_present:
        try:
            judgement_readable = bool(candidates.expanded_reads(
                ["references/review-standard.md#decision-order"], core))
        except (OSError, UnicodeError, ValueError) as exc:
            judgement_issue = str(exc)
    candidate_readable = False
    message_guide = core / "references" / "coordination.md"
    message_readable = False
    message_issue = None
    try:
        content = reader.read_section("references/coordination.md#message-delivery", core)["content"]
        # A resolvable anchor or heading alone does not supply the contract.
        message_readable = visible_text_present(re.sub(r'(?m)^\s*#{1,6}[ \t]+[^\n]*$', '', content))
        if not message_readable:
            message_issue = "message-contract-visible-body-missing"
    except (OSError, UnicodeError, ValueError) as exc:
        message_issue = str(exc)
    continuity_selector = "references/coordination.md#activation"
    continuity_readable, continuity_issue = False, None
    try:
        content = reader.read_section(continuity_selector, core)["content"]
        continuity_readable = bool(candidates.expanded_reads([continuity_selector], core))
        if not continuity_readable:
            continuity_issue = "continuity-contract-visible-body-missing"
    except (OSError, UnicodeError, ValueError) as exc:
        continuity_issue = str(exc)
    required_review_selectors = (
        "references/review-standard.md#quality-blocking",
        "references/review-completion.md#completion-coverage",
        "references/candidate-collision.md#advancement-guidance",
    )
    required_review_readable, required_review_issue = False, None
    try:
        required_review_readable = bool(candidates.expanded_reads(required_review_selectors, core))
    except (OSError, UnicodeError, ValueError) as exc:
        required_review_issue = str(exc)
    candidate_issue = None
    try:
        candidate_index = candidates.load_index(core)
        candidate_readable = True
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        candidate_index = None
        candidate_issue = str(exc)
    for entry in roles:
        if candidate_index is not None:
            role_data = candidate_index["roles"][entry["role"]]
            entry["primaryProductChecks"] = role_data["productChecks"]
            entry["candidateSections"] = dict(
                obligations=list(dict.fromkeys(x["selector"] for x in role_data["obligations"])),
                productChecks=list(dict.fromkeys(x["selector"] for x in role_data["productChecks"])),
                productMethods={x["id"]:x["methodSelector"] for x in role_data["productChecks"]},
                sharedChecks=list(dict.fromkeys(x['selector'] for x in role_data['checks'] if x['id'] in role_data['sharedChecks'])),
                workBlocks={name: block["selector"] for name, block in role_data["blocks"].items()},
                directed=role_data["directedSelector"])
    return {"schemaVersion": 3, "operation": "role-inspect",
            "ready": present and core_entry["nameMatches"] and guide_readable and judgement_readable and message_readable and continuity_readable and required_review_readable and candidate_readable and all(x["present"] for x in roles),
            "coreEntry": core_entry, "roles": roles,
            "model": DEFAULT_MODEL,
            "reasoning_effort": DEFAULT_EFFORT,
            "fork_turns": "none", "reviewDomain": "unity-game-development",
            "candidateGuidePath": str(guide), "candidateGuidePresent": guide_present,
            "candidateGuideSection": "routing", "candidateGuideReadable": guide_readable, "candidateGuideIssue": guide_issue,
            "candidateMechanismPath": str(core / "references" / "candidate-mechanism.md"),
            "candidateMechanismSection": "selection",
            "candidateMechanismSelectors": (candidate_index["mechanismSections"] if candidate_index else []),
            "candidateRoutingPath": str(core / candidates.INDEX),
            "candidateMaterialsReadable": candidate_readable, "candidateMaterialsIssue": candidate_issue,
            "p0AuthorityPaths": {role:str(core/reference) for role,reference in candidates.P0_REFERENCES.items()},
            "p0ContractSelectors": candidates.P0_CONTRACTS, "commonP0ContractSelector": candidates.P0_SHARED_CONTRACT,
            "judgementGuidePath": str(judgement), "judgementGuideSection": "decision-order",
            "messageGuidePath": str(message_guide),
            "messageGuideSection": "message-delivery",
            "messageGuideReadable": message_readable, "messageGuideIssue": message_issue,
            "continuityContractSelector": continuity_selector,
            "continuityContractReadable": continuity_readable, "continuityContractIssue": continuity_issue,
            "requiredReviewContracts": list(required_review_selectors),
            "requiredReviewContractsReadable": required_review_readable,
            "requiredReviewContractsIssue": required_review_issue,
            "judgementGuidePresent": judgement_present,
            "judgementGuideReadable": judgement_readable, "judgementGuideIssue": judgement_issue,
            "readinessScope": "Each role has its own references P0 contract, catalogue and methods, plus shared judgement boundaries. No investigation, applicability completeness or semantic review is certified.",
            "autoExecute": False, "sourceAuthenticated": False}



def inspect_installation(core: Path) -> dict:
    with reader.reading_session(core):
        return _inspect_installation(core)

MAX_INPUT_BYTES=64*1024
DEFAULT_MODEL='gpt-6.1-sol'
DEFAULT_EFFORT='xhigh'
class InputError(ValueError): pass

def _object(value,allowed,required,label):
    if not isinstance(value,dict) or set(value)-allowed or required-set(value): raise InputError(label+' fields invalid')
def _string(value,label):
    if not isinstance(value,str) or not value.strip(): raise InputError(label+' must be nonempty text')
def _pairs(items):
    data={}
    for key,value in items:
        if key in data: raise InputError('duplicate input key: '+key)
        data[key]=value
    return data
def decode_input(raw):
    if len(raw)>MAX_INPUT_BYTES: raise InputError('input exceeds 64 KiB')
    try: return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=_pairs,parse_constant=lambda x: (_ for _ in ()).throw(InputError('nonfinite input')))
    except (UnicodeError,ValueError,RecursionError) as exc: raise InputError('invalid input JSON: '+str(exc)) from exc

TASK_ROLES=('worker','progress','architecture','dialogue')

def _canonical_reading_text(core, role, stage, domain):
    """Bind the selected reader route to the actual forwarded message."""
    root = Path(core or candidates.ROOT).resolve()
    script = str(root / 'scripts' / 'jury_read.py').replace("'", "''")
    command = "python -X utf8 -B '" + script + "'"
    return ('\n本职责实际读法（先按原需确定模式/有限批，再深读；不认证身份或权限）：\n'
      '先完整读本包入口：' + str(root / 'SKILL.md') + '\n'
      '本次已选领域/职责/阶段的canonical读取命令（PowerShell）：\n' + command +
      ' --profile ' + domain + ' --role ' + role + ' --review-stage ' + stage + '\n'
      '直接消费返回sections[].content；逐次按原样nextArgs续页，保持expect-snapshot，直到nextArgs=null；'
      'profile展开明确续文，不按下一HTML锚切父段，不漏嵌套小节。只显示当前必要正文，'
      '不要将含stdout的完整工具对象再次JSON转义或合并所有页；必要最终输出分片用'
      '--emit-page 0 --emit-bytes 6144，按outputSHA256/nextEmissionPage接完外层，再接内层nextArgs。\n'
      '恢复/已知上下文不足/摘要冲突时，先以原任务明确当前定位读取真实修订、权限/writer和原作业终态，再接首动作；不猜current或把压缩当新身份。'
      '任务已给精确外部定位时，同一读取器可用：' + command +
      " --material-file '<原任务给定的绝对原件路径>' --json-pointer '<原任务给定的RFC6901 pointer>'；"
      'Markdown用--material-anchor替代pointer。路径/pointer/anchor逐字取本任务原件或首动作已给定位，'
      '未给则先核原件，不猜current/最新/尾段；按返回rawSHA/快照和nextArgs核完整材料。'
      '用户指定工具、直接完整读取及其它保完整段落/续文的成熟读法仍合法；本命令不覆盖用户指定手段。\n'
      '规划认可转作者开工、巡查/只读/学习批交回及自然成果后的阶段接续时，实际读取：' + command +
      ' --section references/review-completion.md#stage-continuation --follow\n'
      '按该正文从完整有效目标核已授权必要或有据有值工作，包括直接制作、补专业/原创供给与真正受阻路径，再核原owner实收及作者动作；局部准停不准父停。原owner在途/已投未消费接原后继去重，报告/ACK不代作者后继；各窗自主定下一成果。\n')

def task_packet(observation,core=None,include_routes=True):
    """Prepare real work text, not host dispatch, authority or understanding."""
    _object(observation,{'currentScope','reviewStage','reviewDomain','inputMode','task'}, {'currentScope','task'},'packet')
    scope=observation['currentScope'];_object(scope,{'kind','id'},{'kind','id'},'currentScope')
    for key in scope:_string(scope[key],'currentScope.'+key)
    # Packet scope.kind was and remains an opaque nonempty identity label.
    # Host/model preparation has its own pre-existing container schema below.
    input_mode=observation.get('inputMode','independent-first')
    if input_mode not in ('independent-first','legacy-complete'):raise InputError('inputMode invalid')
    domain=observation.get('reviewDomain','general')
    if domain not in candidates.PROFILE_DOMAINS:raise InputError('reviewDomain invalid')
    task=observation['task']
    _object(task,{'taskId','waveId','userRequest','sourceRefs','expectedResult','artifacts','constraints','assignments','returnTo'},
      {'taskId','waveId','userRequest','sourceRefs','expectedResult','artifacts','constraints','assignments','returnTo'},'task')
    for key in ('taskId','waveId','userRequest','expectedResult','returnTo'):_string(task[key],'task.'+key)
    if task['taskId']!=scope['id']:raise InputError('task identity differs from currentScope.id')
    for key in ('sourceRefs','artifacts','constraints'):
        values=task[key]
        if not isinstance(values,list) or len(values)>64:raise InputError('task.'+key+' requires bounded list')
        for value in values:_string(value,'task.'+key)
    if not task['sourceRefs'] or not task['artifacts']:raise InputError('task needs original sources and consumable artifacts')
    jobs=task['assignments']
    _object(jobs,set(TASK_ROLES),set(),'task.assignments')
    if not jobs:raise InputError('task needs actual work assignments')
    for role,job in jobs.items():
        _object(job,{'result','firstAction','methods','contextSources'},{'result','firstAction','methods'},'assignment.'+role)
        for key in ('result','firstAction'):_string(job[key],'assignment.'+role+'.'+key)
        if not isinstance(job['methods'],list) or not job['methods'] or len(job['methods'])>16:raise InputError('assignment needs real method/source locations')
        for value in job['methods']:_string(value,'assignment.methods')
    stage,selection=candidates.review_stage(observation['reviewStage']) if 'reviewStage' in observation else candidates.review_stage()
    if stage=='unresolved':return dict(ready=False,status='stage-unresolved',taskId=task['taskId'],waveId=task['waveId'],nativeTasks={},autoExecute=False,
      reason='Caller must determine planning or mature review from this task, without an extra user approval.')
    common='用户原文：'+task['userRequest']+'\n原始来源：'+'；'.join(task['sourceRefs'])+'\n原件：'+'；'.join(task['artifacts'])+'\n已知控制/风险（核其来源，缺证不授新权）：'+'；'.join(task['constraints'])
    messages={};contexts={};complete={};unresolved=[];first_contexts={}
    for role,job in jobs.items():
        messages[role]='任务 '+task['taskId']+' / 波次 '+task['waveId']+' / 阶段 '+stage+' / 职责 '+role+'\n'+common+'\n受托结果（回原需核定）：'+task['expectedResult']+'\n本职责实际成果：'+job['result']+'\n'+CONTINUITY_REMINDER+'\n'+INDEPENDENT_JUDGMENT+'本次首作业：依本人角色合同亲核完整原需及原件，先给当前必要结果、主要差距、能推翻路线的条件与合法正常，再提出有据的下一完整作者结果/查证及消费者；首判断保候选，按独立核验合同采用。用户明确指定的工序/工具/格式和已核成熟本职动作仍须完整首发执行；没有必要新变化时复用成熟同条件证据。公开命题依据、限制和实际动作，不索隐藏思维链。\n接回：'+task['returnTo']+'；本人回件含原分/事件和basis.userNeed、basis.actualUse各自source/evidence/disposition/action，必要结果未证按wave-gain负分，局部收益不抵成0。'+REQUIREMENT_MAPPING
        contexts[role]='任务 '+task['taskId']+' / 波次 '+task['waveId']+' / 职责 '+role+'\n完整派发动作输入（原来源未由工具认证，不机械视为AI修法）：\n首动作：'+job['firstAction']+'\n方法/源：'+'；'.join(job['methods'])+'\n实际caller按原话/已核事实区分用户指定、成熟本职工作、已知风险与新推断；前三类完整进入首发，只有未核推荐修法/预期答案在真实首判断后交。来源未知先核对应来源，不由工具猜归属或新增用户批准。'
        messages[role]+=_canonical_reading_text(core,role,stage,domain)
        complete[role]=messages[role]+'\n'+contexts[role]
        # The caller binds each actual work item to its real source; neither kind nor a file proves truth.
        items=[job['firstAction'],*job['methods']]
        sources=job.get('contextSources')
        selected=[]
        if sources is None:
            unresolved.append(role)
            selected=list(items)  # Original schema is a real commissioned work path, not automatically inferred answers.
        else:
            if not isinstance(sources,list) or len(sources)!=len(items):raise InputError('contextSources must bind firstAction and each method in order')
            for item,basis in zip(items,sources):
                _object(basis,{'kind','sourceRef'},{'kind','sourceRef'},'context source')
                if basis['kind'] not in ('user-selected','evidenced-work','known-control','new-inference'):raise InputError('context source kind invalid')
                _string(basis['sourceRef'],'context.sourceRef')
                if basis['kind']!='new-inference':selected.append(item+' [来源：'+basis['sourceRef']+'；'+basis['kind']+']')
        first_contexts[role]='\n'.join(selected)
        if selected:messages[role]+='\n首发有据本职材料（由实际caller核原来源）：\n'+first_contexts[role]
    native=complete if input_mode=='legacy-complete' else messages
    dispatch_ready=True
    route_refs={role:candidates.read_profile(core or candidates.ROOT,role=role,stage=stage,domain=domain)['readSelectors'] for role in jobs} if include_routes else {}

    return dict(ready=dispatch_ready,status='packet-ready' if dispatch_ready else 'input-source-unresolved',
      taskId=task['taskId'],waveId=task['waveId'],currentScope=dict(scope),scopeAuthenticated=False,
      reviewStage=stage,reviewDomain=domain,domainSelectionSource='explicit' if 'reviewDomain' in observation else 'default-shared-contracts',
      domainApplicabilityVerified=False,stageSelectionSource=selection,
      inputMode=input_mode,nativeTasks=native,primaryTasks=messages,callerContexts=contexts,
      legacyTasks=complete,readSelectorsByRole=route_refs,unresolvedContextRoles=unresolved,
      contextSourceResolved=not unresolved,autoExecute=False,sourceAuthenticated=False,semanticContentVerified=False,
      reason='Default nativeTasks contains original work and source-bound user/mature/control items. New inference is later context. Packet kind is an opaque original identity label, not a domain or host permission. Domain routing does not certify applicability or remove actual-object contracts. Original-schema firstAction/methods remain commissioned first work; caller verifies actual source and withholds identified new answers. Unknown metadata is not a new approval/schema gate. Declared sources are not authenticated. Explicit legacy-complete preserves old material for compatible reproduction; actual first dispatch still obeys independent-input.')


def _prepare(observation,core):
    _object(observation,{'currentScope','availableModels','selection','paused','cancelled','existingAgents','dispatchContext','roles','reviewStage','reviewDomain','inputMode','task'},{'currentScope','availableModels'},'input')
    stage,stage_source=candidates.review_stage(observation['reviewStage']) if 'reviewStage' in observation else candidates.review_stage()
    if len(json.dumps(observation,ensure_ascii=False).encode('utf-8'))>MAX_INPUT_BYTES: raise InputError('input exceeds 64 KiB')
    scope=observation['currentScope']
    _object(scope,{'kind','id'},{'kind','id'},'currentScope')
    if scope['kind'] not in ('task','session','project','installation'): raise InputError('currentScope.kind invalid')
    _string(scope['id'],'currentScope.id')
    for key in ('paused','cancelled'):
        if key in observation and type(observation[key]) is not bool: raise InputError(key+' must be boolean')
    dispatch_context=observation.get('dispatchContext')
    if observation.get('paused') or observation.get('cancelled'):
        return dict(schemaVersion=3,operation='role-prepare',ready=False,dispatch=[],
          reviewStage=stage,stageSelectionSource=stage_source,
          currentScope=dict(scope),dispatchContext=dispatch_context,hostContextAuthenticated=False,
          status='held',reason='Current pause/cancellation prevents dispatch; package inspection deferred.',
          readinessScope='Not inspected while held.',autoExecute=False,sourceAuthenticated=False)
    if stage=='unresolved':
        return dict(schemaVersion=3,ready=False,status='stage-unresolved',dispatch=[],reviewStage=stage,
          stageSelectionSource=stage_source,autoExecute=False,reason='Caller must first determine this task stage; no implicit detailed review.')
    if 'task' not in observation:
        return dict(schemaVersion=3,ready=False,status='task-unresolved',dispatch=[],reviewStage=stage,autoExecute=False,
          reason='Supply the real task packet: original request/source, artifacts, boundaries and actual role work, not only scope metadata.')
    packet=task_packet({key:observation[key] for key in ('currentScope','reviewStage','reviewDomain','inputMode','task') if key in observation},core,include_routes=False)
    if not packet['ready']:
        return dict(schemaVersion=3,ready=False,status=packet['status'],dispatch=[],unresolvedContextRoles=packet['unresolvedContextRoles'],
          taskId=packet['taskId'],waveId=packet['waveId'],autoExecute=False,sourceAuthenticated=False,reason=packet['reason'])
    domain=packet['reviewDomain']
    selected=observation.get('roles',[role for role,_,_ in ROLES])
    if not isinstance(selected,list) or not 1 <= len(selected) <= len(ROLES): raise InputError('roles must select one or two roles in dispatch order')
    if any(not isinstance(role,str) or role not in {x[0] for x in ROLES} for role in selected) or len(set(selected))!=len(selected):
        raise InputError('roles must contain distinct progress/architecture values')
    try:
        result=inspect_installation(core) if domain=='unity' else _inspect_profile_installation(core,selected,stage,domain)
    except (OSError,candidates.CandidateError,KeyError) as exc:
        return dict(schemaVersion=3,ready=False,status='missing-stage-material',dispatch=[],reason=str(exc),autoExecute=False)
    catalogue={entry['role']:entry for entry in result['roles']}
    result['roles']=[catalogue[role] for role in selected]
    result.update(operation='role-prepare',dispatch=[],currentScope=dict(scope),dispatchContext=dispatch_context,hostContextAuthenticated=False,
      reviewStage=stage,stageSelectionSource=stage_source)
    if 'dispatchContext' in observation and dispatch_context not in ('same-host','cross-window'): raise InputError('dispatchContext must be same-host or cross-window')
    existing=observation.get('existingAgents',{})
    _object(existing,{x[0] for x in ROLES},set(),'existingAgents')
    for role,identifier in existing.items(): _string(identifier,'existingAgents.'+role)
    if existing and dispatch_context is None:
        return {**result,'status':'dispatch-context-unresolved','unclassifiedAgentRefs':dict(existing),'reason':'Nonempty role references require an actual same-host or cross-window context declaration. No followup, resume or dispatch is prepared; preserve these references without authenticating them.'}
    if dispatch_context is None: dispatch_context='same-host'
    result['dispatchContext']=dispatch_context
    if not result['ready']: return {**result,'status':'missing-role-material','reason':'Core, role, candidate, judgement or message material is absent/empty/mismatched.'}
    models=observation['availableModels']
    if not isinstance(models,list) or len(models)>64: raise InputError('availableModels must be bounded array')
    capabilities={}
    for entry in models:
        _object(entry,{'modelId','efforts','family','supportsEffort'},{'modelId','efforts'},'model')
        model=entry['modelId']; _string(model,'modelId')
        efforts=entry['efforts']; supports=entry.get('supportsEffort',True)
        if type(supports) is not bool or not isinstance(efforts,list) or len(efforts)>16: raise InputError('model efforts invalid')
        for effort in efforts: _string(effort,'effort')
        if len(set(efforts))!=len(efforts) or (not supports and efforts) or model in capabilities: raise InputError('duplicate or contradictory capabilities')
        family=entry.get('family')
        if family is not None and family not in ('astra','sol','luna'): raise InputError('model family invalid')
        known_family={'gpt-6-astra':'astra',DEFAULT_MODEL:'sol'}.get(model)
        if known_family is not None:
            if family is not None and family!=known_family: raise InputError('model family contradicts known modelId')
            family=known_family
        capabilities[model]=(efforts,supports,family)
    model,effort,source=DEFAULT_MODEL,DEFAULT_EFFORT,'skill-policy'
    if 'selection' in observation:
        choice=observation['selection']
        _object(choice,{'modelId','effort','sourceKind','messageRef','rawText','responseKind','scope','revoked'},
          {'modelId','sourceKind','messageRef','rawText','responseKind','scope','revoked'},'selection')
        for key in ('modelId','sourceKind','messageRef','rawText','responseKind'): _string(choice[key],'selection.'+key)
        if 'revoked' in choice and type(choice['revoked']) is not bool: raise InputError('revoked must be boolean')
        if choice['sourceKind']!='direct-user' or choice['responseKind']!='model-choice' or choice['scope']!=scope or choice.get('revoked'):
            return {**result,'status':'model-unresolved','reason':'Declared choice does not match current direct-user evidence/scope.'}
        model=choice['modelId']; source='direct-user'
        capability=capabilities.get(model)
        if capability is None: return {**result,'status':'model-unavailable','reason':'Explicit model unavailable; no substitute.'}
        effort=choice.get('effort', DEFAULT_EFFORT if model==DEFAULT_MODEL else {'astra':'high','sol':'xhigh','luna':'xhigh'}.get(capability[2],DEFAULT_EFFORT))
        if not capability[1]:
            if choice.get('effort') is not None: return {**result,'status':'model-unresolved','reason':'Explicit effort contradicts host no-effort capability.'}
            if 'effort' not in choice: return {**result,'status':'model-unavailable','reason':'Policy default effort is unsupported; an explicit user choice is required to omit the effort parameter. No downgrade.'}
            effort=None
    if model not in capabilities or (effort is not None and effort not in capabilities[model][0]) or (effort is None and capabilities[model][1]):
        return {**result,'status':'model-unavailable','reason':'Required model/effort unavailable or unspecified; no substitute.'}
    current_existing=existing if dispatch_context=='same-host' else {}
    if len(set(current_existing.values()))!=len(current_existing): raise InputError('Independent roles cannot share one Agent identity')
    result['historicalAgentRefs']=dict(existing) if dispatch_context=='cross-window' else {}
    calls=[]
    by_role={entry['role']:entry for entry in result['roles']}
    for role in selected:
        if role not in packet['nativeTasks']:raise InputError('task assignment missing for selected role: '+role)
        entry=by_role[role]
        try:
            selectors=candidates.read_profile(core,role,stage,domain)['readSelectors']
        except candidates.CandidateError as exc:
            return {**result,'ready':False,'status':'missing-stage-material','dispatch':[],'reason':str(exc)}
        call=dict(role=entry['role'],action='followup' if entry['role'] in current_existing else 'spawn',
          taskId=packet['taskId'],waveId=packet['waveId'],taskText=packet['nativeTasks'][role],
          primaryTaskText=packet['primaryTasks'][role],callerContextText=packet['callerContexts'][role],contextSourceResolved=packet['contextSourceResolved'],
          coreSkillPath=result['coreEntry']['skillPath'],roleCardPath=entry['roleCardPath'],readSelectors=selectors,
          workBlockSelectors=entry['candidateSections']['workBlocks'],candidateGuidePath=result['candidateGuidePath'],candidateGuideSection='routing',
          workspaceGuideSelector=candidates.WORKSPACE_GUIDE,crossCuttingWorkspaceSelectors=candidates.CROSS_CUTTING_WORKSPACES,usabilityMethodSelector=candidates.USABILITY_METHOD,
          gameQualityReminder='Read source-authority.md#current-mainline and review-standard.md#decision-order for full required outcomes/quality. Consume applicable selectors; author batches/checks do not redefine success.',
          messageGuidePath=result['messageGuidePath'],messageGuideSection='message-delivery',
          candidateRoutingPath=result['candidateRoutingPath'],model=model,fork_turns='none',task_name=entry['task_name'],
          executionObligationsAreProductP0=False,continuityContractSelector=result['continuityContractSelector'],
          initialReviewInputContractSelector=candidates.INDEPENDENT_INPUT_CONTRACT,
          initialReviewInputPolicy='original-user-goal-and-primary-artifacts-first',
          authorInterpretationsStage='after-independent-first-opinion',
          initialInputIndependenceVerified=False,
          initialReviewInputReminder=CONTINUITY_REMINDER+INDEPENDENT_JUDGMENT+' Independent verification, not automatic rejection. Under coordination.md#independent-input, judge original user needs/primary artifacts before author/peer explanations; preserve first judgment/counterevidence through replies and route renewal. Revise only on checked facts or corrected reasoning. Share known failures/safety immediately; preserve actual exposure and valid evidence.',
          evidenceStopReminder='Use verification-scope.md#relevance for real impact and valid-evidence reuse. Under must-read-work-priority.md#continue-or-change distinguish local correctness, goal contribution and parent support; apply the decision to the next real author/consumer action. A useful patch does not renew a challenged parent premise. Preserve evidenced local convergence, informative research and technical commissions.',
          primaryProductChecks=entry['primaryProductChecks'],
          productMethodSelectors=entry['candidateSections']['productMethods'],
          p0AuthorityPath=result['p0AuthorityPaths'][entry['role']],p0ContractSelector=result['p0ContractSelectors'][entry['role']],commonP0ContractSelector=result['commonP0ContractSelector'],
          knowledgeLookupGuideSelector=candidates.KNOWLEDGE_GUIDE,knowledgeIndexSelector=candidates.KNOWLEDGE_INDEX,
          knowledgeLookupRequiredWhen=list(candidates.KNOWLEDGE_TRIGGERS),
          knowledgeLookupReminder='On blockage, specific high risk or explicit quality/fidelity/precision/performance demands, apply reading-guide.md#knowledge-use to this object/next action. Reuse valid findings; no match means source investigation, not whole-library rereading.',
          projectContextSelector=candidates.PROJECT_CONTEXT,
          projectDecisionSelectors=list(candidates.PROJECT_DECISIONS),
          projectReviewReminder='For target-project action read project-understanding.md#project-fit and project-workspace.md#workspace: authority, sources, entries/bindings and old consumers. Unknowns restrict dependencies. Skill maintenance uses package consumers, not a game baseline.',
          commonFailureMethodSelector='references/review-standard.md#failure-continuation',
          responsibilityReminder='Under must-read-work-priority.md#route-leadership lead the next necessary result within your remit; verify author action and consumer, correct drift and share cross-role facts. Dialogue actively observes/questions, without dense reporting; the native background worker alone writes production. Prepare has only F/A. Preserve independent judgment, worker counterevidence and original veto closure.',
          evidenceReminder='Read available primary source/assets/observations before new execution. Complete visual originals and dynamics follow the actual claim. Generation/recovery/retirement use evidence-lifecycle.md. Preserve corrections under review-correction.md#workflow-correction; dialogue renders the user event.',
          p0ReviewReminder='Apply review-standard.md#quality-blocking and p0-review.md#review-contract to necessary gaps, missed investigation or useless content/steps. State P0 blocked and returned for the affected choice; preserve useful research/safeguards, independent authorized work and original closure. Unknown is not fabricated failure. Before ending use review-completion.md#completion-coverage.',
          roleP0Responsibility=('Before dependent ordinary work independently verify business authority, old entry paths and continuation under project-fit. Check business authority and outcomes: operations, rules/economy/ownership, unit/world states, persistence/continuation and key feedback. Include required author production/editing, save/reload and actual adoption paths at the commissioned delivery stage. Visual/technical verdicts cannot replace these.' if entry['role']=='progress' else 'Before dependent ordinary work independently trace real owners, entry points, sources and bindings under project-fit; block missing necessary understanding and ecology violations. Apply references/p0-architecture.md#project-tracking: establish the whole-project technical baseline on first project takeover, when the baseline is missing/invalid, or when major structural change requires it. For subsequent reviews reuse still-valid evidence and trace affected dependencies, unchanged consumers and open issues; a new batch or window alone does not require rebuilding the baseline. Preserve whole-project coverage and do not limit discovery to the current diff or reported symptoms; missing whole-project coverage prevents whole-project acceptance, not supported scoped conclusions or independent work. Own identity/isolation, resources/environment, UI/spatial access, continuous audiovisual behavior and load/lifetime. Transfer business verdicts to progress.'),
          deliveryReminder='Use coordination.md#message-delivery and source-authority.md#grounded-consideration. Keep actual role/state, object/version, original integer/scope/event and full necessary opinion; user projection preserves original scores/main events and gives meaningful responsibility/judgment/change without allocated agent names. Retain same-wave score/history and both personal grounds; no new mandatory mapping fields. '+REQUIREMENT_MAPPING+' Unverifiable required results need negative scores; missing scores follow wave-gain. Dialogue alone renders user layout via probe. Keep task-plan.md#task-tracking progress/risk facts; send user control to affected responsibilities before long analysis, verify receipt/in-flight outcome rather than queue status. Tools certify no identity, semantics or authority.',**ROLE_FACTS)
        if effort is not None: call['reasoning_effort']=effort
        if entry['role']=='architecture':call.update(projectTrackingSelector=candidates.P0_ARCHITECTURE_TRACKING,projectReviewScope='whole-project-baseline-and-dependency-tracking')
        call.update(reviewStage=stage,stageSelectionSource=stage_source)
        if stage=='planning':
            call.update(firstReviewTask=candidates.PLANNING_TASK,stageDetailPolicy=candidates.PLANNING_DETAIL_POLICY)
            call['gameQualityReminder']='Planning: read the current planning selectors and perform firstReviewTask within stageDetailPolicy; do not duplicate their full text or treat a limited route judgment as production permission.'
            call['projectReviewReminder']='Before a supported route/limited planning judgment, independently verify real goals, author/source/entry authority, current permission and old-consumer relations, and the supply/method premises that can change this route or current safe action. Unknown necessary relations restrict dependent decisions. Do not require every later module audit before judging route value. Before ordinary production/adoption verify all dependencies of that action; whole-project architecture acceptance still needs its complete baseline. Read project-understanding.md#project-fit and p0-architecture.md#project-tracking when applicable; reuse valid evidence.'
            call['roleP0Responsibility']=('Independently verify current business authority, needed actions/feedback/continuation and route quality from the original goal; do not replace choices/consequences with API or completed-check counts. Current protection risks constrain dependent actions immediately.' if role=='progress' else 'Independently verify the current route-critical authority/source/binding, method/supply, spatial/continuous and load assumptions. Known protection risks constrain dependent actions immediately. Detailed baseline coverage follows actual dependencies and is required before whole-project acceptance, not a universal prerequisite to a limited route judgment.')
            if role=='architecture':call['projectReviewScope']='route-critical-relations-now; whole-project-baseline-before-whole-project-acceptance'
        call['reviewDomain']=domain
        if domain!='unity':
            # The actual dispatch contains this domain's contracts, never Unity catalogue/P0 claims.
            retained=('role','action','taskId','waveId','taskText','readSelectors','coreSkillPath','roleCardPath',
              'model','reasoning_effort','fork_turns','task_name','reviewStage','stageSelectionSource','reviewDomain',
              'initialReviewInputContractSelector','initialReviewInputPolicy','initialInputIndependenceVerified',
              'contextSourceResolved','deliveryReminder','responsibilityReminder','autoExecute')
            call={key:value for key,value in call.items() if key in retained}
        if entry['role'] in current_existing: call.update(target=current_existing[entry['role']],capabilityNote='Verify this current window identity/model, state and real send/return capability before followup. A historical address is not proof.')
        elif dispatch_context=='cross-window': call['capabilityNote']='Create new native identities in the current window; old references are history only. Do not resume old sessions.'
        calls.append(call)
    if stage=='planning':result['readinessScope']='Planning material declarations only; route quality, current production dependencies, investigation, identity and permissions are not certified.'
    return {**result,'roles':[by_role[name] for name in selected],'status':'prepared','taskId':packet['taskId'],'waveId':packet['waveId'],'model':model,'reasoning_effort':effort,'selectionSource':source,'dispatch':calls,
      'nonClaims':['No Agent spawned/resumed.','Declared evidence does not authenticate user control or identity.','Prepared material does not certify investigation or product behavior.']}

def prepare(observation,core):
    with reader.reading_session(core):
        return _prepare(observation,core)

def _inspect_profile_installation(core, selected, stage, domain):
    core=Path(core).resolve()
    raw=reader.package_bytes(core/'SKILL.md',core).decode('utf-8-sig')
    matches=bool(re.search(r'(?m)^name: es-acceptance-jury\s*$',raw))
    records=[]
    for role,filename,task_name in ROLES:
        if role not in selected:continue
        candidates.read_profile(core,role,stage,domain)
        records.append(dict(role=role,roleCardPath=str(core/'references'/filename),task_name=task_name,
          present=True,primaryProductChecks=[],candidateSections=dict(sharedChecks=[],obligations=[],productChecks=[],
          productMethods={},workBlocks={}),**ROLE_FACTS))
    # Keep the internal compatibility shape; non-Unity dispatch strips inapplicable fields below.
    return dict(schemaVersion=3,ready=matches,operation='role-inspect',reviewDomain=domain,roles=records,
      coreEntry=dict(skillPath=str(core/'SKILL.md'),present=True,nameMatches=matches),
      p0ContractSelectors={x:None for x in selected},p0AuthorityPaths={x:None for x in selected},
      commonP0ContractSelector=None,candidateMechanismSelectors=[],candidateGuidePath=None,candidateRoutingPath=str(core/candidates.INDEX),
      messageGuidePath=str(core/'references/coordination.md'),continuityContractSelector='references/coordination.md#activation',
      readinessScope='Only applicable profile material is readable; no authority, investigation or semantic acceptance certified.',
      sourceAuthenticated=False,autoExecute=False)


def selected_output(result, operation, role=None, view='first'):
    """One consumable view for the actual CLI; full API/legacy material remains explicitly available."""
    if view=='full':return result
    if operation=='packet':
        field={'first':'nativeTasks','context':'callerContexts','legacy':'legacyTasks'}[view]
        tasks=result.get(field,{})
        if role is not None:
            tasks={role:tasks[role]} if role in tasks else {}
            result={**result,'readSelectorsByRole':{role:result.get('readSelectorsByRole',{}).get(role,[])}}
        return {**{k:v for k,v in result.items() if k not in ('primaryTasks','callerContexts','legacyTasks','nativeTasks')},
                'selectedView':view,'nativeTasks':tasks}
    if operation=='prepare':
        dispatch=[]
        for item in result.get('dispatch',[]):
            if role is not None and item['role']!=role:continue
            omitted={'primaryTaskText','callerContextText'}
            call={k:v for k,v in item.items() if k not in omitted}
            if view=='context':call['taskText']=item.get('callerContextText','')
            elif view=='legacy':call['taskText']=item.get('primaryTaskText',item['taskText'])+'\n'+item.get('callerContextText','')
            dispatch.append(call)
        keep=('schemaVersion','ready','status','taskId','waveId','model','reasoning_effort','selectionSource','reviewDomain',
              'reviewStage','stageSelectionSource','reason','unresolvedContextRoles','autoExecute','sourceAuthenticated','nonClaims')
        return {**{k:v for k,v in result.items() if k in keep},'selectedView':view,'dispatch':dispatch}
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog='''inspect checks installed material only. packet and prepare read one UTF-8 JSON object on stdin (at most 64 KiB).
packet: currentScope {kind,id}, explicit reviewStage planning|review, and task.
task: taskId (matching currentScope.id), waveId, userRequest, sourceRefs, expectedResult,
artifacts, constraints, assignments, returnTo. Each actual assignment has result,
firstAction and methods. Default independent-first binds contextSources in order to
firstAction then each method: {kind:user-selected|evidenced-work|known-control|new-inference,
sourceRef:actual-original-location}. Only new-inference is delayed. Original-schema work remains first input;
caller verifies source and withholds identified new answers without a new schema gate. inputMode=legacy-complete explicitly
retains the original complete view. Declared references do not authenticate sources.
Include user-selected/mature work and known risks in the first message; delay only
new inferred fixes/answer context until the real independent first result. No source
classification, release or independence is authenticated by these fields.
prepare adds availableModels and actual selected progress/architecture roles to the
same input; taskText now follows independent-first by default. reviewDomain is
general(default shared contracts)|maintenance|unity, independent of currentScope.kind.
Packet accepts the original nonempty scope labels; prepare retains its existing typed
task/session/project/installation host/model-control containers. Neither scope nor
domain declares authority or excludes applicable object-quality contracts. Default CLI
returns one first view; --role selects a receiver and --view context|legacy|full makes
other material explicit. --emit-page/--emit-bytes bound final JSON via jury_io.
Omitted stage returns stage-unresolved. Missing task returns task-unresolved.
The caller determines routine task stage; no additional user approval is required.
Mature supported repairs may explicitly select review. Pause/cancellation remains held.
Optional dispatchContext/existingAgents and direct-user model selection retain their
original identity/model boundaries. Neither path sends messages or authenticates
user authority, facts, identity or understanding. See juror-prompt.md#task-packet.''')
    parser.add_argument('operation',choices=('inspect','prepare','packet'))
    parser.add_argument('--role',choices=TASK_ROLES,help='Return one actual role, not repeated full dispatches')
    parser.add_argument('--view',choices=('first','context','legacy','full'),default='first')
    parser.add_argument('--emit-page',type=int)
    parser.add_argument('--emit-bytes',type=int,default=None)
    parser.add_argument('--expect-emission')
    args=parser.parse_args(argv)
    core=Path(__file__).resolve().parents[1]
    try:
        if args.emit_bytes is not None and args.emit_page is None:raise InputError('--emit-bytes requires --emit-page')
        if args.expect_emission is not None and args.emit_page is None:raise InputError('--expect-emission requires --emit-page')
        if args.operation=='inspect':result=inspect_installation(core)
        else:
            observation=decode_input(sys.stdin.buffer.read(MAX_INPUT_BYTES+1))
            result=task_packet(observation) if args.operation=='packet' else prepare(observation,core)
    except (InputError,OSError,UnicodeError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='invalid-input',reason=str(exc),autoExecute=False))); return 2
    exit_code=0 if result.get('ready') and result.get('status','prepared') in ('prepared','packet-ready') else 3
    result=selected_output(result,args.operation,args.role,args.view)
    if args.emit_page is not None:
        from jury_io import emission_page
        try:result=emission_page(result,args.emit_page,6144 if args.emit_bytes is None else args.emit_bytes,args.expect_emission)
        except ValueError as exc:
            print(json.dumps(dict(status='invalid-input',reason=str(exc),autoExecute=False)));return 2
    print(json.dumps(result,ensure_ascii=False,indent=2)); return exit_code
if __name__=='__main__': raise SystemExit(main())
