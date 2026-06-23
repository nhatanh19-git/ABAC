import json
from nlacp.pipeline.pipeline_v2 import parse_acp_sentence

tests = [
    'A teaching assistant reviews submissions at night.',
    'A student checks application status on the campus portal.',
    'An admissions officer reviews applications in the admissions office.',
    'A teaching assistant modifies course grades in the lab.',
    'An instructor updates a gradebook during the semester.',
]

for s in tests:
    policy = parse_acp_sentence(s)
    print(f'INPUT: {s}')
    if not policy:
        print('  parse failed')
        print()
        continue

    # Subjects: show role if available, otherwise entity type or full dict
    subj_list = []
    for sub in policy.subjects:
        try:
            subj_list.append(sub.role or str(sub.entity_type) or sub.model_dump())
        except Exception:
            subj_list.append(str(sub))

    # Actions: verbs
    actions = [a.verb for a in policy.actions]

    # Resource: label or entity type
    res = policy.resource
    res_label = getattr(res, 'label', None) or str(getattr(res, 'entity_type', None))

    envs = policy.environments or []
    if envs:
        env_list = [ (e.trigger_phrase or e.id or str(e.env_type)) for e in envs ]
    else:
        env_list = []

    print(f'  subjects: {subj_list}')
    print(f'  actions : {actions}')
    print(f'  resource: {res_label}')
    print(f'  env     : {env_list}')
    print()
