"""Bounded data context and relationship claims reuse ordinary analysis facts."""
from datetime import date
import re

from .errors import EvolveError
from .workspace import current_digest, inside


def nonempty_strings(value):
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def dates(value):
    if not nonempty_strings(value):
        return False
    try:
        return all(date.fromisoformat(item).isoformat() == item for item in value)
    except ValueError:
        return False


def validate_material(analysis, sources):
    context = analysis.get('data_context')
    if context is not None:
        if (not isinstance(context, dict) or not nonempty_strings(context.get('objects'))
                or not nonempty_strings(context.get('source_ids'))
                or not set(context['source_ids']).issubset(sources)):
            raise EvolveError('DATA_CONTEXT', 'Data context names actual objects and saved source identities')
        limits = context.get('limitations')
        if not isinstance(limits, list) or any(not isinstance(item, str) or not item.strip() for item in limits):
            raise EvolveError('DATA_CONTEXT', 'Data context keeps explicit limitations')
        for key in ('business_dates', 'grain', 'definitions'):
            if key not in context:
                raise EvolveError('DATA_CONTEXT', 'Relevant data fields are explicit, with null for unknown values')
        if context['business_dates'] is not None and not dates(context['business_dates']):
            raise EvolveError('DATA_CONTEXT', 'Business dates use actual YYYY-MM-DD values, not observation timestamps')
        if context['grain'] is not None and (not isinstance(context['grain'], str) or not context['grain'].strip()):
            raise EvolveError('DATA_CONTEXT', 'Data grain must be stated or explicitly unknown')
        if context['definitions'] is not None and not nonempty_strings(context['definitions']):
            raise EvolveError('DATA_CONTEXT', 'Metric definitions must be stated or explicitly unknown')
        if any(context[key] is None for key in ('business_dates', 'grain', 'definitions')):
            if not limits or analysis['answer_status'] == 'answered':
                raise EvolveError('DATA_CONTEXT', 'Unknown data fields require a bounded answer and limitations')
        covered_objects, covered_pairs = set(), set()
        for source_id in context['source_ids']:
            scope = sources[source_id].get('data_scope')
            if (not isinstance(scope, dict) or not nonempty_strings(scope.get('objects'))
                    or 'business_dates' not in scope
                    or scope['business_dates'] is not None and not dates(scope['business_dates'])):
                raise EvolveError('DATA_SOURCE_SCOPE', 'Data evidence identifies its actual objects and supported business dates')
            covered_objects.update(scope['objects'])
            covered_pairs.update((obj, day) for obj in scope['objects'] for day in (scope['business_dates'] or []))
        if (not set(context['objects']).issubset(covered_objects)
                or any((obj, day) not in covered_pairs for obj in context['objects'] for day in (context['business_dates'] or []))):
            raise EvolveError('DATA_SOURCE_SCOPE', 'Expanded objects or dates need matching observations; old scope is not current evidence')
    relationships = analysis.get('relationships', [])
    if not isinstance(relationships, list):
        raise EvolveError('RELATIONSHIP', 'Relationships are an explicit array of bounded observations')
    seen = set()
    for item in relationships:
        if (not isinstance(item, dict) or not re.fullmatch(r'R[1-9][0-9]*', str(item.get('local_key')))
                or item['local_key'] in seen
                or any(not isinstance(item.get(key), str) or not item[key].strip() for key in ('source', 'target', 'transformation'))
                or item.get('certainty') not in ('observed', 'inferred', 'unknown')
                or not nonempty_strings(item.get('sources')) or not set(item['sources']).issubset(sources)
                or not isinstance(item.get('limitations'), list)
                or any(not isinstance(limit, str) or not limit.strip() for limit in item['limitations'])):
            raise EvolveError('RELATIONSHIP', 'Each relation identifies endpoints, transformation, certainty, real sources and limitations')
        if item['certainty'] == 'observed':
            if not any(sources[key]['kind'] in ('file', 'observation') and sources[key].get('observed_at') is not None for key in item['sources']):
                raise EvolveError('RELATIONSHIP', 'Observed relationships need retained dated evidence')
        elif not item['limitations']:
            raise EvolveError('RELATIONSHIP', 'Inferred or unknown relationships retain their actual uncertainty')
        seen.add(item['local_key'])


def source_applicability(root, sources):
    observations = []
    for source in sources:
        item = {'source_id': source['id'], 'observed_at': source.get('observed_at'),
                'data_scope': source.get('data_scope'), 'external_data': 'not_observed'}
        if source['kind'] == 'file' and root is not None:
            try:
                current = current_digest(inside(root, source['path']))
                item.update(status='matching_local_bytes' if current == source['expected_digest'] else 'local_bytes_changed',
                            current_digest=current)
            except (EvolveError, OSError) as error:
                item.update(status='unavailable', reason=getattr(error, 'code', type(error).__name__))
        else:
            item['status'] = 'not_reobserved'
        observations.append(item)
    return observations
