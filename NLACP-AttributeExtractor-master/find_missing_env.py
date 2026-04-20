import json

with open('outputs/policies/policy_dataset_gold.json', encoding='utf-8') as f:
    gold_raw = json.load(f)

with open('outputs/policies/policy_dataset.json', encoding='utf-8') as f:
    data_raw = json.load(f)

gold_list = gold_raw if isinstance(gold_raw, list) else gold_raw.get('policies', [])
data_list = data_raw if isinstance(data_raw, list) else data_raw.get('policies', [])

gold_by_id = {p['id']: p for p in gold_list if isinstance(p, dict)}
data_by_id = {p['id']: p for p in data_list if isinstance(p, dict)}

missing = []
for pid, gp in sorted(gold_by_id.items()):
    g_env = gp.get('environment', [])
    dp = data_by_id.get(pid, {})
    d_env = dp.get('environment', [])
    if g_env and not d_env:
        missing.append((pid, gp['sentence'], g_env))

print(f'Total missing environment: {len(missing)} sentences\n')
for pid, sent, envs in missing[:30]:
    phrases = [e.get('full_value') or e.get('phrase', '') for e in envs]
    print(f'[{pid}] {sent}')
    print(f'  GOLD: {phrases}')
    print()
