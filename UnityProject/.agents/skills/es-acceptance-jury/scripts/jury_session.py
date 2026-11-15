"""Current literal message relay and visible-body check; no session or host writes."""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
MAX_RECORD=4*1024*1024
MESSAGE_CONTRACT_VERSION=7
def _display_lines(value):
    """Extract the existing visible Markdown subset without authenticating a role.

    Keep original text/hashes untouched. Raw HTML and code cannot supply a
    marker or body; quoted prose can supply a body, never a root marker.
    """
    if not isinstance(value, str):
        return []

    lines, fence, quoted, html, definition, comment = [], None, False, [], False, False
    void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def html_line(line):
        # Markdown autolinks are visible text, not raw HTML containers.
        markup = re.sub(r'<(?:[A-Za-z][A-Za-z0-9+.-]{1,31}:[^ <>]*|[^ <>@]+@[^ <>@]+)>', '', line)
        tags = list(re.finditer(r'<(/?)([A-Za-z][\w:-]*)(?=[\s/>]|$)[^>]*(?:>|$)', markup))
        was_html = bool(html)
        for tag in tags:
            closing, name = tag[1], tag[2].lower()
            if closing and name in html:
                del html[len(html) - 1 - html[::-1].index(name):]
            elif not closing and name not in void_tags and not tag[0].endswith('/>'):
                html.append(name)
        return was_html or bool(html) or bool(tags) or bool(re.search(r'<[!?]', line))
    def comment_line(line):
        nonlocal comment
        contains_comment, offset = comment, 0
        while True:
            token = '-->' if comment else '<!--'
            found = line.find(token, offset)
            if found < 0:
                return contains_comment
            contains_comment = True
            comment = not comment
            offset = found + len(token)

    for line in value.splitlines():
        if comment:
            comment_line(line)
            continue
        quote = re.match(r' {0,3}>[ \t]?(.*)$', line)
        if fence is not None:
            run, quote_fence = fence
            if quote_fence and not quote:
                # A quote's fenced code cannot continue without its container.
                fence, quoted = None, False
            else:
                candidate = quote[1] if quote_fence else line
                closing = re.match(r' {0,3}(`{3,}|~{3,})[ \t]*$', candidate)
                if closing and closing[1][0] == run[0] and len(closing[1]) >= len(run):
                    fence = None
                continue
        # Comments are syntax only outside code. Ignore the entire mixed line
        # rather than joining fragments into a counterfeit marker.
        if comment_line(line):
            continue
        if html:
            html_line(line)
            continue
        if not line.strip():
            quoted, definition = False, False
            continue
        if quote:
            quoted = True
            line = re.sub(r'^(?: {0,3}>[ \t]?)+', '', line)
        match = re.match(r' {0,3}(`{3,}|~{3,})(.*)$', line)
        if match:
            fence = (match[1], bool(quote))
            continue
        if line.startswith(('    ', '\t')):
            continue
        if html_line(line):
            continue
        if re.match(r' {0,3}\[[^\]]+\]:', line):
            definition = True
        if definition:
            continue
        body = re.sub(r'(`+).*?\1', '', line)
        lines.append((line if not quoted else None,any(c.isalnum() for c in body)))
    return lines


def visible_text_present(value):
    """Content presence only; no opinion, identity, gain or event semantics checked."""
    return any(has_body for _, has_body in _display_lines(value))



def _read(filename,limit=MAX_RECORD):
    path=Path(filename)
    if not path.is_absolute(): raise ValueError('absolute source path required')
    with path.open('rb') as stream: raw=stream.read(limit+1)
    if len(raw)>limit: raise ValueError('message exceeds byte capacity: '+str(path))
    return path,raw

def check_message(text,version=MESSAGE_CONTRACT_VERSION):
    if version!=MESSAGE_CONTRACT_VERSION: raise ValueError('historical message contract withdrawn; consult archived original')
    passed=visible_text_present(text)
    return dict(passed=passed,reason=None if passed else 'visible-body-missing',contractVersion=MESSAGE_CONTRACT_VERSION,
      scope='selected-message-content-presence-only',semanticContentVerified=False,
      noLossRelayVerified=False,userVisible=False,autoExecute=False,hostWriteIntercepted=False)
check_reply=check_message

def relay_message(source_files,source_roles,draft_file=None,check_receipts=False):
    if not source_files or len(source_files)!=len(source_roles): raise ValueError('relay-requires-one-role-for-each-source-file')
    sources=[]; blocks=[]; receipts=[]; originals={}
    for filename,role in zip(source_files,source_roles):
        if not isinstance(role,str) or not role.strip() or any(c in role for c in '\r\n<>`*_[]()#!&~\\'):
            raise ValueError('relay-source-role-must-be-a-plain-single-line')
        if filename not in originals: originals[filename]=_read(filename)
        path,raw=originals[filename]
        if check_receipts: receipts.append(_receipt_record(path,raw))
        body=raw.decode('utf-8-sig',errors='strict').replace('\r\n','\n')
        if not visible_text_present(body): raise ValueError('relay-source-visible-body-missing:'+str(path))
        sources.append(dict(sourceRole=role,sourceRef=str(path),sha256=hashlib.sha256(raw).hexdigest()))
        literal=re.sub(r'([\\`*_\[\]<>#~!&])',r'\\\1',body.rstrip('\n'))
        blocks.append('转发来源：'+role+'\n\n'+literal)
    message='\n\n'.join(blocks)+'\n'
    # Generated bytes include escaping expansion; LF may become CRLF plus BOM.
    draft_limit=max(MAX_RECORD,len(message.encode('utf-8'))+message.count('\n')+3)
    draft=(_read(draft_file,draft_limit)[1].decode('utf-8-sig',errors='strict').replace('\r\n','\n') if draft_file is not None else None)
    passed=draft is None or draft.rstrip('\n')==message.rstrip('\n')
    result = dict(passed=passed,reason=None if passed else 'relay-draft-does-not-preserve-complete-sources',
      scope='selected-complete-source-messages-only',sources=sources,messageText=message,
      draftChecked=draft is not None,draftLimitBytes=draft_limit,sourceAuthenticated=False,
      sourceSetCompletenessVerified=False,semanticContentVerified=False,userVisible=False,
      hostWriteIntercepted=False,autoExecute=False,wrote=False)
    if check_receipts:
        result['receiptCheck'] = dict(passed=True,scope='declared-receipt-presence-only',
          receiptFiles=receipts,receiptCoverageVerified=False,receiptAuthenticated=False,
          semanticContentVerified=False,reuseScope='Only these selected raw sources and hashes; not another source set or later edited originals.')
    if not passed:
        expected, actual = message.rstrip('\n'), draft.rstrip('\n')
        offset = next((i for i,(a,b) in enumerate(zip(expected,actual)) if a!=b), min(len(expected),len(actual)))
        lo, hi = max(0,offset-80), offset+160
        result['difference'] = dict(firstDifferentCharacter=offset,
          expectedLine=expected.count('\n',0,offset)+1,actualLine=actual.count('\n',0,offset)+1,
          expectedContext=expected[lo:hi],actualContext=actual[lo:hi],
          contextStartCharacter=lo,contextTruncated=lo>0 or hi<len(expected) or hi<len(actual))
    return result

ROLE_MARKERS=('🟦','🔶','🟪')
PLAIN_ROLE_PATTERN=re.compile(r'(?im)^\s*["\']?(?:role|角色)["\']?\s*[:：]\s*["\']?(?:progress|architecture|target|F|A|T)\b')
GAIN_PATTERN=re.compile(r'本波推进增益\s*[:：]\s*[+-]?\d+')
EVENT_PATTERN=re.compile(r'主事件\s*[:：]')

def role_blocks(text):
    """Count declared role blocks in a draft by marker, gain or event line."""
    root='\n'.join(line for line,_ in _display_lines(text) if line is not None)
    structured=0;data_record=False
    try:
        value=json.loads(text)
        if isinstance(value,(dict,list)):
            data_record=True
            records=value if isinstance(value,list) else value.get('opinions',[value])
            if isinstance(records,list):structured=sum(isinstance(x,dict) and x.get('role') in REVIEW_ROLES for x in records)
    except (ValueError,RecursionError):pass
    marked=structured if data_record else sum(root.count(m) for m in ROLE_MARKERS)+len(PLAIN_ROLE_PATTERN.findall(root))
    return dict(markedBlocks=marked,gainBlocks=len(GAIN_PATTERN.findall(root)),
                eventBlocks=len(EVENT_PATTERN.findall(root)))

def _receipt_record(path,raw):
    """Same raw-format check for standalone and literal-relay consumers."""
    body=raw.decode('utf-8-sig',errors='strict')
    if path.suffix.lower()=='.json':
        def reject_constant(value):
            raise ValueError('receipt-invalid-json-constant:'+value)
        try:
            record=json.loads(body,parse_constant=reject_constant)
        except (ValueError,RecursionError) as exc:
            raise ValueError('receipt-invalid-json:'+str(path)) from exc
        empty=record is None or (isinstance(record,(str,list,dict)) and not record)
        if isinstance(record,str) and not record.strip(): empty=True
    else:
        empty=not body.strip()
    if empty: raise ValueError('receipt-content-missing:'+str(path))
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest())

def check_roles(draft_text,receipt_files):
    """Require at least one readable declared receipt for a role-marked draft.

    This is file presence only, not per-role coverage, source authentication
    or proof that the text was sent. A single original may contain many sources.
    Receipt data is not rendered as Markdown; message checks remain separate.
    """
    counts=role_blocks(draft_text)
    blocks=max(counts['markedBlocks'],counts['gainBlocks'],counts['eventBlocks'])
    if blocks==0:
        return dict(passed=True,reason=None,blocks=0,receipts=0,
                    verdict='no-role-blocks',scope='declared-receipt-presence-only',
                    receiptCoverageVerified=False,
                    receiptAuthenticated=False,semanticContentVerified=False,
                    userVisible=False,autoExecute=False)
    receipts=[]
    for filename in receipt_files:
        path,raw=_read(filename)
        receipts.append(_receipt_record(path,raw))
    if not receipts:
        return dict(passed=False,reason='role-block-without-receipt',blocks=blocks,receipts=0,
                    verdict='receipt-required',counts=counts,
                    action='supply or verify the real returned originals; withhold unverified role relays',
                    scope='declared-receipt-presence-only',receiptCoverageVerified=False,
                    receiptAuthenticated=False,semanticContentVerified=False,
                    userVisible=False,autoExecute=False)
    return dict(passed=True,reason=None,blocks=blocks,receipts=len(receipts),receiptFiles=receipts,
                verdict='declared-receipts-present',counts=counts,
                scope='declared-receipt-presence-only',receiptCoverageVerified=False,
                receiptAuthenticated=False,semanticContentVerified=False,
                userVisible=False,autoExecute=False)

USER_EVENTS={
 'planning-start':'【🧭开始评估方案】','workspace-read':'【🧠 项目理解】',
 'workspace-scope':'【🧭 本段可做／禁做】','workspace-write':'【🗂️ 工作区维护】',
 'workspace-gap':'【⛔ 理解缺口｜P0阻断】','workspace-resume':'【🔄 项目理解接回】',
 'closeout-start':'【⚔️ 超大任务收尾辩论】','closeout-goals':'【🎯 有效原需求核对】',
 'closeout-f-case':'【🛡️ F正方立论】','closeout-a-challenge':'【🔍 A反方质证】',
 'closeout-supply':'【🧰 质量不足｜找资源与替代方案】','closeout-history':'【🧠 工作AI经历回溯】',
 'closeout-f-reply':'【🛡️ F正方答辩｜逐项回应不满】','closeout-repair':'【🛠️ 工作AI查证与整改】',
 'closeout-reject':'【🚨 拒绝收尾｜追查本质偏离】','replan':'【🧭 重新定案】',
 'production-resume':'【🔁 继续制作与复验】','closeout-verdict':'【🏁 收尾裁定】',
 'accepted':'【✅ 原记录声明允许收尾】','stage-delivery':'【📦 阶段交付｜父任务未完成】',
 'repair-needed':'【🔧 暂缓收尾｜修复或补证】','evidence-blocked':'【⛔ 收尾未获核证｜保留障碍】',
 'user-revision':'【🧭 用户修订｜重核范围】','user-paused':'【⏸️ 用户暂停／撤销】',
 'correction':'【错误结论/思路/承诺/实现】','progress':'【📍 进度】','risk-warning':'【⚠️ 风险预警】',
 'element-modeling':'【🧬 元素建模】','element-question':'【🧪 模型质疑】',
 'element-open':'【🪢 模型未闭合】','element-reposition':'【🔀 模型重新定位】',
 'element-declaration':'【📐 元素建模声明】'}
USER_ROLES={'progress':'🟦F 进度／功能','architecture':'🔶A 架构／技术生态／可玩性','target':'🟪T 目标／美术'}
REVIEW_ROLES=frozenset(USER_ROLES)
USER_ROLES.update(worker='工作AI',dialogue='主交流AI')
USER_FEATURES={'basic':'【基础功能】','advanced':'【细节／进阶功能】'}

def _probe_text(value,label):
    if not isinstance(value,str) or not value.strip():raise ValueError(label+' requires nonempty text')

def _probe_list(value,label):
    if not isinstance(value,list) or len(value)>256:raise ValueError(label+' requires bounded list')
    for item in value:_probe_text(item,label)

def _probe_object(value,required,optional,label):
    if not isinstance(value,dict) or required-set(value) or set(value)-required-optional:
        raise ValueError(label+' fields invalid')

def _probe_json(body):
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('duplicate state key: '+key)
            value[key]=item
        return value
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite state')))

def _probe_state(body,marker='jury-state',all_blocks=False):
    if body.lstrip().startswith('{'):return [body] if all_blocks else _probe_json(body)
    blocks=[];fence=None;target=False;content=[];comment=False;quoted=False;html=[]
    for raw_line in body.splitlines(keepends=True):
        line=raw_line.rstrip('\r\n')
        if fence is not None:
            close=re.match(r' {0,3}(`{3,}|~{3,})[ \t]*$',line)
            if close and close[1][0]==fence[0] and len(close[1])>=len(fence):
                if target:blocks.append(''.join(content))
                fence=None;target=False;content=[]
            elif target:content.append(raw_line)
            continue
        was_comment=comment;offset=0;has_comment=comment
        while True:
            token='-->' if comment else '<!--';found=line.find(token,offset)
            if found<0:break
            has_comment=True;comment=not comment;offset=found+len(token)
        if has_comment or was_comment:continue
        if not line.strip():quoted=False;continue
        if re.match(r' {0,3}>',line):quoted=True;continue
        if quoted or line.startswith(('    ','\t')):continue
        tags=list(re.finditer(r'<(/?)([A-Za-z][\w:-]*)(?=[\s/>]|$)[^>]*(?:>|$)',line))
        was_html=bool(html)
        for tag in tags:
            name=tag[2].lower()
            if tag[1] and name in html:del html[len(html)-1-html[::-1].index(name):]
            elif not tag[1] and not tag[0].endswith('/>') and name not in {'br','hr','img','input','meta','link','source','wbr','area','base','embed','param','track','col'}:html.append(name)
        if was_html or html or tags:continue
        opening=re.match(r' {0,3}(`{3,}|~{3,})(.*)$',line)
        if opening:
            fence=opening[1];target=opening[2].strip()==marker
    if fence is not None and target:raise ValueError('unterminated current state block')
    if all_blocks:return blocks
    if len(blocks)>1:raise ValueError('multiple state blocks; use the actual current record')
    return _probe_json(blocks[0]) if blocks else None

def _validate_probe(state):
    _probe_object(state,{'schemaVersion'},{'progress','risks','opinions','events','requiredRoles','features','scope','elementModel','taskId','waveId','participants','responsibilityRoles','propositions','adoptions','considerations'},'state')
    if type(state['schemaVersion']) is not int or state['schemaVersion']!=1:raise ValueError('state schemaVersion unsupported')
    if 'scope' in state:_probe_text(state['scope'],'state.scope')
    if not set(state)&{'progress','risks','opinions','events','features','elementModel','propositions','adoptions','considerations'}:raise ValueError('state has no facts')
    if 'features' in state:
        _probe_object(state['features'],{'basic','advanced'},set(),'features')
        for key in state['features']:_probe_list(state['features'][key],'features.'+key)
    if 'events' in state:
        _probe_list(state['events'],'events')
        if any(x not in USER_EVENTS for x in state['events']):raise ValueError('record event unsupported')
    if 'requiredRoles' in state:
        roles=state['requiredRoles'];_probe_list(roles,'requiredRoles')
        if len(set(roles))!=len(roles) or any(x not in REVIEW_ROLES for x in roles):raise ValueError('requiredRoles contains feedback-only or invalid role')
    if 'progress' in state:
        p=state['progress'];_probe_object(p,{'done','active','todo','next','blocked'},set(),'progress')
        for key in ('done','active','todo','blocked'):_probe_list(p[key],'progress.'+key)
        _probe_object(p['next'],{'owner','result'},set(),'progress.next')
        for key in p['next']:_probe_text(p['next'][key],'progress.next.'+key)
    risks=state.get('risks',[])
    if not isinstance(risks,list) or len(risks)>256:raise ValueError('risks requires bounded list')
    for risk in risks:
        _probe_object(risk,{'id','source','status','impact','limitedActions','next','resume','urgent'},{'appliesTo','closureOwner','recovery'},'risk')
        for key in ('id','source','impact','resume'):_probe_text(risk[key],'risk.'+key)
        if risk['status'] not in ('proven','unknown','closed') or type(risk['urgent']) is not bool:raise ValueError('risk status/urgent invalid')
        if risk.get('appliesTo','current') not in ('current','parent','other'):raise ValueError('risk appliesTo invalid')
        _probe_list(risk['limitedActions'],'risk.limitedActions')
        _probe_object(risk['next'],{'owner','action'},set(),'risk.next')
        for key in risk['next']:_probe_text(risk['next'][key],'risk.next.'+key)
    if 'elementModel' in state:
        model=state['elementModel']
        _probe_object(model,{'sourceRef','scope','declaration'},
          {'questions','reposition','openRisks'},'elementModel')
        for key in ('sourceRef','scope','declaration'):_probe_text(model[key],'elementModel.'+key)
        for key in ('questions','reposition','openRisks'):
            if key in model:_probe_list(model[key],'elementModel.'+key)
        refs=model.get('openRisks',[])
        if len(refs)!=len(set(refs)):raise ValueError('elementModel.openRisks duplicate reference')
        if any(sum(risk['id']==ref for risk in risks)!=1 for ref in refs):
            raise ValueError('elementModel.openRisks needs unambiguous declared risk')
    opinions=state.get('opinions',[])
    if not isinstance(opinions,list) or len(opinions)>256:raise ValueError('opinions requires bounded list')
    for opinion in opinions:
        _probe_object(opinion,{'role','state','scope','event','judgment','basis'},
          {'gain','sourceRef','object','wave','open','conditions','losses','limits','closureOwner','next','scoreStatus','details','decision','id','taskId','waveId','actor','sourceSelection','response','responseSelection','responses','reviews'},'opinion')
        if opinion['role'] not in USER_ROLES:raise ValueError('opinion role unsupported')
        for key in ('state','scope','event','judgment'):_probe_text(opinion[key],'opinion.'+key)
        _probe_object(opinion['basis'],{'userNeed','actualUse'},set(),'opinion.basis')
        for key,value in opinion['basis'].items():
            if isinstance(value,dict):
                _probe_object(value,{'source','evidence','disposition','action'},set(),'opinion.basis.'+key)
                for field in value:_probe_text(value[field],'opinion.basis.'+key+'.'+field)
            else:_probe_text(value,'opinion.basis.'+key)
        for key in ('open','conditions','losses','limits'):
            if key in opinion:_probe_list(opinion[key],'opinion.'+key)
        for key in ('sourceRef','object','wave','closureOwner','next','details'):
            if key in opinion:_probe_text(opinion[key],'opinion.'+key)
        gain=opinion.get('gain')
        valid=type(gain) is int and -100<=gain<=100
        if opinion.get('scoreStatus') not in (None,'verified','unverifiable'):raise ValueError('scoreStatus invalid')
        if opinion.get('decision') not in (None,'allow','deny','pending'):raise ValueError('opinion decision invalid')
        if valid and opinion.get('scoreStatus')=='unverifiable' and gain>=0:raise ValueError('unverifiable score must be negative')
        responses=opinion.get('responses',[])
        if not isinstance(responses,list) or len(responses)>256:raise ValueError('responses requires bounded list')
        if responses and opinion['role']!='dialogue':raise ValueError('only actual dialogue feedback may supply dialogue dispositions')
        targets=[]
        for response in responses:
            _probe_object(response,{'to','blockSha256','source','evidence','disposition','action'},set(),'dialogue response')
            _probe_text(response['to'],'response target')
            if not isinstance(response['blockSha256'],str) or not re.fullmatch('[0-9a-f]{64}',response['blockSha256']):raise ValueError('dialogue response needs the actual target source-block fingerprint')
            _ground({k:v for k,v in response.items() if k not in ('to','blockSha256')},'dialogue response basis');targets.append(response['to'])
        if len(set(targets))!=len(targets):raise ValueError('duplicate dialogue response for one source')
    _validate_controls(state)

def _ground(value,label):
    _probe_object(value,{'source','evidence','disposition','action'},set(),label)
    for key in value:_probe_text(value[key],label+'.'+key)

def _identity(state,task,wave):
    if not task or not wave:raise ValueError('current consumer needs expected taskId and waveId')
    if state is None or state.get('taskId')!=task or state.get('waveId')!=wave:
        raise ValueError('task-wave-mismatch or missing current identity; read the real current task, not the latest filename/hash')

def _validate_controls(state):
    for key in ('taskId','waveId'):
        if key in state:_probe_text(state[key],key)
    participants=state.get('participants',[]);_probe_list(participants,'participants')
    if len(set(participants))!=len(participants) or any(x not in USER_ROLES for x in participants):raise ValueError('participants invalid')
    bindings=state.get('responsibilityRoles',{})
    if not isinstance(bindings,dict) or len(bindings)>256:raise ValueError('responsibilityRoles needs bounded actual role bindings, not extra review votes')
    for actor,role in bindings.items():
        _probe_text(actor,'responsibility actor')
        if not isinstance(role,str) or role not in USER_ROLES:raise ValueError('responsibility role unsupported')
    for opinion in state.get('opinions',[]):
        actor=opinion.get('actor')
        if actor is not None:
            _probe_text(actor,'opinion actor')
            if actor in bindings and bindings[actor]!=opinion['role']:raise ValueError('responsibility binding conflicts with selected actual role')
    props=state.get('propositions',[])
    if not isinstance(props,list) or len(props)>256:raise ValueError('propositions invalid')
    ids=set()
    for item in props:
        _probe_object(item,{'id','claim','status','evidenceRefs','conditions','affectedActions','owner','nextAction'},set(),'proposition')
        for key in ('id','claim','conditions','owner','nextAction'):_probe_text(item[key],'proposition.'+key)
        if item['id'] in ids:raise ValueError('duplicate proposition')
        ids.add(item['id'])
        if item['status'] not in ('observed','supported','unknown','refuted'):raise ValueError('proposition status invalid')
        _probe_list(item['evidenceRefs'],'proposition evidence');_probe_list(item['affectedActions'],'proposition actions')
        if item['status'] in ('observed','supported') and not item['evidenceRefs']:raise ValueError('supported proposition lacks evidence location')
    for key in ('adoptions','considerations'):
        if not isinstance(state.get(key,[]),list) or len(state.get(key,[]))>256:raise ValueError(key+' requires bounded list')
    for adoption in state.get('adoptions',[]):
        _probe_object(adoption,{'action','owner','propositionIds','state'},set(),'adoption')
        for key in ('action','owner'):_probe_text(adoption[key],'adoption.'+key)
        _probe_list(adoption['propositionIds'],'adoption propositions')
        if adoption['state'] not in ('proposed','held','allowed'):raise ValueError('adoption state invalid')
        if not adoption['propositionIds'] or set(adoption['propositionIds'])-ids:raise ValueError('adoption needs declared proposition support')
        if adoption['state']=='allowed' and any(x['status'] not in ('observed','supported') for x in props if x['id'] in adoption['propositionIds']):
            raise ValueError('adoption conflicts with unknown/refuted proposition; restrict the dependent action')
    for item in state.get('considerations',[]):
        _probe_object(item,{'id','name','kind','sourceRef','owner','request','state','nextAction'},{'response','limitedActions','appliesTo'},'consideration')
        for key in ('id','name','sourceRef','owner','request','nextAction'):_probe_text(item[key],'consideration.'+key)
        if item['kind'] not in ('consideration','request') or item['state'] not in ('open','answered','adopted','declined'):raise ValueError('consideration state invalid')
        _probe_list(item.get('limitedActions',[]),'consideration limited actions')
        if item.get('appliesTo','current') not in ('current','parent','other'):raise ValueError('consideration scope invalid')
        if item['state']!='open':
            _ground(item.get('response'),'consideration same-name response')
    for risk in state.get('risks',[]):
        recovery=risk.get('recovery')
        if recovery is None:continue
        recovery_fields={'state','proposition','question','affectedAction','evidenceOwner','evidenceAction','reviewOwner','challengeRef','evidenceRef','reviewRef','decision'}
        _probe_object(recovery,recovery_fields,{'history','requestSource','changeReason'},'recovery')
        history=recovery.get('history',[])
        if not isinstance(history,list) or len(history)>256:raise ValueError('recovery history requires a bounded list')
        for prior in history:
            _probe_object(prior,recovery_fields,{'requestSource','changeReason'},'prior recovery decision')
            for key in recovery_fields:_probe_text(prior[key],'prior recovery.'+key)
            if prior['state']!='resolved' or prior['decision'] not in ('retain','revise','withdraw'):
                raise ValueError('prior recovery history must preserve an actual resolved decision')
        for attempt in [*history,recovery]:
            if 'changeReason' in attempt:
                _probe_text(attempt['changeReason'],'later change reason')
                if 'requestSource' not in attempt:raise ValueError('later change reason needs its actual request source version')
            if 'requestSource' in attempt:
                _probe_object(attempt['requestSource'],{'path','sha256'},set(),'request source version')
                _probe_text(attempt['requestSource']['path'],'request original path')
                if not isinstance(attempt['requestSource']['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',attempt['requestSource']['sha256']):raise ValueError('request source needs an actual byte fingerprint')
        for key in ('proposition','question','affectedAction','evidenceOwner','evidenceAction','reviewOwner','challengeRef'):_probe_text(recovery[key],'recovery.'+key)
        if recovery['state'] not in ('evidence-needed','review-needed','resolved'):raise ValueError('recovery state invalid')
        if recovery['reviewOwner']!=risk.get('closureOwner'):raise ValueError('recovery must return to original responsibility or a recorded lawful successor')
        if recovery['state']=='resolved':
            for key in ('evidenceRef','reviewRef','decision'):_probe_text(recovery[key],'recovery.'+key)
            if recovery['decision'] not in ('retain','revise','withdraw'):raise ValueError('recovery requires an explicit review decision category')
            if recovery['decision']=='withdraw':
                if risk['status']!='closed' or risk['limitedActions']:raise ValueError('withdraw must close only this risk and release its limited actions')
            elif risk['status']=='closed' or not risk['limitedActions']:
                raise ValueError('retained/revised veto cannot be closed or lose its dependent action restriction')
        elif risk['status']=='closed':raise ValueError('risk closed before evidence and original review returned')
    restricted={x['action'] for x in _restricted_actions(state)}
    if any(x['state']=='allowed' and x['action'] in restricted for x in state.get('adoptions',[])):
        raise ValueError('allowed adoption conflicts with another declared current restriction or unresolved premise')

def _restricted_actions(state):
    held=[]
    for risk in state.get('risks',[]):
        if risk['status']!='closed' and risk.get('appliesTo','current')=='current':
            held.extend(dict(action=x,kind='risk',id=risk['id'],source=risk['source']) for x in risk['limitedActions'])
    for prop in state.get('propositions',[]):
        if prop['status'] in ('unknown','refuted'):
            held.extend(dict(action=x,kind='proposition',id=prop['id'],source='; '.join(prop['evidenceRefs']) or 'unverified declared premise') for x in prop['affectedActions'])
    for item in state.get('considerations',[]):
        if item['state']=='open' and item.get('appliesTo','current')=='current':
            held.extend(dict(action=x,kind='consideration',id=item['id'],source=item['sourceRef']) for x in item.get('limitedActions',[]))
    return held

def select_opinion(filename,opinion_id,task,wave,historical=False):
    """Select one actual source block; append-only history does not invalidate it."""
    path,raw=_read(filename);matches=[]
    text=raw.decode('utf-8-sig');all_opinions=[]
    for body in _probe_state(text,marker='jury-opinion',all_blocks=True):
        value=_probe_json(body)
        all_opinions.append(value)
        if value.get('id')==opinion_id:matches.append((value,body))
    if len(matches)!=1:raise ValueError('current opinion selection must match exactly one named block')
    opinion,body=matches[0];_identity(opinion,task,wave)
    for key in ('id','actor','role','state','scope','event','judgment'):_probe_text(opinion.get(key),'opinion.'+key)
    if opinion['role'] not in USER_ROLES:raise ValueError('unsupported feedback role')
    if not historical:
        ids={x.get('id') for x in all_opinions if x.get('taskId')==task and x.get('waveId')==wave and x.get('role')==opinion['role'] and x.get('actor')==opinion['actor']}
        heads=set();superseded=set();declared=False
        for current_body in _probe_state(text,marker='jury-current',all_blocks=True):
            current=_probe_json(current_body)
            if 'currentOpinionId' not in current:continue
            if any(current.get(k)!=opinion.get(k) for k in ('taskId','waveId','role','actor')):continue
            _probe_object(current,{'taskId','waveId','role','actor','currentOpinionId','supersedes'},set(),'current opinion declaration')
            _probe_list(current['supersedes'],'explicit superseded opinions')
            if current['currentOpinionId'] not in ids or set(current['supersedes'])-ids or current['currentOpinionId'] in current['supersedes']:raise ValueError('current declaration must bind actual same-owner opinion history')
            heads.add(current['currentOpinionId']);superseded.update(current['supersedes']);declared=True
        if declared:
            active=heads-superseded
            if len(active)!=1 or opinion_id not in active or ids-active-superseded:
                raise ValueError('selected opinion is superseded or current revision is unresolved; no timestamp/latest-hash guessing')
        elif len(ids)>1:raise ValueError('multiple same-owner opinions need an explicit jury-current revision declaration; history remains readable')
    _probe_object(opinion.get('basis'),{'userNeed','actualUse'},set(),'opinion.basis')
    for key in ('userNeed','actualUse'):_ground(opinion['basis'][key],'opinion.basis.'+key)
    selected=dict(opinion,sourceRef=str(path),sourceSelection={'path':str(path),'id':opinion_id,'blockSha256':hashlib.sha256(body.encode('utf-8')).hexdigest()})
    _validate_probe({'schemaVersion':1,'opinions':[selected]})
    return selected

def _current_feedback(state,task,wave):
    _identity(state,task,wave)
    roles=[]
    for opinion in state.get('opinions',[]):
        _identity(opinion,task,wave)
        for key in ('userNeed','actualUse'):_ground(opinion['basis'][key],'current basis.'+key)
        if 'response' in opinion:
            _ground(opinion['response'],'dialogue response to source')
            binding=opinion.get('responseSelection')
            if not binding:raise ValueError('caller response lacks real dialogue-source binding')
            reply=select_opinion(binding['path'],binding['id'],task,wave)
            actual=[x for x in reply.get('responses',[]) if x['to']==opinion['id']]
            selected_dialogue=[x for x in state.get('opinions',[]) if x['role']=='dialogue']
            if reply['role']!='dialogue' or reply['sourceSelection']!=binding or len(actual)!=1 or actual[0]['blockSha256']!=opinion['sourceSelection']['blockSha256'] or {k:v for k,v in actual[0].items() if k not in ('to','blockSha256')}!=opinion['response'] or not selected_dialogue or selected_dialogue[0]['sourceSelection']!=binding:
                raise ValueError('dialogue disposition differs from the actual current response source')
        selection=opinion.get('sourceSelection')
        if not selection:raise ValueError('current feedback needs an actual named original selection, not a copied pointer')
        current=select_opinion(selection['path'],selection['id'],task,wave)
        if {key:value for key,value in opinion.items() if key not in ('response','responseSelection')}!=current:
            raise ValueError('selected opinion changed or was rewritten by caller')
        roles.append(opinion['role'])
    if len(set(roles))!=len(roles):raise ValueError('multiple current opinions for one participant; select the actual current result')
    if not state.get('participants'):raise ValueError('current participants must be declared from the actual task')
    missing=set(state['participants'])-set(roles)
    if missing:raise ValueError('current participant feedback missing: '+', '.join(sorted(missing)))

def review_transition(state,change,task,wave):
    """Pure declared-state transition. Host must verify the real sender/receipt."""
    _identity(state,task,wave);_validate_probe(state)
    result=json.loads(json.dumps(state));risk=next((x for x in result.get('risks',[]) if x['id']==change.get('riskId')),None)
    if risk is None:raise ValueError('unknown disputed risk')
    action=change.get('action');actor=change.get('actor');_probe_text(actor,'actual evidence/review actor')
    restored=[]
    if action in ('challenge','recheck'):
        if risk['status']=='closed':raise ValueError('closed result needs a new sourced risk, not replay of an old transition')
        for key in ('proposition','question','affectedAction','evidenceOwner','evidenceAction','sourceRef'):_probe_text(change.get(key),'challenge.'+key)
        prior=risk.get('recovery');history=[];request_source=None
        if action=='challenge' and prior:raise ValueError('dispute already exists; use a sourced recheck after a resolved decision, not replay')
        if action=='recheck':
            if not prior or prior['state']!='resolved':raise ValueError('recheck requires an unresolved risk with a completed original review; pending work is not replayed')
            _probe_text(change.get('changeReason'),'actual later change reason, not merely a new filename')
            used=[*prior.get('history',[]),prior]
            if change['sourceRef'] in {x[key] for x in used for key in ('challengeRef','evidenceRef','reviewRef')} and not any(x.get('requestSource') and x['challengeRef']==change['sourceRef'] for x in used):
                raise ValueError('recheck cannot replay a processed source without a preserved prior byte snapshot')
            request_path,request_raw=_read(change['sourceRef'])
            request_source=dict(path=str(request_path),sha256=hashlib.sha256(request_raw).hexdigest())
            if any(x.get('requestSource',{}).get('sha256')==request_source['sha256'] for x in used):
                raise ValueError('recheck cannot replay already processed request bytes under the same or another path')
            known=[x['requestSource'] for x in used if x.get('requestSource',{}).get('path')==request_source['path']]
            if request_source in known or not known and change['sourceRef'] in {x[key] for x in used for key in ('challengeRef','evidenceRef','reviewRef')}:
                raise ValueError('recheck cannot replay a processed source; same-path new versions need a preserved prior byte snapshot')
            history=[*prior.get('history',[]),{k:v for k,v in prior.items() if k!='history'}]
        elif Path(change['sourceRef']).is_file():
            request_path,request_raw=_read(change['sourceRef'])
            request_source=dict(path=str(request_path),sha256=hashlib.sha256(request_raw).hexdigest())
        _probe_text(risk.get('closureOwner'),'original closure responsibility')
        if change['affectedAction'] not in risk['limitedActions']:raise ValueError('challenge must name an actually limited dependent action')
        risk['recovery']=dict(state='evidence-needed',proposition=change['proposition'],question=change['question'],affectedAction=change['affectedAction'],
          evidenceOwner=change['evidenceOwner'],evidenceAction=change['evidenceAction'],reviewOwner=risk['closureOwner'],challengeRef=change['sourceRef'],evidenceRef='',reviewRef='',decision='')
        if history:risk['recovery']['history']=history
        if request_source:risk['recovery']['requestSource']=request_source
        if action=='recheck':risk['recovery']['changeReason']=change['changeReason']
        risk['next']={'owner':change['evidenceOwner'],'action':change['evidenceAction']}
    elif action=='evidence':
        recovery=risk.get('recovery',{})
        if recovery.get('state')!='evidence-needed' or actor!=recovery.get('evidenceOwner'):raise ValueError('evidence must return from the assigned work owner at the pending step')
        _read(change['sourceRef']);recovery.update(state='review-needed',evidenceRef=change['sourceRef'])
        risk['next']={'owner':recovery['reviewOwner'],'action':'按同一命题/区分证据给维持、修订或撤回的本人裁定；不由作者代关'}
    elif action=='review':
        recovery=risk.get('recovery',{})
        if recovery.get('state')!='review-needed':raise ValueError('review needs the actual evidence result first')
        opinion=select_opinion(change['sourceRef'],change['opinionId'],task,wave)
        if opinion['role'] not in REVIEW_ROLES or opinion['actor']!=actor or actor!=recovery['reviewOwner']:
            raise ValueError('only original review responsibility or recorded lawful same-role successor may close; feedback author/root is not a review vote')
        reviews=[x for x in opinion.get('reviews',[]) if x.get('riskId')==risk['id']]
        if len(reviews)!=1:raise ValueError('actual review opinion needs one decision for this precise risk')
        decision=reviews[0]
        if decision.get('evidenceRef')!=recovery['evidenceRef'] or decision.get('decision') not in ('retain','revise','withdraw'):
            raise ValueError('review must bind this evidence and an explicit supported disposition')
        _probe_text(decision.get('reason'),'review reason')
        recovery.update(state='resolved',decision=decision['decision'],reviewRef=change['sourceRef']+'#'+change['opinionId'])
        if decision['decision']=='withdraw':
            restored=list(risk['limitedActions']);risk.update(status='closed',limitedActions=[])
            risk['next']={'owner':decision.get('nextOwner',recovery['evidenceOwner']),'action':decision.get('nextAction','仅恢复本命题原受限动作，保其它真否决/未知')}
        elif decision['decision']=='revise':
            _probe_list(decision.get('limitedActions'),'revised limited actions')
            restored=[x for x in risk['limitedActions'] if x not in decision['limitedActions']]
            risk['limitedActions']=decision['limitedActions']
            risk['next']={'owner':decision.get('nextOwner',recovery['evidenceOwner']),'action':decision.get('nextAction',decision['reason'])}
        else:risk['next']={'owner':decision.get('nextOwner',recovery['evidenceOwner']),'action':decision.get('nextAction',decision['reason'])}
    else:raise ValueError('unknown review transition')
    _validate_probe(result)
    held=_restricted_actions(result);still={x['action'] for x in held}
    return dict(passed=True,facts=result,releasedActions=restored,restoredActions=[x for x in restored if x not in still],
      stillHeld=[x for x in held if x['action'] in restored],sourceAuthenticated=False,semanticContentVerified=False,autoExecute=False,wrote=False)

def _user_plain(value):
    # Preserve literal source text while preventing injected headings/markup.
    return re.sub(r'([\\`*_\[\]<>#~!&])',r'\\\1',str(value))

def _user_basis(value):
    if isinstance(value,dict):
        return '['+_user_plain(value['source'])+'] 依据：'+_user_plain(value['evidence'])+'；处置：'+_user_plain(value['disposition'])+'；落实：'+_user_plain(value['action'])
    return '[原记录依据：'+_user_plain(value)+']'

def _record_scope(state):
    if state.get('scope'):return state['scope']
    scopes={x['scope'] for x in state.get('opinions',[]) if x['role'] in state.get('requiredRoles',[])}
    if len(scopes)!=1:raise ValueError('accepted event needs one explicit current record scope')
    return next(iter(scopes))

def _model_open_risks(state):
    refs=state.get('elementModel',{}).get('openRisks',[])
    return [risk for risk in state.get('risks',[]) if risk['id'] in refs and risk['status']!='closed']


def _model_event_supported(state,event):
    if event not in ('element-modeling','element-question','element-open','element-reposition','element-declaration'):
        return True
    model=state.get('elementModel')
    if model is None:return False
    if event=='element-question':return bool(model.get('questions'))
    if event=='element-reposition':return bool(model.get('reposition'))
    if event=='element-open':return bool(_model_open_risks(state))
    return True


def _render_probe(state,events):
    lines=[USER_EVENTS[event]+('（当前记录范围：'+_user_plain(_record_scope(state))+'）' if event=='accepted' else '')
           for event in events if state is None or event not in
           ('progress','risk-warning','element-question','element-open','element-reposition','element-declaration')]
    if state is None:return '\n\n'.join(lines+['记录未解析；请读取原件，进度和风险尚未核实。'])+'\n'
    # Resolve only responsibility fields from actual role metadata. Business
    # paths, identifiers, quotes and substantive text are never globally scrubbed.
    owners={role:label for role,label in USER_ROLES.items()}
    owners['root']=USER_ROLES['dialogue']
    owners.update({actor:USER_ROLES[role] for actor,role in state.get('responsibilityRoles',{}).items()})
    owners.update({op['actor']:USER_ROLES[op['role']] for op in state.get('opinions',[]) if op.get('actor')})
    def responsibility(value):
        if value not in owners and (value=='/root' or value.startswith('/root/')):
            raise ValueError('native responsibility lacks a real role binding for user display; reuse actual host responsibility or give a meaningful owner, do not add a review vote')
        return _user_plain(owners.get(value,value))
    def reference(value):
        for opinion in state.get('opinions',[]):
            container=opinion.get('sourceRef')
            if container and value in (container,container+'#'+opinion.get('id','')):
                return USER_ROLES[opinion['role']]+'原始意见'
        return value
    def basis(value):
        return _user_basis(dict(value,source=reference(value['source'])) if isinstance(value,dict) else value)
    model=state.get('elementModel')
    if model is not None:
        lines.extend([USER_EVENTS['element-declaration'],
          '模型原件／当版定位：'+_user_plain(model['sourceRef']),
          '模型范围：'+_user_plain(model['scope']),_user_plain(model['declaration'])])
        for key,event in (('questions','element-question'),('reposition','element-reposition')):
            if model.get(key):lines.extend([USER_EVENTS[event],*(_user_plain(x) for x in model[key])])
        open_risks=_model_open_risks(state)
        if open_risks:lines.extend([USER_EVENTS['element-open'],
          '关联原风险：'+'；'.join(_user_plain(x['id']) for x in open_risks)])
    if 'features' in state:
        for key,title in USER_FEATURES.items():
            lines.append(title+'\n'+('\n'.join(_user_plain(x) for x in state['features'][key]) or '原记录本次无此类项。'))
    p=state.get('progress')
    if p:
        lines.append(USER_EVENTS['progress'])
        for key,label in (('done','已做'),('active','在做'),('todo','待做'),('blocked','阻断')):
            lines.append(label+'：'+('；'.join(_user_plain(x) for x in p[key]) if p[key] else '当前记录无此项'))
        lines.append('下一结果：'+responsibility(p['next']['owner'])+' — '+_user_plain(p['next']['result']))
    if 'risks' not in state:lines.append('风险：原记录未提供，尚待核实。')
    for risk in state.get('risks',[]):
        if risk['status']=='closed' and not risk.get('recovery'):continue
        lines.extend([USER_EVENTS['risk-warning']+' '+_user_plain(risk['id']),
          '状态：'+risk['status']+'；来源：'+_user_plain(reference(risk['source'])),
          '适用范围：'+risk.get('appliesTo','current')+('（父/其他范围不随本次当前许可关闭）' if risk.get('appliesTo','current')!='current' else '（本记录当前范围）'),
          '影响：'+_user_plain(risk['impact']), '受限动作：'+'；'.join(_user_plain(x) for x in risk['limitedActions']),
          '下一处理：'+responsibility(risk['next']['owner'])+' — '+_user_plain(risk['next']['action']),
          '接回：'+_user_plain(risk['resume'])])
        if risk.get('recovery'):
            r=risk['recovery'];lines.extend(['争议状态：'+r['state']+'；命题：'+_user_plain(r['proposition']),
              '区分观察：'+_user_plain(r['question']), '取证：'+responsibility(r['evidenceOwner'])+' — '+_user_plain(r['evidenceAction']),
              '原责重核：'+responsibility(r['reviewOwner'])+'；证据：'+_user_plain(reference(r['evidenceRef']) if r['evidenceRef'] else '尚未取得'),
              '本人裁定：'+_user_plain(r['decision'] or '尚未回件')])
            if r.get('changeReason'):
                lines.append('后到再核变化：'+_user_plain(r['changeReason']))
            if r.get('history'):
                previous=r['history'][-1];lines.append('保留既往重核 '+str(len(r['history']))+' 项；上一裁定：'+previous['decision'])
    for prop in state.get('propositions',[]):
        lines.extend(['命题 '+_user_plain(prop['id'])+'：'+_user_plain(prop['claim'])+'（'+prop['status']+'）',
          '依据：'+'；'.join(_user_plain(reference(x)) for x in prop['evidenceRefs'])+'；条件：'+_user_plain(prop['conditions']),
          '受影响动作：'+'；'.join(_user_plain(x) for x in prop['affectedActions'])+'；后继：'+responsibility(prop['owner'])+' — '+_user_plain(prop['nextAction'])])
    for adoption in state.get('adoptions',[]):
        lines.append('动作采用声明：'+_user_plain(adoption['action'])+'（'+adoption['state']+'；依据命题 '+', '.join(adoption['propositionIds'])+'；承担 '+responsibility(adoption['owner'])+'）')
    for opinion in state.get('opinions',[]):
        gain=opinion.get('gain');valid=type(gain) is int and -100<=gain<=100
        score=gain if valid else -1
        lines.extend(['**'+USER_ROLES[opinion['role']]+'／'+_user_plain(opinion['state'])+' '+
          '【📈 本波推进增益：'+str(score)+'】**（'+_user_plain(opinion['scope'])+'）',
          '主事件：'+_user_plain(opinion['event']),_user_plain(opinion['judgment'])])
        if not valid:lines.append('原来源未提供合法数值；此分依缺分规则记录，非原角色评价；须向原角色补正。')
        for key,label in (('object','对象／版本'),('wave','波次'),('decision','本责决定'),('scoreStatus','评分核实状态（原声明）'),('open','未闭'),('conditions','条件'),('losses','损失'),('limits','限制'),('closureOwner','关闭责任'),('next','下一动作'),('details','完整意见')):
            if key in opinion:
                if key=='wave' and opinion[key] in (state.get('waveId'),opinion.get('waveId')):continue
                if key=='details' and reference(opinion[key])!=opinion[key]:continue
                value=opinion[key];lines.append(label+'：'+('；'.join(_user_plain(x) for x in value) if isinstance(value,list) else responsibility(value) if key=='closureOwner' else _user_plain(value)))
        lines.extend(['🔎考虑到｜用户需求偏移：'+basis(opinion['basis']['userNeed']),
                      '🔎考虑到｜真实的视觉理解：'+basis(opinion['basis']['actualUse'])])
        if 'response' in opinion:lines.append('主交流对本来源的处置／落实：'+basis(opinion['response']))
    for item in state.get('considerations',[]):
        marker='🧩请考虑' if item['kind']=='request' else '🔎考虑到'
        lines.extend([marker+'｜'+_user_plain(item['name'])+'（'+item['state']+'）',
          '来源：'+_user_plain(reference(item['sourceRef']))+'；实际收件职责：'+responsibility(item['owner']),_user_plain(item['request'])])
        if item.get('response'):lines.append('同名实答｜'+_user_plain(item['name'])+'：'+basis(item['response']))
        else:lines.append('同名实答尚未收到；仅限制：'+'；'.join(_user_plain(x) for x in item.get('limitedActions',[])))
        lines.append('真实下一动作／接回：'+_user_plain(item['nextAction']))
    return '\n\n'.join(lines)+'\n'

def probe_record(filename,audience='internal',event=None,expected_sha256=None,expected_task=None,expected_wave=None,_opinions=None):
    """Read declared task facts. No host action, semantic ruling or record writes."""
    if audience not in ('internal','user'):raise ValueError('audience invalid')
    if event is not None and event not in USER_EVENTS:raise ValueError('unknown declared event')
    path,raw=_read(filename);digest=hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest!=expected_sha256:raise ValueError('record-changed; inspect current original')
    state=_probe_state(raw.decode('utf-8-sig',errors='strict'))
    if _opinions is not None:
        if state is None:raise ValueError('compose needs an actual current record')
        state['opinions']=_opinions
    if state is not None:_validate_probe(state)
    if expected_task is not None or expected_wave is not None:_identity(state,expected_task,expected_wave)
    if audience=='user':
        if state is not None:_attach_dialogue_responses(state.get('opinions',[]))
        _current_feedback(state,expected_task,expected_wave)
    alerts=[{'riskId':x['id'],'source':x['source'],'status':x['status'],'limitedActions':x['limitedActions']}
       for x in (state or {}).get('risks',[]) if x['urgent'] and x['status']!='closed']
    events=[]
    if event is not None:
        supported=state is not None and (event in state.get('events',[]) or
          event=='progress' and 'progress' in state or
          event=='element-declaration' and 'elementModel' in state or
          event=='risk-warning' and any(x['status']!='closed' for x in state.get('risks',[])))
        if not supported or not _model_event_supported(state,event):
            raise ValueError('requested event not supported by current record')
        if event=='accepted':
            if any(x['state']=='open' and x.get('appliesTo','current')=='current' and x.get('limitedActions') for x in state.get('considerations',[])):
                raise ValueError('accepted conflicts with unanswered dependent consideration')
            p=state.get('progress',{})
            if any(p.get(x) for x in ('active','todo','blocked')) or any(x.get('open') or x.get('conditions') for x in state.get('opinions',[])):
                raise ValueError('accepted event conflicts with declared unfinished facts')
            if any(x['status']!='closed' and x.get('appliesTo','current')=='current' and
              (x['urgent'] or x['limitedActions']) for x in state.get('risks',[])):
                raise ValueError('accepted event conflicts with current unresolved risk')
            if any(risk.get('appliesTo','current')=='current' for risk in _model_open_risks(state)):
                raise ValueError('accepted event conflicts with current unresolved element model')
            required=state.get('requiredRoles',[])
            if not required or any(not [x for x in state.get('opinions',[]) if x['role']==role] or
              any(x.get('decision')!='allow' for x in state['opinions'] if x['role']==role) for role in required):
                raise ValueError('accepted event lacks current declared review decisions')
            _record_scope(state)
        events.append(event)
    if alerts and 'risk-warning' not in events:events.append('risk-warning')
    result=dict(passed=True,status='declared-facts-read' if state is not None else 'record-unstructured',
      audience=audience,sourceRef=str(path),sourceSha256=digest,observedAt=datetime.now(timezone.utc).isoformat(),
      facts=state,declaredEvents=events,alerts=alerts,progressParsed=state is not None and 'progress' in state,
      riskStatus='declared' if state is not None and 'risks' in state else 'unknown',
      sourceAuthenticated=False,semanticContentVerified=False,readinessCertified=False,
      noLossRelayVerified=False,userVisible=False,autoExecute=False,wrote=False)
    if audience=='user':result['messageText']=_render_probe(state,events)
    if path.read_bytes()!=raw:raise ValueError('record changed during probe')
    return result

def _attach_dialogue_responses(opinions):
    dialogue=[x for x in opinions if x['role']=='dialogue']
    if len(dialogue)>1:raise ValueError('select one actual current dialogue opinion')
    for reply in dialogue:
        for response in reply.get('responses',[]):
            targets=[x for x in opinions if x['id']==response['to']]
            if not targets:continue  # A genuinely unselected source is not silently made a participant.
            if len(targets)!=1:raise ValueError('dialogue response target is ambiguous')
            target=targets[0]
            if response['blockSha256']!=target['sourceSelection']['blockSha256']:raise ValueError('dialogue response target changed; obtain the real updated disposition before reusing it')
            body={k:v for k,v in response.items() if k not in ('to','blockSha256')}
            if 'response' in target and (target['response']!=body or target.get('responseSelection')!=reply['sourceSelection']):
                raise ValueError('caller response differs from the actual current dialogue source')
            target.update(response=body,responseSelection=reply['sourceSelection'])

def compose_record(filename,selections,task,wave,event=None):
    opinions=[select_opinion(path,identity,task,wave) for path,identity in selections]
    original=_probe_state(_read(filename)[1].decode('utf-8-sig'))
    dialogue=[x for x in opinions if x['role']=='dialogue']
    if len(dialogue)>1:raise ValueError('select one actual current dialogue opinion')
    for opinion in opinions:
        prior=[x for x in (original or {}).get('opinions',[]) if x.get('sourceSelection')==opinion['sourceSelection']]
        if prior and prior[0].get('responseSelection') and dialogue and prior[0]['responseSelection']==dialogue[0]['sourceSelection']:
            opinion.update(response=prior[0]['response'],responseSelection=prior[0]['responseSelection'])
    _attach_dialogue_responses(opinions)
    result=probe_record(filename,'user',event,expected_task=task,expected_wave=wave,_opinions=opinions)
    result.update(status='selected-current-source-projection',compositionWritten=False)
    return result

def check_user_view(filename,draft_file,task,wave,event=None,selections=()):
    projected=compose_record(filename,selections,task,wave,event) if selections else probe_record(filename,'user',event,expected_task=task,expected_wave=wave)
    draft=_read(draft_file)[1].decode('utf-8-sig')
    def root_text(value):return '\n'.join(line for line,_ in _display_lines(value) if line is not None).strip()
    expected,actual=root_text(projected['messageText']),root_text(draft)
    passed=expected in actual
    return dict(passed=passed,reason=None if passed else 'current per-source body/bases/dispositions missing, changed or hidden; metadata is not the user body',
      taskId=task,waveId=wave,sourceSha256=projected['sourceSha256'],draftSha256=hashlib.sha256(draft.encode('utf-8')).hexdigest(),
      scope='selected-current-visible-body-preservation-only',semanticContentVerified=False,sourceAuthenticated=False,userVisible=False,autoExecute=False,wrote=False)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest='command',required=True)
    relay=commands.add_parser('relay-message'); relay.add_argument('--source-file',action='append',required=True)
    relay.add_argument('--source-role',action='append',required=True); relay.add_argument('--draft-file'); relay.add_argument('--check-receipts',action='store_true',help='Reuse the same selected originals for the receipt presence/format check')
    check=commands.add_parser('check-message'); check.add_argument('--message-file',required=True)
    check.add_argument('--role',choices=('jury','worker'),default='jury'); check.add_argument('--contract-version',type=int,default=MESSAGE_CONTRACT_VERSION)
    roles=commands.add_parser('check-roles'); roles.add_argument('--draft-file',required=True)
    roles.add_argument('--receipt-file',action='append',default=[])
    probe=commands.add_parser('probe');probe.add_argument('--record-file',required=True)
    probe.add_argument('--audience',choices=('internal','user'),default='internal')
    probe.add_argument('--event',choices=tuple(USER_EVENTS));probe.add_argument('--expect-sha256')
    probe.add_argument('--expect-task');probe.add_argument('--expect-wave')
    select=commands.add_parser('select-opinion');select.add_argument('--source-file',required=True);select.add_argument('--opinion-id',required=True);select.add_argument('--history',action='store_true')
    compose=commands.add_parser('compose');compose.add_argument('--record-file',required=True);compose.add_argument('--event',choices=tuple(USER_EVENTS))
    view=commands.add_parser('check-user-view');view.add_argument('--record-file',required=True);view.add_argument('--draft-file',required=True);view.add_argument('--event',choices=tuple(USER_EVENTS))
    transition=commands.add_parser('review-step');transition.add_argument('--record-file',required=True);transition.add_argument('--input-file',required=True)
    for command in (select,compose,view,transition):
        command.add_argument('--expect-task',required=True);command.add_argument('--expect-wave',required=True)
    for command in (compose,view):
        command.add_argument('--source-file',action='append',default=[]);command.add_argument('--opinion-id',action='append',default=[])
    args=parser.parse_args(argv)
    try:
        if args.command=='relay-message':
            result=relay_message(args.source_file,args.source_role,args.draft_file,args.check_receipts)
        elif args.command=='check-roles':
            result=check_roles(_read(args.draft_file)[1].decode('utf-8-sig'),args.receipt_file)
        elif args.command=='probe':
            result=probe_record(args.record_file,args.audience,args.event,args.expect_sha256,args.expect_task,args.expect_wave)
        elif args.command=='select-opinion':
            result=dict(passed=True,opinion=select_opinion(args.source_file,args.opinion_id,args.expect_task,args.expect_wave,args.history),historical=args.history,sourceAuthenticated=False,semanticContentVerified=False,autoExecute=False,wrote=False)
        elif args.command in ('compose','check-user-view'):
            if len(args.source_file)!=len(args.opinion_id):raise ValueError('one current opinion id required per actual source')
            selections=list(zip(args.source_file,args.opinion_id))
            result=compose_record(args.record_file,selections,args.expect_task,args.expect_wave,args.event) if args.command=='compose' else check_user_view(args.record_file,args.draft_file,args.expect_task,args.expect_wave,args.event,selections)
        elif args.command=='review-step':
            state=_probe_state(_read(args.record_file)[1].decode('utf-8-sig'))
            change=_probe_json(_read(args.input_file)[1].decode('utf-8-sig'))
            result=review_transition(state,change,args.expect_task,args.expect_wave)
        else:
            result=check_message(_read(args.message_file)[1].decode('utf-8-sig'),args.contract_version)
    except (OSError,UnicodeError,ValueError) as exc:
        result=dict(passed=False,reason=str(exc),autoExecute=False,wrote=False)
        if args.command=='check-roles':
            result.update(scope='declared-receipt-presence-only',receiptCoverageVerified=False,
                          receiptAuthenticated=False,semanticContentVerified=False)
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['passed'] else 2
if __name__=='__main__': raise SystemExit(main())
