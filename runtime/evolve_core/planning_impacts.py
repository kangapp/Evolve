"""Show producer/input intersections without inferring semantic dependencies."""
import json

from .errors import EvolveError
from .workspace import inside


def targets(root, names):
    return {inside(root, name).resolve().relative_to(root).as_posix() for name in names}


def observe(root, tasks, resolutions=None):
    by_key = {task['local_key']: task for task in tasks}
    ancestors = {}
    def upstream(key):
        if key not in ancestors:
            ancestors[key] = set()
            for dependency in by_key[key].get('dependencies', []):
                parent = dependency['upstream_task']
                ancestors[key].add(parent)
                ancestors[key].update(upstream(parent))
        return ancestors[key]
    resolutions = [] if resolutions is None else resolutions
    if not isinstance(resolutions, list) or any(not isinstance(item, dict) for item in resolutions):
        raise EvolveError('PLAN_IMPACT', 'impact_resolutions must be an explicit list')
    decisions = {}
    for item in resolutions:
        if (item.get('decision') != 'independent' or not isinstance(item.get('basis'), str) or not item['basis'].strip()
                or not all(isinstance(item.get(field), str) and item[field] for field in ('producer', 'consumer'))
                or not isinstance(item.get('paths'), list) or not item['paths']
                or any(not isinstance(name, str) for name in item['paths'])):
            raise EvolveError('PLAN_IMPACT', 'An independent-impact decision requires exact paths and its actual semantic basis')
        key = (item.get('producer'), item.get('consumer'), tuple(sorted(targets(root, item['paths']))))
        if key in decisions:
            raise EvolveError('PLAN_IMPACT', 'Impact decisions must not repeat')
        decisions[key] = item
    result, used = [], set()
    for producer in tasks:
        outputs = targets(root, producer['scope'])
        for consumer in tasks:
            if producer['local_key'] == consumer['local_key']:
                continue
            inputs = targets(root, [*consumer['context_paths'], *consumer.get('preservation_inputs', [])])
            paths = sorted(outputs & inputs)
            if not paths:
                continue
            key = (producer['local_key'], consumer['local_key'], tuple(paths))
            ordered = producer['local_key'] in upstream(consumer['local_key'])
            decision = decisions.get(key)
            if decision:
                used.add(key)
            result.append({'producer': producer['local_key'], 'consumer': consumer['local_key'], 'paths': paths,
                'relationship': 'producer_precedes_consumer' if ordered else
                    'consumer_precedes_producer' if consumer['local_key'] in upstream(producer['local_key']) else 'unordered',
                'resolution': 'declared_dependency' if ordered else 'independent' if decision else 'review_required',
                'basis': decision['basis'] if decision else 'The producer may change a declared consumer input.',
                'requires_review': not ordered and not decision, 'automatic_dependency': False})
    if used != set(decisions):
        raise EvolveError('PLAN_IMPACT', 'Impact decisions must identify actual producer/input intersections')
    return result


def workspace_observations(connection, root, scope, inputs, *, change_id=None):
    outputs, inputs = targets(root, scope), targets(root, inputs)
    result = []
    for row in connection.execute('SELECT t.*,c.title FROM tasks t JOIN changes c ON c.id=t.change_id '
            "WHERE t.revision_id=c.current_revision AND c.state NOT IN ('archived','cancelled') ORDER BY t.rowid"):
        if row['change_id'] == change_id:
            continue
        definition = json.loads(row['definition_json'])
        other_inputs = targets(root, [*definition.get('context', {}), *definition.get('preservation_inputs', []),
                                     *definition.get('dependency_inputs', [])])
        paths = sorted((outputs & other_inputs) | (inputs & targets(root, definition['scope'])))
        if paths:
            result.append({'change_id': row['change_id'], 'title': row['title'], 'task_id': row['id'],
                'task_key': definition['local_key'], 'paths': paths, 'requires_semantic_review': True,
                'automatic_dependency': False, 'basis': 'An active work item produces or consumes an intersecting declared input.'})
    return result
