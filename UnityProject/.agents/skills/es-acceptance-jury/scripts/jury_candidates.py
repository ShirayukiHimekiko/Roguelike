"""Inspect declared current checks; plans never certify product behavior."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
import jury_read as reader
from jury_session import visible_text_present

ROOT=Path(__file__).resolve().parents[1]
INDEX='scripts/candidate-routing.json'
P0_REFERENCES={'progress':'references/p0-progress.md','architecture':'references/p0-architecture.md'}
P0_CONTRACTS={role:reference+'#review-contract' for role,reference in P0_REFERENCES.items()}
P0_SHARED_CONTRACT='references/p0-review.md#review-contract'
PROJECT_CONTEXT='references/project-understanding.md#project-fit'
PROJECT_DECISIONS=('references/project-understanding.md#stage-fit','references/project-understanding.md#necessity-before-dependency')
P0_ARCHITECTURE_TRACKING=P0_REFERENCES['architecture']+'#project-tracking'
INDEPENDENT_INPUT_CONTRACT='references/coordination.md#independent-input'
SOURCE_MODE_CONTRACTS=('references/coordination.md#no-simulation',)
KNOWLEDGE_GUIDE='references/reading-guide.md#knowledge-use'
KNOWLEDGE_INDEX='knowledge/index.md#issues'
KNOWLEDGE_TRIGGERS=('blockage','high-risk','high-requirement')
WORKSPACE_GUIDE='references/game-workspaces.md#approach'
USABILITY_METHOD='references/constraints/11-methods.md#early-value-check'
BOUNDED_INSPECTION='references/verification-scope.md#relevance'
CROSS_CUTTING_WORKSPACES={key:'references/game-workspaces.md#'+key for key in ('flow','playability')}
GAME_BLOCKS=('goal','rules','interaction','art','resources','tools','architecture','delivery')
ROLES=('progress','architecture')
REVIEW_STAGES=('planning','review')
_UNSPECIFIED_STAGE=object()
PLANNING_TASK='Independently establish effective original user outcomes, consumers, necessary quality and boundaries. AI extensions require worker/F/A agreement under source-authority.md#current-mainline. From primary artifacts assess route value, weakest supply/craft premise and a refuting observation before author/peer interpretations; investigate current route-changing or safety unknowns, then choose a supported next result under task-plan.md#plan-evaluation.'
PLANNING_DETAIL_POLICY='Preserve current authority/data/permissions and known vetoes. Route judgment is not production or whole-project acceptance; detailed audits follow actual dependencies. Reuse valid evidence; no fixed probe, alternative count or extra approval round.'
NON_CLAIMS=['A plan is not evidence of investigation or complete affected-block selection.',
 'Execution obligations are separate from product severity; product checks are uninvestigated.',
 'Source declarations do not authenticate identity or permission. No host or product executes.']
class CandidateError(ValueError): pass
class UnregisteredSelection(CandidateError): pass
class RetiredInterface(CandidateError): pass

def _pairs(items):
    data={}
    for key,value in items:
        if key in data: raise CandidateError('duplicate index key: '+key)
        data[key]=value
    return data

def _inside(root,name):
    if not isinstance(name,str) or not name: raise CandidateError('nonempty relative path required')
    target=(root/name).resolve()
    if target==root or not target.is_relative_to(root): raise CandidateError('path escapes package: '+name)
    return target

def _strings(items,label):
    if not isinstance(items,(list,tuple)) or len(items)>128: raise CandidateError(label+' must be a bounded list')
    if any(not isinstance(x,str) or not x.strip() for x in items): raise CandidateError(label+' requires names')
    return list(dict.fromkeys(items))

def _mapping(value,label):
    if not isinstance(value,dict): raise CandidateError(label+' must be a mapping')
    return value

def _load_index(root=ROOT):
    root=Path(root).resolve()
    _inside(root,INDEX)
    raw=reader.package_bytes(root/INDEX,root,256*1024)
    if len(raw)>256*1024: raise CandidateError('index exceeds 256 KiB')
    try:
        index=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=_pairs,
          parse_constant=lambda value: (_ for _ in ()).throw(CandidateError('nonfinite index value: '+value)))
    except RecursionError as exc:
        raise CandidateError('index JSON nesting exceeds capacity') from exc
    _mapping(index,'index')
    role_map=_mapping(index.get('roles'),'roles')
    templates=_mapping(index.get('templates'),'templates')
    cross_workspaces=_mapping(index.get('crossCuttingWorkspaces'),'crossCuttingWorkspaces')
    if type(index.get('schemaVersion')) is not int or index['schemaVersion']!=3 or set(role_map)!=set(ROLES):
        raise CandidateError('unsupported current index or role set')
    keys=_strings(index.get('blockKeys'),'blockKeys')
    if keys!=list(GAME_BLOCKS) or len(keys)!=len(index['blockKeys']): raise CandidateError('current eight game blocks required')
    checked={}
    def section(selector):
        if not isinstance(selector,str) or not selector: raise CandidateError('section selector required')
        if selector not in checked: checked[selector]=reader.read_section(selector,root)
        body=re.sub(r'(?m)^\s*#{1,6}[ \t]+[^\n]*$','',checked[selector]['content'])
        if not visible_text_present(body): raise CandidateError('visible section body missing: '+selector)
        return checked[selector]
    def same(selector,canonical,strict=True):
        def identity(record):
            offset=next((i for i,line in enumerate(record['content'].splitlines()) if re.match(r'^ {0,3}#{1,6}\s+',line)),None)
            if offset is None: raise CandidateError('section heading missing')
            return (record['resolvedSelector'].partition('#')[0],record['startLine']+offset,record['endLine'])
        matched=identity(section(selector))==identity(section(canonical))
        if strict and not matched: raise CandidateError('wrong section binding: '+selector)
        return matched
    required=['references/candidate-mechanism.md#'+x for x in ('selection','candidate-contract','blocks')]
    selectors=_strings(index.get('mechanismSections'),'mechanismSections')
    same(index['mechanism'],required[0])
    for required_selector in required:
        if not any(same(s,required_selector,strict=False) for s in selectors):
            raise CandidateError('required mechanism missing: '+required_selector)
    same(index.get('workspaceGuide'),WORKSPACE_GUIDE)
    if set(cross_workspaces)!=set(CROSS_CUTTING_WORKSPACES):
        raise CandidateError('cross-cutting workspaces incomplete')
    for name,selector in CROSS_CUTTING_WORKSPACES.items():same(index['crossCuttingWorkspaces'][name],selector)
    section('references/review-standard.md#failure-continuation')
    section(P0_SHARED_CONTRACT)
    section(PROJECT_CONTEXT)
    for project_selector in PROJECT_DECISIONS: section(project_selector)
    expanded_reads([PROJECT_CONTEXT],root)
    section(INDEPENDENT_INPUT_CONTRACT)
    for selector in SOURCE_MODE_CONTRACTS: section(selector)
    section(KNOWLEDGE_GUIDE)
    section(USABILITY_METHOD)
    section(BOUNDED_INSPECTION)
    expanded_reads([BOUNDED_INSPECTION],root)
    ids=set(); owners={}
    for role,prefix in [('progress','F'),('architecture','A')]:
        section(P0_CONTRACTS[role])
        if role=='architecture':section(P0_ARCHITECTURE_TRACKING)
        data=_mapping(role_map[role],'roles.'+role)
        card='references/'+('progress-correctness.md' if role=='progress' else 'architecture-ecology-playability.md')
        if data.get('card')!=card: raise CandidateError('wrong role card: '+role)
        for group,anchor,pattern in [('obligations','obligations-'+role,prefix+r'0-\d{2}'),('productChecks','products-'+role,prefix+r'-P0-\d{2}')]:
            entries=data.get(group)
            if not isinstance(entries,list) or not entries: raise CandidateError('missing role '+group)
            canonical=(P0_REFERENCES[role] if group=='productChecks' else card)+'#'+anchor
            actual=re.findall(r'^\|\s*('+pattern+r')\s*\|',section(canonical)['content'],re.M)
            registered=[]
            for entry in entries:
                _mapping(entry,role+'.'+group+' entry')
                candidate_id=entry['id']; same(entry['selector'],canonical)
                if not isinstance(candidate_id,str) or not re.fullmatch(pattern,candidate_id) or candidate_id in ids:
                    raise CandidateError('invalid/duplicate check identity')
                ids.add(candidate_id); owners[candidate_id]=role; registered.append(candidate_id)
                if group=='productChecks':
                    if entry.get('primaryRole')!=role or entry.get('severityIfConfirmed')!='P0':
                        raise CandidateError('product result primary role/severity differs: '+candidate_id)
                    _strings([entry.get('object')],'product result object')
                    row=re.search(r'^\|\s*'+re.escape(candidate_id)+r'\s*\|\s*([^|]+)\|',section(canonical)['content'],re.M)
                    if not row or row[1].strip()!=entry['object']:raise CandidateError('product result object differs from role catalogue: '+candidate_id)
                    same(entry['methodSelector'],P0_REFERENCES[role]+'#method-'+candidate_id.lower())
            if len(actual)!=len(set(actual)) or set(actual)!=set(registered): raise CandidateError('catalogue membership differs: '+role+'/'+group)
        product=data['productChecks']
        if len({x['object'] for x in product})!=len(product):
            raise CandidateError('duplicate role-owned product result')
        catalogue=data.get('checks')
        if not isinstance(catalogue,list) or not catalogue:raise CandidateError('unique check catalogue required')
        registered=[]
        for entry in catalogue:
            _mapping(entry,role+'.checks entry')
            member=entry['id']
            if not isinstance(member,str) or not re.fullmatch(prefix+r'1-\d{2}',member) or member in ids:
                raise CandidateError('invalid/duplicate check identity')
            record=section(entry['selector'])
            if record['resolvedSelector'].partition('#')[0]!=card:
                raise CandidateError('wrong check card: '+member)
            actual=re.findall(r'^\|\s*('+prefix+r'1-\d{2})\s*\|',record['content'],re.M)
            if actual.count(member)!=1:raise CandidateError('check method binding differs: '+member)
            ids.add(member); owners[member]=role; registered.append(member)
        actual=re.findall(r'^\|\s*('+prefix+r'1-\d{2})\s*\|',section(card+'#p1-'+role)['content'],re.M)
        if len(actual)!=len(set(actual)) or set(actual)!=set(registered):raise CandidateError('role check catalogue differs')
        shared=_strings(data.get('sharedChecks'),'shared checks')
        if not shared or len(shared)!=len(data['sharedChecks']) or set(shared)-set(registered):
            raise CandidateError('invalid shared check references')
        referenced=set(shared)
        block_map=_mapping(data.get('blocks'),role+'.blocks')
        if set(block_map)!=set(keys): raise CandidateError('role blocks incomplete')
        for block,entry in block_map.items():
            _mapping(entry,role+'.blocks.'+block)
            canonical='references/game-workspaces.md#'+block
            same(entry['selector'],canonical)
            members=_strings(entry.get('candidates'),'block candidates')
            if not members or len(members)!=len(entry['candidates']) or set(members)-set(registered):
                raise CandidateError('invalid block check references: '+role+'/'+block)
            referenced.update(members)
        cross_checks=_mapping(data.get('crossCuttingChecks'),role+'.crossCuttingChecks')
        if set(cross_checks)!=set(CROSS_CUTTING_WORKSPACES):
            raise CandidateError('cross-cutting check references incomplete')
        for workspace,members in cross_checks.items():
            unique=_strings(members,'cross-cutting check references')
            if not unique or len(unique)!=len(members) or set(unique)-set(registered):
                raise CandidateError('invalid cross-cutting check references: '+role+'/'+workspace)
            referenced.update(unique)
        if referenced!=set(registered):raise CandidateError('unreachable role check method')
        same(data['directedSelector'],card+'#directed-'+role)
    symptoms=index.get('symptoms')
    if symptoms is not None:
        if not isinstance(symptoms,dict) or not symptoms or len(symptoms)>32:
            raise CandidateError('symptom map must be a bounded mapping')
        registered_ids=ids
        for key,entry in symptoms.items():
            if not isinstance(key,str) or not re.fullmatch(r'[a-z][a-z0-9-]{2,40}',key):
                raise CandidateError('invalid symptom key: '+str(key))
            if not isinstance(entry,dict): raise CandidateError('symptom entry must be a mapping: '+key)
            for field in ('title','cannotConclude'):
                if not isinstance(entry.get(field),str) or not entry[field].strip():
                    raise CandidateError('symptom '+field+' required: '+key)
            for field in ('blocks','templates','staticChain','legalContrast'):
                _strings(entry.get(field),'symptom '+field)
            if not entry['blocks'] or set(entry['blocks'])-set([*index['blockKeys'],*index['crossCuttingWorkspaces']]):
                raise CandidateError('symptom blocks must name current blocks: '+key)
            if set(entry['templates'])-set(index['templates']):
                raise CandidateError('symptom templates must name current cards: '+key)
            if not entry['staticChain'] or not entry['legalContrast']:
                raise CandidateError('symptom needs static chain and legal contrast: '+key)
            for role in ROLES:
                members=_strings(entry.get(role,[]),'symptom '+role)
                if set(members)-registered_ids:
                    raise CandidateError('symptom names an unregistered check: '+key+'/'+role)
                misplaced=[m for m in members if owners.get(m)!=role]
                if misplaced:
                    raise CandidateError('symptom puts a result under the wrong role: '+key+'/'+role+': '+', '.join(misplaced))
    if set(templates)!={f'U{i}' for i in range(1,10)}: raise CandidateError('operation cards incomplete')
    for name,selector in templates.items(): same(selector,'references/unity-candidates.md#'+name.lower())
    return index

def load_index(root=ROOT):
    with reader.reading_session(root):
        return _load_index(root)


def expanded_reads(selectors,root=ROOT):
    try:
        return [record['selector'] for record in reader.expanded_sections(selectors,root)]
    except ValueError as exc:
        raise CandidateError(str(exc)) from exc


def review_stage(value=_UNSPECIFIED_STAGE):
    if value is _UNSPECIFIED_STAGE:
        return 'unresolved','caller-must-select-stage'
    if not isinstance(value,str) or value not in REVIEW_STAGES:
        raise CandidateError('review stage must be planning or review')
    return value,'explicit'


def _unity_planning_reads(root=ROOT,role='both'):
    """One planning selection shared by ordinary plans and native-role preparation."""
    if role not in (*ROLES,'both'):raise CandidateError('unknown role')
    index=load_index(root)
    selected=ROLES if role=='both' else (role,)
    selectors=['references/reading-guide.md#planning-round',
        'references/reading-guide.md#unity-planning',
        *(P0_CONTRACTS[name] for name in selected),P0_SHARED_CONTRACT,
        *SOURCE_MODE_CONTRACTS,INDEPENDENT_INPUT_CONTRACT,PROJECT_CONTEXT,
        KNOWLEDGE_GUIDE,USABILITY_METHOD,BOUNDED_INSPECTION,
        *(x['selector'] for name in selected for x in index['roles'][name]['obligations']),
        *(x['selector'] for name in selected for x in index['roles'][name]['productChecks'])]
    return expanded_reads(selectors,root)



PROFILE_DOMAINS=('general','maintenance','unity')
PROFILE_ROLES=('worker','dialogue','target',*ROLES)

def read_profile(root=ROOT, role='worker', stage='review', domain='general'):
    """The sole role/stage/domain read authority; does not infer a business domain from scope kind."""
    if role not in (*PROFILE_ROLES,'both') or domain not in PROFILE_DOMAINS or stage not in REVIEW_STAGES:
        raise CandidateError('profile requires registered role, explicit stage and business domain')
    raw=reader.package_bytes(Path(root)/INDEX,root,256*1024)
    try: profiles=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=_pairs)['readProfiles']
    except (KeyError,ValueError,UnicodeError) as exc: raise CandidateError('read profile authority unavailable') from exc
    if profiles.get('schemaVersion')!=1: raise CandidateError('unsupported read profiles')
    selected=ROLES if role=='both' else (role,)
    seeds=[*profiles['stages'][stage],*profiles['base'],
           *(s for name in selected for s in profiles['roles'][name]),
           *profiles['domains'][domain],*profiles.get('domainStages',{}).get(domain+':'+stage,[])]
    # Unity's existing detailed catalogue and P0 contracts remain authoritative.
    if domain=='unity' and stage=='planning' and role in (*ROLES,'both'):
        seeds+=_unity_planning_reads(root,role)
    elif domain=='unity' and role in (*ROLES,'both'):
        index=load_index(root)
        seeds += [*(P0_CONTRACTS[name] for name in selected),P0_SHARED_CONTRACT,
          PROJECT_CONTEXT,KNOWLEDGE_GUIDE,USABILITY_METHOD,BOUNDED_INSPECTION,index['workspaceGuide'],
          *index['crossCuttingWorkspaces'].values(),*index['mechanismSections'],
          *(x['selector'] for name in selected for x in index['roles'][name]['obligations']),
          *(x['selector'] for name in selected for x in index['roles'][name]['productChecks']),
          *(x['selector'] for name in selected for x in index['roles'][name]['checks'] if x['id'] in index['roles'][name]['sharedChecks'])]
    return dict(status='profile-selected',role=role,reviewStage=stage,reviewDomain=domain,
                readSelectors=expanded_reads(list(dict.fromkeys(seeds)),root),autoExecute=False,
                routeAuthority=INDEX+'#/readProfiles',sourceAuthenticated=False)

def planning_reads(root=ROOT,role='both',domain='unity'):
    # Existing Unity API remains compatible; generic callers select their real domain.
    return read_profile(root,role,'planning',domain)['readSelectors']


def _inspect_index(root=ROOT,include_legacy=False):
    if include_legacy: raise RetiredInterface('Old leaf CLI withdrawn; consult the archived original package. Named investigation remains allowed.')
    index=load_index(root)
    return dict(status='materials-readable',schemaVersion=3,autoExecute=False,reviewContractSelectors=P0_CONTRACTS,commonReviewContractSelector=P0_SHARED_CONTRACT,mechanism=index['mechanism'],
      mechanismSections=index['mechanismSections'],blockKeys=index['blockKeys'],
      workspaceGuideSelector=index['workspaceGuide'],crossCuttingWorkspaceSelectors=index['crossCuttingWorkspaces'],
      roles={role:dict(obligations=[x['id'] for x in data['obligations']],productChecks=data['productChecks'],card=data['card'],
        blockCandidates=len(data['checks'])) for role,data in index['roles'].items()},
      templates=index['templates'],nonClaims=NON_CLAIMS)

def inspect_index(root=ROOT,include_legacy=False):
    with reader.reading_session(root):
        return _inspect_index(root,include_legacy)

def _plan(root=ROOT,role='both',blocks=(),templates=(),legacy_ids=(),product_ids=(),symptom_ids=(),review_stage_value=_UNSPECIFIED_STAGE,domain='unity'):
    stage,stage_source=review_stage(review_stage_value)
    if legacy_ids: raise RetiredInterface('Old leaf CLI withdrawn; use archived original or investigate a named current hypothesis.')
    if role not in (*ROLES,'both'): raise CandidateError('unknown role')
    if stage=='unresolved':
        return dict(schemaVersion=3,status='stage-unresolved',autoExecute=False,
          reviewStage=stage,stageSelectionSource=stage_source,candidates=[],readSelectors=[],
          reason='Caller must determine this task stage: planning for route/first work, review for a supported route or mature repair. Do not ask the user to approve a routine stage choice.',
          nonClaims=NON_CLAIMS)
    if domain not in PROFILE_DOMAINS: raise CandidateError('unknown review domain')
    if domain!='unity':
        if blocks or templates or product_ids or symptom_ids:
            raise CandidateError('Unity catalogue selections require domain unity')
        profile=read_profile(root,role,stage,domain)
        return dict(schemaVersion=3,status='planned',autoExecute=False,roles=list(ROLES if role=='both' else (role,)),
          reviewStage=stage,stageSelectionSource=stage_source,reviewDomain=domain,candidates=[],
          readSelectors=profile['readSelectors'],routeAuthority=profile['routeAuthority'],nonClaims=NON_CLAIMS)
    index=load_index(root)
    if role not in (*ROLES,'both'): raise CandidateError('unknown role')
    blocks=_strings(blocks,'blocks'); templates=_strings(templates,'templates')
    if set(blocks)-set([*index['blockKeys'],*index['crossCuttingWorkspaces']]) or set(templates)-set(index['templates']): raise UnregisteredSelection('Unregistered selection; investigate the named affected block/hypothesis manually.')
    selected=ROLES if role=='both' else (role,)
    symptom_ids=_strings(symptom_ids,'symptoms')
    symptom_refs=[]
    extra_checks={name:[] for name in selected}
    if symptom_ids:
        table=index.get('symptoms') or {}
        unknown=[x for x in symptom_ids if x not in table]
        if unknown: raise UnregisteredSelection('Unknown symptom selection: '+', '.join(unknown))
        blocks=list(blocks); templates=list(templates); product_ids=list(product_ids)
        for key in symptom_ids:
            entry=table[key]; symptom_refs.append(dict(id=key,**entry))
            blocks+=list(entry['blocks']); templates+=list(entry['templates'])
            for name in selected:
                for member in entry.get(name,[]):
                    (product_ids if '-P0-' in member else extra_checks[name]).append(member)
        blocks=list(dict.fromkeys(blocks)); templates=list(dict.fromkeys(templates))
        product_ids=list(dict.fromkeys(product_ids))
        for name in extra_checks: extra_checks[name]=list(dict.fromkeys(extra_checks[name]))
    product_ids=_strings(product_ids,'product results')
    available={entry['id']:(name,entry) for name in selected for entry in index['roles'][name]['productChecks']}
    if set(product_ids)-set(available):raise UnregisteredSelection('Unknown or different primary-role result; investigate/transfer the named proposition manually.')
    checks=[]
    for name in selected:
        data=index['roles'][name]
        for entry in data['obligations']:
            checks.append(dict(role=name,**entry,type='obligation',activation='each-substantive-review',state='planned'))
        for entry in data['productChecks']:
            checks.append(dict(role=name,**entry,type='product-check',activation='scope-and-object-check',state='planned'))
        catalogue={x['id']:x for x in data['checks']}
        activated={identity:['shared-workspaces'] for identity in data['sharedChecks']} if stage=='review' else {}
        for identity in extra_checks.get(name,()): activated.setdefault(identity,[]).append('symptom')
        for block in index['blockKeys']:
            if block in blocks:
                entry=data['blocks'][block]
                for identity in entry['candidates']:activated.setdefault(identity,[]).append(block)
        for workspace,members in data['crossCuttingChecks'].items():
            if workspace in blocks:
                for identity in members:activated.setdefault(identity,[]).append(workspace)
        for identity,triggers in activated.items():
            checks.append(dict(role=name,**catalogue[identity],type='shared-check' if identity in data['sharedChecks'] else 'work-block',
                activation=triggers[0],activatedBy=triggers,state='planned'))
    template_refs=[dict(id=x,selector=index['templates'][x]) for x in templates]
    method_refs=[dict(role=available[x][0],id=x,selector=available[x][1]['methodSelector']) for x in product_ids]
    selectors=list(dict.fromkeys([*(P0_CONTRACTS[name] for name in selected),*SOURCE_MODE_CONTRACTS,INDEPENDENT_INPUT_CONTRACT,P0_SHARED_CONTRACT,PROJECT_CONTEXT,KNOWLEDGE_GUIDE,USABILITY_METHOD,BOUNDED_INSPECTION,index['workspaceGuide'],*index['crossCuttingWorkspaces'].values(),
        *('references/game-workspaces.md#'+block for block in index['blockKeys'] if block in blocks),*index['mechanismSections'],'references/review-standard.md#decision-order',
        *(x['selector'] for x in checks),*(x['selector'] for x in template_refs),*(x['selector'] for x in method_refs),
        *(['references/review-standard.md#failure-continuation'] if method_refs else []),
        *(['references/recognition.md#symptom-trace','references/recognition.md#perspective','references/recognition.md#unit-state'] if symptom_refs else [])]))
    selectors=list(dict.fromkeys([*read_profile(root,role,stage,domain)['readSelectors'],*selectors]))
    if stage=='planning':
        selectors=list(dict.fromkeys([*planning_reads(root,role),
            *('references/game-workspaces.md#'+block for block in index['blockKeys'] if block in blocks),
            *(x['selector'] for x in checks),*(x['selector'] for x in template_refs),*(x['selector'] for x in method_refs),
            *(['references/review-standard.md#failure-continuation'] if method_refs else []),
            *(['references/recognition.md#symptom-trace','references/recognition.md#perspective','references/recognition.md#unit-state'] if symptom_refs else [])]))
    result=dict(schemaVersion=3,status='planned',autoExecute=False,roles=list(selected),declaredBlocks=blocks,candidates=checks,
      reviewStage=stage,stageSelectionSource=stage_source,
      workspaceGuideSelector=index['workspaceGuide'],crossCuttingWorkspaceSelectors=index['crossCuttingWorkspaces'],usabilityMethodSelector=USABILITY_METHOD,
      reviewContractSelectors={name:P0_CONTRACTS[name] for name in selected},commonReviewContractSelector=P0_SHARED_CONTRACT,investigationTemplates=template_refs,investigationMethods=method_refs,readSelectors=expanded_reads(selectors,root),
      knowledgeLookupGuideSelector=KNOWLEDGE_GUIDE,knowledgeIndexSelector=KNOWLEDGE_INDEX,knowledgeLookupRequiredWhen=list(KNOWLEDGE_TRIGGERS),
      symptomRefs=symptom_refs,
      additionalCandidates='Inspect evidence-based named hypotheses without waiting for registration.',nonClaims=NON_CLAIMS)
    if stage=='planning':result.update(firstReviewTask=PLANNING_TASK,stageDetailPolicy=PLANNING_DETAIL_POLICY)
    return result

def plan(root=ROOT,role='both',blocks=(),templates=(),legacy_ids=(),product_ids=(),symptom_ids=(),review_stage=_UNSPECIFIED_STAGE,domain='unity'):
    with reader.reading_session(root):
        return _plan(root,role,blocks,templates,legacy_ids,product_ids,symptom_ids,review_stage,domain)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('inspect','plan','route')); parser.add_argument('--role',choices=(*PROFILE_ROLES,'both'),default='both')
    parser.add_argument('--block',action='append',default=[]); parser.add_argument('--template',action='append',default=[])
    parser.add_argument('--product',action='append',default=[],help='Read the complete method for an affected current primary-role result; never a finding declaration.')
    parser.add_argument('--symptom',action='append',default=[],help='Map a named symptom to affected blocks, cards and checks; never a finding declaration.')
    parser.add_argument('--review-stage',choices=REVIEW_STAGES,default=_UNSPECIFIED_STAGE,help='Caller selects planning or mature review; omission returns stage-unresolved, never an implicit detailed review.')
    parser.add_argument('--legacy',action='append',default=[]); parser.add_argument('--include-legacy',action='store_true')
    parser.add_argument('--domain',choices=PROFILE_DOMAINS,default='unity')
    parser.add_argument('--emit-page',type=int)
    parser.add_argument('--emit-bytes',type=int,default=None)
    parser.add_argument('--expect-emission')
    args=parser.parse_args(argv)
    try:
        if args.emit_bytes is not None and args.emit_page is None:raise CandidateError('--emit-bytes requires --emit-page')
        if args.expect_emission is not None and args.emit_page is None:raise CandidateError('--expect-emission requires --emit-page')
        if args.include_legacy or args.legacy: raise RetiredInterface('Old leaf CLI withdrawn; original package is archived outside this installation.')
        if args.operation=='inspect' and args.review_stage is not _UNSPECIFIED_STAGE:
            raise CandidateError('review stage applies to plan, not inspect')
        if args.operation=='inspect' and args.symptom:
            raise UnregisteredSelection('inspect lists registered material only; a symptom needs plan to route it.')
        if args.operation=='route':
            if args.review_stage is _UNSPECIFIED_STAGE: raise CandidateError('route requires explicit review stage')
            result=read_profile(role=args.role,stage=args.review_stage,domain=args.domain)
        else: result=inspect_index() if args.operation=='inspect' else plan(role=args.role,blocks=args.block,templates=args.template,product_ids=args.product,symptom_ids=args.symptom,review_stage=args.review_stage,domain=args.domain)
    except RetiredInterface as exc:
        result=dict(status='retired-interface',reason=str(exc),autoExecute=False); code=2
    except UnregisteredSelection as exc:
        result=dict(status='unregistered-selection',reason=str(exc),autoExecute=False,nextAction='Check role obligations, role-owned results/methods, every affected block and named directed hypotheses; transfer cross-role evidence without waiting.'); code=2
    except (OSError,UnicodeError,ValueError,KeyError,TypeError) as exc:
        result=dict(status='invalid-candidate-material',reason=str(exc),autoExecute=False); code=2
    else: code=0
    if code==0 and args.emit_page is not None:
        from jury_io import emission_page
        try:result=emission_page(result,args.emit_page,6144 if args.emit_bytes is None else args.emit_bytes,args.expect_emission)
        except ValueError as exc:
            result=dict(status='invalid-emission',reason=str(exc),autoExecute=False);code=2
    print(json.dumps(result,ensure_ascii=False,indent=2)); return code
if __name__=='__main__': raise SystemExit(main())
