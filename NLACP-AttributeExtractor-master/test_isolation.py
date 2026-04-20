import json
from nlacp.pipeline.pipeline import process_sentence

tests = [
    'A teaching assistant reviews submissions at night.',
    'A student checks application status on the campus portal.',
    'An admissions officer reviews applications in the admissions office.',
    'A teaching assistant modifies course grades in the lab.',
    'An instructor updates a gradebook during the semester.',
]
for s in tests:
    res = process_sentence(s)
    print(f'INPUT: {s}')
    print(f'  subject : {res["subject"]}')
    print(f'  actions : {res["actions"]}')
    print(f'  object  : {res["object"]}')
    env = res.get("environment", [])
    if env:
        print(f'  env     : {[e["full_value"] for e in env]}')
    else:
        print(f'  env     : []')
    print()
