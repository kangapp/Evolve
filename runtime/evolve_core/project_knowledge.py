"""Typed knowledge, observed coverage and navigation over existing immutable records."""
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .errors import EvolveError
from .package import ROOT, digest
from .workspace import current_digest, inside

PERSPECTIVES = ('purpose', 'domain', 'behavior', 'code', 'contracts', 'verification', 'decisions', 'risks')
DIMENSIONS = ('structure', 'sources', 'consistency', 'usefulness')
KINDS = {
    'project': ('project.md', ('项目定位', '目标与边界', '主要能力', '知识导航', '覆盖与缺口')),
    'codemap': ('codemap.md', ('范围', '运行入口', '模块职责', '关键链路', '数据与依赖', '检查与修改入口', '未覆盖范围')),
    'domain': ('domain.md', ('领域范围', '业务术语', '对象关系', '相关规格')),
    'spec': ('specs/<capability>/spec.md', ('能力与边界', '前置条件', '行为规则', '异常与边界', '验收场景', '依据与待决问题')),
    'decision': ('decisions/<number>-<topic>.md', ('背景', '决定', '理由与影响')),
    'development': ('guides/development.md', ('前置条件', '环境与启动', '检查与预期结果', '问题与限制')),
    'architecture': ('guides/architecture.md', ('范围与边界', '组件与职责', '交互与依赖', '约束与决定')),
    'data': ('guides/data.md', ('对象与来源', '标识与粒度', '关系与转换', '时间与单位口径', '质量与限制')),
    'rule': ('guides/rules.md', ('适用范围', '规则', '依据与例外')),
}


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise EvolveError('KNOWLEDGE_INPUT', name + ' must be nonempty text')
    return value


def templates(kind=None):
    if kind is not None and kind not in KINDS:
        raise EvolveError('KNOWLEDGE_KIND', 'Unknown document kind')
    result = {'committed': False, 'template_version': 1, 'acceptance_dimensions': list(DIMENSIONS),
              'kinds': {key: {'default_path': 'evolve/' + value[0], 'sections': list(value[1])} for key, value in KINDS.items()}}
    if kind:
        result.update(kind=kind, template=(ROOT / ('assets/templates/knowledge-' + kind + '.md')).read_text())
    return result


def observed_sources(root, sources, store=None):
    if not isinstance(sources, list):
        raise EvolveError('KNOWLEDGE_SOURCE', 'Provide an explicit source list')
    result, seen = [], set()
    for source in sources:
        if not isinstance(source, dict):
            raise EvolveError('KNOWLEDGE_SOURCE', 'Each source must identify actual material')
        name = nonempty(source.get('path'), 'source.path')
        path = inside(root, name)
        if name in seen or not path.is_file() or current_digest(path) != source.get('expected_digest'):
            raise EvolveError('KNOWLEDGE_SOURCE', 'Source is missing, repeated or changed: ' + name, exit_code=3)
        content = path.read_bytes()
        if digest(content) != source['expected_digest']:
            raise EvolveError('KNOWLEDGE_SOURCE', 'Source changed while reading: ' + name, exit_code=3)
        if store:
            store.blob(content)
        result.append({'path': name, 'expected_digest': source['expected_digest']})
        seen.add(name)
    return result


def structure_errors(content, sections):
    errors = []
    if content.count('```') % 2:
        errors.append('Unclosed fenced block')
    prose = re.sub(r'```[^\n]*\n.*?```', '', content, flags=re.S)
    found = list(re.finditer(r'^#{1,6}\s+(.+?)\s*$', prose, re.M))
    for title in sections:
        match = next((m for m in found if m[1] == title), None)
        if match is None:
            errors.append('Missing section: ' + title)
            continue
        end = next((m.start() for m in found if m.start() > match.start()), len(prose))
        if not prose[match.end():end].strip():
            errors.append('Empty section: ' + title)
    if re.search(r'\{\{[^}]+\}\}|\bTODO\b|待填写', prose):
        errors.append('Unresolved template placeholder')
    ids = re.findall(r'^\s*(?:[-*]\s+)?\*{0,2}((?:REQ|AC)-[A-Za-z0-9_-]+)\*{0,2}\s*[:：]', prose, re.M)
    if len(ids) != len(set(ids)):
        errors.append('Repeated requirement or acceptance identity')
    return errors


def document_errors(root, name, content, *, alternatives=None):
    """Check local references and graph source shape; rendering remains a named observation."""
    root = Path(root).resolve()
    path = inside(root, name)
    alternatives = alternatives or {}
    errors = []
    prose = re.sub(r'```[^\n]*\n.*?```', '', content, flags=re.S)
    for link in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', prose):
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc:
            continue
        target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
        if not target.is_relative_to(root):
            errors.append('Reference escapes project: ' + link)
            continue
        relative = target.relative_to(root).as_posix()
        text = alternatives.get(relative)
        if target == path:
            text = content
        if text is None and not target.exists():
            errors.append('Missing reference: ' + link)
        elif parsed.fragment and target.suffix == '.md':
            text = text if text is not None else target.read_text()
            titles = re.findall(r'^#{1,6}\s+(.+?)\s*$', text, re.M)
            anchors = {re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-') for title in titles}
            anchors.update(re.findall(r'<a\s+id=[\'"]([^\'"]+)', text))
            if unquote(parsed.fragment) not in anchors:
                errors.append('Missing anchor: ' + link)
    for graph in re.findall(r'```mermaid\s*\n(.*?)```', content, re.S):
        if not graph.strip() or not re.match(r'\s*(?:flowchart|graph|sequenceDiagram|stateDiagram(?:-v2)?|erDiagram|classDiagram|mindmap|timeline|gantt|journey|pie)\b', graph):
            errors.append('Missing or unsupported Mermaid diagram declaration')
    return errors


def require_retained_topics(root, catalog, name, topics):
    retained = {d['topic'] for d in catalog if d['active'] and inside(root, d['path']).resolve() == inside(root, name).resolve()}
    if retained - {t['topic'] for t in topics}:
        raise EvolveError('KNOWLEDGE_AUTHORITY', 'Retain current topic mappings in a revised document; move topics through explicit replacement', exit_code=3)


def document_definition(store, data, owner):
    value = data.get('document')
    if value is None:
        if store.one("SELECT id FROM events WHERE kind IN ('knowledge_survey_recorded','knowledge_document_applied') LIMIT 1"):
            raise EvolveError('KNOWLEDGE_DOCUMENT', 'Surveyed projects require typed knowledge and its sources')
        return None
    if not isinstance(value, dict) or value.get('kind') not in KINDS:
        raise EvolveError('KNOWLEDGE_KIND', 'Document must identify its supported kind')
    path = inside(store.root, data['path'])
    local = path.relative_to(store.root).parts
    mapped = value.get('mode', 'managed') == 'mapped'
    if mapped:
        if owner != 'evolve-init' or not path.is_file() or path.read_bytes() != data['content'].encode():
            raise EvolveError('KNOWLEDGE_LOCATION', 'Initial mapping preserves exact existing text')
    elif len(local) < 2 or local[0] != 'evolve' or path.resolve().relative_to(store.root).parts[0] != 'evolve':
        raise EvolveError('KNOWLEDGE_LOCATION', 'New and revised knowledge belongs under evolve/')
    topic = nonempty(value.get('topic'), 'document.topic')
    scope = nonempty(value.get('scope'), 'document.scope')
    roles = value.get('roles', [value['kind']])
    if (not isinstance(roles, list) or any(not isinstance(role, str) or role not in KINDS for role in roles)
            or value['kind'] not in roles or len(set(roles)) != len(roles) or not mapped and roles != [value['kind']]):
        raise EvolveError('KNOWLEDGE_KIND', 'Only an existing mapped document can carry multiple supported roles')
    sources = observed_sources(store.root, value.get('sources'), store)
    if not mapped and any(inside(store.root, source['path']).resolve() == path.resolve() for source in sources):
        raise EvolveError('KNOWLEDGE_SOURCE', 'A replacement cannot use its target as a live source; the prior formal version already retains its baseline')
    sections = value.get('sections', list(KINDS[value['kind']][1]))
    if not isinstance(sections, list) or any(not isinstance(s, str) or not s.strip() for s in sections):
        raise EvolveError('KNOWLEDGE_STRUCTURE', 'Sections must name actual headings')
    if len(set(sections)) != len(sections):
        raise EvolveError('KNOWLEDGE_STRUCTURE', 'Declared headings must be distinct; responsibilities may share a section')
    if not mapped:
        errors = structure_errors(data['content'], sections)
        if errors:
            raise EvolveError('KNOWLEDGE_STRUCTURE', '; '.join(errors))
    if not set(DIMENSIONS).issubset({c['key'] for c in data['acceptance']}):
        raise EvolveError('KNOWLEDGE_CRITERIA', 'Review structure, sources, consistency and usefulness explicitly')
    if '```mermaid' in data['content'] and 'diagrams' not in {c['key'] for c in data['acceptance']}:
        raise EvolveError('KNOWLEDGE_CRITERIA', 'Diagrams require an explicit rendering and text-consistency observation')
    topics = value.get('topics', [{'topic': topic, 'section': None}])
    if (not isinstance(topics, list) or not topics or any(not isinstance(t, dict) or not isinstance(t.get('topic'), str) or not t['topic'].strip() for t in topics)
            or len({t['topic'] for t in topics}) != len(topics)):
        raise EvolveError('KNOWLEDGE_AUTHORITY', 'Document topics need distinct stable identities')
    for item in topics:
        if set(item) - {'topic', 'section'}:
            raise EvolveError('KNOWLEDGE_AUTHORITY', 'Topic metadata cannot override computed navigation or authority')
        if item.get('section') is not None and (not isinstance(item['section'], str) or item['section'] not in {m[1] for m in re.finditer(r'^#{1,6}\s+(.+?)\s*$', data['content'], re.M)}):
            raise EvolveError('KNOWLEDGE_STRUCTURE', 'Mapped topic section does not exist')
    replaced = value.get('replaces', [])
    if not isinstance(replaced, list):
        raise EvolveError('KNOWLEDGE_MIGRATION', 'Replacements identify exact current topics')
    catalog = catalog_view(store.connection, store.root)['documents']
    require_retained_topics(store.root, catalog, data['path'], topics)
    for old in replaced:
        match = next((d for d in catalog if d['topic'] == old.get('topic') and d['path'] == old.get('path') and d['active']), None) if isinstance(old, dict) else None
        if not match or match['artifact_version_id'] != old.get('artifact_version_id') or match['current_digest'] != match['registered_digest']:
            raise EvolveError('KNOWLEDGE_MIGRATION', 'Replacement source is stale or not active', exit_code=3)
    active = [d for d in catalog if d['topic'] in {t['topic'] for t in topics} and d['active'] and d['path'] != data['path']]
    if any(not any(r['path'] == d['path'] and r['topic'] == d['topic'] for r in replaced) for d in active):
        raise EvolveError('KNOWLEDGE_AUTHORITY', 'The active topic must be explicitly replaced, not duplicated')
    return {'kind': value['kind'], 'roles': roles, 'topic': topic, 'scope': scope, 'mode': 'mapped' if mapped else 'managed',
            'sources': sources, 'sections': sections, 'topics': topics, 'replaces': replaced, 'template_version': 1}


def require_document_current(store, proposal):
    """Recheck input material and transferred authority before any actual application."""
    from .knowledge_proposals import metadata
    doc = (metadata(proposal) or {}).get('document')
    if not doc:
        if store.one("SELECT id FROM events WHERE kind IN ('knowledge_survey_recorded','knowledge_document_applied') LIMIT 1"):
            raise EvolveError('KNOWLEDGE_DOCUMENT', 'Managed projects apply typed knowledge only')
        return
    observed_sources(store.root, doc['sources'])
    catalog = catalog_view(store.connection, store.root)['documents']
    require_retained_topics(store.root, catalog, proposal['target_path'], doc['topics'])
    formal = store.one("SELECT current_version FROM artifacts WHERE path=? AND kind='knowledge'", (proposal['target_path'],))
    if formal and formal['current_version'] != metadata(proposal)['formal_version_id']:
        current = store.one('SELECT p.* FROM knowledge_proposals p JOIN spec_applications a ON a.proposal_id=p.id WHERE a.artifact_version_id=?', (formal['current_version'],))
        if not current or (metadata(current) or {}).get('document') != doc:
            raise EvolveError('KNOWLEDGE_METADATA', 'Formal document metadata advanced; rebase the typed candidate before composing its text', exit_code=3)
    for replaced in doc['replaces']:
        item = next((d for d in catalog if d['active'] and d['topic'] == replaced['topic'] and d['path'] == replaced['path']), None)
        if not item or item['artifact_version_id'] != replaced['artifact_version_id'] or item['current_digest'] != item['registered_digest']:
            raise EvolveError('KNOWLEDGE_MIGRATION', 'Authority source changed before application', exit_code=3)
    target_topics = {t['topic'] for t in doc['topics']}
    for item in catalog:
        if item['active'] and item['topic'] in target_topics and item['path'] != proposal['target_path']:
            if not any(r['path'] == item['path'] and r['topic'] == item['topic'] and r['artifact_version_id'] == item['artifact_version_id'] for r in doc['replaces']):
                raise EvolveError('KNOWLEDGE_AUTHORITY', 'Topic acquired another authority before application', exit_code=3)


def catalog_view(connection, root):
    from .knowledge_proposals import metadata, source_facts
    from .formal import application_source
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'events', 'spec_applications', 'knowledge_proposals', 'phase_runs', 'operations'}.issubset(tables):
        return {'available': False, 'documents': [], 'survey': None,
                'initial_delivery': {'status': 'unavailable', 'scope': None},
                'limitation': 'Knowledge records are unavailable in this archive; no repair or inference performed.'}
    documents = []
    observations = {}
    for event in connection.execute("SELECT run_id,payload_json FROM events WHERE kind='knowledge_applicability_observed' ORDER BY rowid"):
        if source_facts(connection, event['run_id']) is not None:
            value = json.loads(event['payload_json'])
            observations[value['artifact_version_id']] = {**value, 'run_id': event['run_id']}
    for app in connection.execute('SELECT * FROM spec_applications ORDER BY rowid'):
        proposal = connection.execute('SELECT * FROM knowledge_proposals WHERE id=?', (app['proposal_id'],)).fetchone()
        value = metadata(proposal) or {}
        doc = value.get('document')
        if not doc or application_source(connection, app) is None:
            continue
        actual = current_digest(inside(root, proposal['target_path']))
        sources = [{**source, 'status': 'matching_local_bytes' if current_digest(inside(root, source['path'])) == source['expected_digest'] else 'changed_or_unavailable'} for source in doc['sources']]
        review = observations.get(app['artifact_version_id'])
        if review and actual == review['document_digest']:
            for source in sources:
                current_review = next((s for s in review['sources'] if s['path'] == source['path']), None)
                if current_review and current_digest(inside(root, source['path'])) == current_review['expected_digest']:
                    source['status'] = 'matching_reviewed_bytes'
                    source['reviewed_digest'] = current_review['expected_digest']
                    source['review_run_id'] = review['run_id']
        item = {**doc, 'path': proposal['target_path'], 'application_id': app['id'],
                'artifact_version_id': app['artifact_version_id'], 'registered_digest': app['result_digest'],
                'current_digest': actual, 'sources': sources, 'active': True,
                'verification_id': app['verification_id'],
                'applicability': 'matching_local_bytes' if actual == app['result_digest'] and all(s['status'] in ('matching_local_bytes', 'matching_reviewed_bytes') for s in sources) else 'needs_review',
                'external_data': 'not_reobserved'}
        for old in documents:
            if old['path'] == item['path'] or any(r['path'] == old['path'] and r['topic'] == old['topic'] for r in item['replaces']):
                old['active'] = False
                old['superseded_by'] = {'path': item['path'], 'topic': item['topic'], 'artifact_version_id': item['artifact_version_id']}
        for topic in doc['topics']:
            documents.append({**item, **topic})
    survey = None
    for event in connection.execute("SELECT run_id,payload_json FROM events WHERE kind='knowledge_survey_recorded' ORDER BY rowid"):
        if source_facts(connection, event['run_id']) is not None:
            survey = json.loads(event['payload_json'])
    completed = next((json.loads(e['payload_json']) for e in connection.execute(
        "SELECT run_id,payload_json FROM events WHERE kind='knowledge_initial_delivery_completed' ORDER BY rowid DESC")
        if source_facts(connection, e['run_id']) is not None), None)
    if completed and (not survey or completed.get('survey_digest') != digest(json.dumps(survey, sort_keys=True).encode())):
        completed = None
    return {'available': True, 'documents': documents, 'survey': survey,
            'initial_delivery': {'status': 'completed' if completed else 'pending',
                                 'scope': completed['scope'] if completed else None,
                                 'applicability': 'historical_not_revalidated' if completed else 'not_delivered'}}


def document_verified(connection, document):
    """Use the application's latest safe observation of these exact formal bytes."""
    from .work import verification_source
    verification = connection.execute('SELECT * FROM verifications WHERE id=?', (document['verification_id'],)).fetchone()
    if not verification or verification['status'] != 'passed' or verification_source(connection, verification) is None:
        return False
    snapshot = json.loads(verification['fingerprint_json'])
    items = json.loads(verification['items_json'])
    return (items.get('application_id') == document['application_id']
            and snapshot.get('artifact_version_id') == document['artifact_version_id']
            and snapshot.get('actual_digest') == document['registered_digest'] == document['current_digest'])


def _survey(store, data, run_id):
    scope = data.get('scope')
    if not isinstance(scope, list) or not scope or any(not isinstance(s, str) for s in scope):
        raise EvolveError('KNOWLEDGE_COVERAGE', 'Survey requires explicit project-relative scope')
    for path in scope:
        inside(store.root, path)
    sources = observed_sources(store.root, data.get('sources'), store)
    for source in sources:
        if not any(inside(store.root, s) == inside(store.root, source['path']) or inside(store.root, s) in inside(store.root, source['path']).parents for s in scope):
            raise EvolveError('KNOWLEDGE_COVERAGE', 'Survey source is outside declared scope')
    coverage = data.get('coverage')
    if not isinstance(coverage, list) or len(coverage) != len(PERSPECTIVES) or any(not isinstance(c, dict) for c in coverage) or {c.get('perspective') for c in coverage} != set(PERSPECTIVES):
        raise EvolveError('KNOWLEDGE_COVERAGE', 'Assess all eight knowledge perspectives')
    for item in coverage:
        if 'blocking' in item and not isinstance(item['blocking'], bool):
            raise EvolveError('KNOWLEDGE_COVERAGE', 'blocking must be an explicit boolean')
        if item.get('status') not in ('covered', 'partial', 'unknown', 'not_applicable'):
            raise EvolveError('KNOWLEDGE_COVERAGE', 'Coverage needs a bounded actual status')
        nonempty(item.get('basis'), 'coverage.basis')
        refs, questions = item.get('source_paths'), item.get('questions')
        if not isinstance(refs, list) or any(p not in {s['path'] for s in sources} for p in refs):
            raise EvolveError('KNOWLEDGE_COVERAGE', 'Coverage must refer to retained actual sources')
        if not isinstance(questions, list) or any(not isinstance(q, str) or not q.strip() for q in questions):
            raise EvolveError('KNOWLEDGE_COVERAGE', 'Keep explicit remaining questions')
        if item['status'] in ('partial', 'unknown') and not questions or item['status'] == 'covered' and not refs:
            raise EvolveError('KNOWLEDGE_COVERAGE', 'Unknowns need questions; covered perspectives need evidence')
    value = {'scope': scope, 'sources': sources, 'coverage': coverage}
    store.event(run_id, 'knowledge_survey_recorded', value)
    return {'outcome': 'knowledge_survey_recorded', **value, 'initial_delivery': 'pending'}


def survey(root, payload):
    from .knowledge_proposals import _record
    return _record(root, payload, 'survey', _survey, action='init', owner='evolve-init')


def _complete(store, data, run_id):
    view = catalog_view(store.connection, store.root)
    survey = view['survey']
    documents = [d for d in view['documents'] if d['active']]
    missing = []
    if not survey:
        missing.append('actual eight-perspective survey')
    for kind in ('project', 'codemap'):
        if not any(kind in d['roles'] and d['applicability'] == 'matching_local_bytes' for d in documents):
            missing.append(kind)
    for doc in documents:
        if doc['applicability'] != 'matching_local_bytes' or not document_verified(store.connection, doc):
            missing.append('actual document verification: ' + doc['path'])
    if survey:
        for item in survey['coverage']:
            if item.get('blocking') or item['perspective'] in ('purpose', 'domain', 'behavior', 'code', 'verification') and item['status'] == 'unknown':
                missing.append('essential perspective or blocking question: ' + item['perspective'])
        for source in survey['sources']:
            if current_digest(inside(store.root, source['path'])) != source['expected_digest']:
                missing.append('survey source changed: ' + source['path'])
    if missing:
        raise EvolveError('KNOWLEDGE_INCOMPLETE', '; '.join(missing), exit_code=3)
    value = {'scope': survey['scope'], 'survey_digest': digest(json.dumps(survey, sort_keys=True).encode()),
             'document_versions': [d['artifact_version_id'] for d in documents],
             'coverage': survey['coverage'], 'limitations': 'Completion is bounded to the declared scope; unknowns remain explicit.'}
    store.event(run_id, 'knowledge_initial_delivery_completed', value)
    return {'outcome': 'knowledge_initial_delivery_completed', **value}


def complete(root, payload):
    from .knowledge_proposals import _record
    return _record(root, payload, 'complete', _complete, action='init', owner='evolve-init')
