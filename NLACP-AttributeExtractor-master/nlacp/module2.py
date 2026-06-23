import uuid
from typing import List, Dict, Any
import math
from nlacp.utils.nlp_utils import get_spacy_model
import numpy as np


class PrincipalClusterBuilder:
    def build(self, subjects: List[Dict[str, Any]]) -> Dict[str, Any]:
        roles = []
        qualifiers = []
        subj_list = []
        for s in subjects or []:
            # accept subjects as dict or simple string; normalize to dict
            if isinstance(s, str):
                subj = {"id": s}
            elif isinstance(s, dict):
                subj = s
            else:
                # fallback to string representation
                subj = {"id": str(s)}
            subj_list.append(subj)
            role = subj.get("role")
            if role and role not in roles:
                roles.append(role)
            q = subj.get("qualifiers")
            if isinstance(q, dict):
                for k, v in q.items():
                    if v and k not in qualifiers:
                        qualifiers.append(k)
        return {"principal_cluster": {"subjects": subj_list, "roles": roles, "qualifiers": qualifiers}}


class ActionClusterBuilder:
    READ_VERBS = {"read", "view", "get", "list"}
    WRITE_VERBS = {"write", "update", "edit", "create"}
    ADMIN_VERBS = {"delete", "remove"}

    def build(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        ops = set()
        action_list = []
        negation = False
        for a in actions or []:
            # accept action as dict or simple string; normalize to dict with 'verb'
            if isinstance(a, str):
                act = {"verb": a}
            elif isinstance(a, dict):
                act = a
            else:
                act = {"verb": str(a)}
            verb = (act.get("verb") or "").lower()
            action_list.append(act)
            if act.get("negated"):
                negation = True
            if verb in self.READ_VERBS:
                ops.add("read-ops")
            elif verb in self.WRITE_VERBS:
                ops.add("write-ops")
            elif verb in self.ADMIN_VERBS:
                ops.add("admin-ops")
            else:
                ops.add("other-ops")
        return {"action_cluster": {"actions": action_list, "ops": list(ops), "negation": negation}}


class ResourceClusterBuilder:
    def build(self, resource: Any, relation_pairs: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        res_name = resource or ""
        scope = ""
        attributes = []
        # simple heuristics
        if isinstance(res_name, dict):
            res_label = res_name.get("label") or ""
            subject_filter = res_name.get("subject_filter")
            if subject_filter:
                scope = subject_filter
            attrs = res_name.get("attributes")
            if isinstance(attrs, list):
                attributes = attrs
            resource_str = res_label
        else:
            resource_str = str(res_name)
            if "own" in resource_str.lower():
                scope = "own"
            elif "department" in resource_str.lower():
                scope = "department"
            elif "all" in resource_str.lower():
                scope = "all"

        # look for possession relations to infer scope
        for r in relation_pairs or []:
            if not isinstance(r, dict):
                # skip or coerce simple list forms
                continue
            if r.get("rel_type") == "possession":
                scope = scope or r.get("value") or "own"

        return {"resource_cluster": {"resource": resource_str, "scope": scope, "attributes": attributes}}


class ContextClusterBuilder:
    def build(self, environments: List[Dict[str, Any]], context: List[Dict[str, Any]], relation_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        conditions = []
        envs = []
        relations = relation_pairs or []
        for c in context or []:
            cond_label = c.get("formal_expression") or c.get("trigger_phrase") or c
            conditions.append(cond_label)
        for e in environments or []:
            # env may contain systems list
            label = e.get("trigger_phrase") or e.get("id") or e
            envs.append(label)
        return {"context_cluster": {"conditions": conditions, "env": envs, "relations": relations}}


class CrossClusterLinker:
    def link(self, principal: Dict[str, Any], action: Dict[str, Any], resource: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # ensure relations are present in context cluster
        ctx = context.get("context_cluster", {})
        rels = ctx.get("relations", [])
        # attach subject_filter if relation indicates subject filtering
        # propagate possession info
        for r in rels:
            if not isinstance(r, dict):
                continue
            if r.get("rel_type") == "possession" and not resource.get("resource_cluster", {}).get("scope"):
                resource.get("resource_cluster", {})["scope"] = r.get("value") or "own"
        merged = {
            "principal_cluster": principal.get("principal_cluster", {}),
            "action_cluster": action.get("action_cluster", {}),
            "resource_cluster": resource.get("resource_cluster", {}),
            "context_cluster": ctx,
        }
        return merged


class ConstraintValidator:
    def validate(self, merged_clusters: Dict[str, Any]) -> Dict[str, Any]:
        warnings = []
        valid = True
        pc = merged_clusters.get("principal_cluster", {})
        ac = merged_clusters.get("action_cluster", {})
        rc = merged_clusters.get("resource_cluster", {})
        cc = merged_clusters.get("context_cluster", {})

        # Check Subject
        if not pc.get("subjects"):
            warnings.append("Missing subject(s)")
            valid = False
        # Check Action
        if not ac.get("actions"):
            warnings.append("Missing action(s)")
            valid = False
        # Check Resource
        if not rc.get("resource"):
            warnings.append("Missing resource")
            valid = False

        # Context empty warning
        if not cc.get("conditions") and not cc.get("env"):
            warnings.append("Context cluster is empty; policy may be too broad")

        # Negation checks
        if ac.get("negation") and not cc.get("conditions"):
            warnings.append("Negation without context constraint may be too broad")

        # resolve negation conflict: just flag if negation true but no qualifiers or role restrictions
        if ac.get("negation") and not pc.get("qualifiers") and not pc.get("roles"):
            warnings.append("Action negation with no principal restrictions")

        result = {"valid": valid, "warnings": warnings, "retry_reason": ("; ".join(warnings) if not valid else "")} 
        return result


class PolicyContextAssembler:
    def assemble(self, merged_clusters: Dict[str, Any], relation_pairs: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        # logical_ops default AND, switch to OR if exclusion relation exists
        logical_op = "AND"
        for r in relation_pairs or []:
            if not isinstance(r, dict):
                continue
            if (r.get("rel_type") or "").lower() in ("exclude", "exclusion") or (str(r.get("attribute") or "").lower() == "except"):
                logical_op = "OR"
                break

        # confidence: number of filled fields / 3
        def score(cluster: Dict[str, Any], fields: List[str]) -> float:
            if not cluster:
                return 0.0
            filled = 0
            for f in fields:
                v = cluster.get(f)
                if v:
                    filled += 1
            return round(filled / max(1, len(fields)), 3)

        principal = merged_clusters.get("principal_cluster", {})
        action = merged_clusters.get("action_cluster", {})
        resource = merged_clusters.get("resource_cluster", {})
        context = merged_clusters.get("context_cluster", {})

        confidence_scores = {
            "principal": score(principal, ["subjects", "roles", "qualifiers"]),
            "action": score(action, ["actions", "ops", "negation"]),
            "resource": score(resource, ["resource", "scope", "attributes"]),
            "context": score(context, ["conditions", "env", "relations"]),
        }

        policy_bundle = {
            "policy_id": str(uuid.uuid4()),
            "principal_cluster": principal,
            "action_cluster": action,
            "resource_cluster": resource,
            "context_cluster": context,
            "abac_policy": {"logical_ops": logical_op, "conditions": context.get("conditions", [])},
            "confidence_scores": confidence_scores,
            "warnings": [],
        }
        return policy_bundle


# Entry point
def run_module2(module1_output: Dict[str, Any]) -> Dict[str, Any]:
    # Dispatcher routes input to builders
    dispatcher_attempts = 0
    max_retries = 2

    principal_builder = PrincipalClusterBuilder()
    action_builder = ActionClusterBuilder()
    resource_builder = ResourceClusterBuilder()
    context_builder = ContextClusterBuilder()
    linker = CrossClusterLinker()
    validator = ConstraintValidator()
    assembler = PolicyContextAssembler()

    while dispatcher_attempts <= max_retries:
        principal = principal_builder.build(module1_output.get("subjects", []))
        action = action_builder.build(module1_output.get("actions", []))
        resource = resource_builder.build(module1_output.get("resource"), module1_output.get("relation_pairs", []))
        context = context_builder.build(module1_output.get("environments", []), module1_output.get("context", []), module1_output.get("relation_pairs", []))

        merged = linker.link(principal, action, resource, context)
        validation = validator.validate(merged)
        if validation.get("valid"):
            policy = assembler.assemble(merged, module1_output.get("relation_pairs", []))
            policy["warnings"] = validation.get("warnings", [])
            policy["valid"] = True
            return policy
        else:
            dispatcher_attempts += 1
            # if we've exhausted retries, assemble anyway and return with valid=false
            if dispatcher_attempts > max_retries:
                policy = assembler.assemble(merged, module1_output.get("relation_pairs", []))
                policy["warnings"] = validation.get("warnings", [])
                policy["valid"] = False
                policy["retry_reason"] = validation.get("retry_reason", "")
                return policy
            # else continue loop to retry (simple backoff could be added)

    # fallback
    return {"error": "unexpected_failure"}


def cluster_env_context(policy_bundles: List[Dict[str, Any]], method: str = "auto", eps: float = None, min_samples: int = None, n_clusters: int = None, distance_threshold: float = None) -> Dict[str, Any]:
    """Cluster environment and context strings across policy bundles using vector-distance clustering.

    Supports 'dbscan' and 'agglomerative' when sklearn is available; otherwise falls back
    to a greedy cosine-similarity grouping. Returns clusters and mapping text->cluster_id.
    eps is interpreted as cosine-distance threshold for DBSCAN (0..1 typical).
    """
    texts = []    
    for b in policy_bundles:
        ctx = b.get("context_cluster", {})
        for e in ctx.get("env", []) or []:
            t = str(e).strip()
            if t and t not in texts:
                texts.append(t)
        for c in ctx.get("conditions", []) or []:
            t = str(c).strip()
            if t and t not in texts:
                texts.append(t)

    if not texts:
        return {"clusters": [], "mapping": {}}

    n = len(texts)

    # autoset method
    if method == "auto":
        method = "dbscan" if n >= 3 else "agglomerative"

    # prepare for adaptive eps selection
    try:
        from sklearn.neighbors import NearestNeighbors
        use_sklearn_nn = True
    except Exception:
        use_sklearn_nn = False

    # Vectorize texts
    nlp = None
    try:
        nlp = get_spacy_model(fallback_to_none=True)
    except Exception:
        nlp = None

    vecs = []
    for t in texts:
        if nlp:
            vec = nlp(t).vector
        else:
            vec = np.array([float(sum(ord(ch) for ch in t) % 1000)])
        vecs.append(np.asarray(vec, dtype=float))

    # Build matrix and normalize
    maxlen = max(v.size for v in vecs)
    mat = np.zeros((len(vecs), maxlen), dtype=float)
    for i, v in enumerate(vecs):
        mat[i, : v.size] = v
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = mat / norms

    # adaptive eps/min_samples when not provided
    if eps is None:
        if n <= 1:
            eps = 0.5
        else:
            try:
                if use_sklearn_nn:
                    from sklearn.neighbors import NearestNeighbors
                    nn = NearestNeighbors(n_neighbors=min(3, n), metric="cosine").fit(normed)
                    distances, _ = nn.kneighbors(normed)
                    candidate = float(np.median(distances[:, -1]))
                    eps = max(0.05, min(0.9, candidate * 1.2))
                else:
                    sims = normed.dot(normed.T)
                    np.fill_diagonal(sims, -1.0)
                    nearest_sim = sims.max(axis=1)
                    dists = 1.0 - nearest_sim
                    candidate = float(np.median(dists))
                    eps = max(0.05, min(0.9, candidate * 1.2))
            except Exception:
                eps = 0.3

    if min_samples is None:
        min_samples = 1 if n < 5 else max(2, int(math.log(max(2, n))))

    labels = None
    try:
        from sklearn.cluster import DBSCAN, AgglomerativeClustering
        if method == "dbscan":
            # sklearn DBSCAN with cosine metric: eps is cosine distance threshold
            clustering = DBSCAN(eps=eps, min_samples=max(1, min_samples), metric="cosine")             
            labels = clustering.fit_predict(normed)
        else:
            if n_clusters is not None:
                clustering = AgglomerativeClustering(n_clusters=n_clusters, affinity="cosine", linkage="average")
                labels = clustering.fit_predict(normed)
            else:
                if distance_threshold is None:
                    # choose heuristic n_clusters based on dataset size
                    heuristic_k = max(1, int(math.sqrt(n)))
                    clustering = AgglomerativeClustering(n_clusters=heuristic_k, affinity="cosine", linkage="average")
                else:
                    clustering = AgglomerativeClustering(distance_threshold=distance_threshold, n_clusters=None, affinity="cosine", linkage="average")
                labels = clustering.fit_predict(normed)
    except Exception:
        # greedy fallback: group by cosine similarity using threshold derived from eps
        labels = [-1] * len(texts)
        cid = 0
        for i in range(len(texts)):
            if labels[i] != -1:
                continue
            labels[i] = cid
            vi = normed[i]
            for j in range(i + 1, len(texts)):
                if labels[j] != -1:
                    continue
                vj = normed[j]
                sim = float(np.dot(vi, vj))
                # interpret eps as allowable cosine distance
                if sim >= (1.0 - eps):
                    labels[j] = cid
            cid += 1

    # build clusters
    clusters_map = {}
    for idx, lab in enumerate(labels):
        clusters_map.setdefault(int(lab), []).append(texts[idx])

    clusters = []
    for cid, members in sorted(clusters_map.items()):
        lower_join = " ".join(members).lower()
        temporal_kw = {"hour", "time", "during", "between", "pm", "am", "business", "working", "day", "night", "shift", "semester"}
        spatial_kw = {"room", "building", "campus", "department", "office", "facility", "floor", "zone", "lab", "vpn", "network", "internal"}
        typ = "other"
        if any(k in lower_join for k in temporal_kw):
            typ = "temporal"
        elif any(k in lower_join for k in spatial_kw):
            typ = "spatial"
        short = _compute_short_name(members)
        clusters.append({"cluster_id": int(cid), "type": typ, "label": short, "members": members})

    mapping = {texts[i]: int(labels[i]) for i in range(len(texts))}
    return {"clusters": clusters, "mapping": mapping}


def _compute_short_name(attr_list):
    stop = {"a", "an", "the", "of", "in", "at", "on", "by", "to", "for"}
    from collections import Counter
    tokens = []
    for attr in attr_list:
        for t in str(attr).lower().split():
            if t not in stop and len(t) > 2:
                tokens.append(t)
    if not tokens:
        return (attr_list[0] if attr_list else "env").replace(" ", "_")
    return Counter(tokens).most_common(1)[0][0]


def aggregate_bundles_by_env(policy_bundles: List[Dict[str, Any]], env_clusters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Aggregate principal/action/resource across policy_bundles grouped by env_cluster id.

    Returns list of {'env_cluster_id': int, 'aggregate_bundle': {...}}
    """
    mapping = env_clusters.get("mapping", {})
    clusters = {}

    def add_unique(lst, item):
        if item not in lst:
            lst.append(item)

    for b in policy_bundles:
        ctx = b.get("context_cluster", {})
        env_texts = ctx.get("env", []) or []
        # determine cluster ids for this bundle (could be multiple)
        cids = []
        for t in env_texts:
            key = t if isinstance(t, str) else str(t)
            cid = mapping.get(key)
            if cid is None:
                continue
            if cid not in cids:
                cids.append(cid)

        # if no env cluster found, assign -1
        if not cids:
            cids = [-1]

        for cid in cids:
            entry = clusters.setdefault(cid, {
                "env_cluster_id": cid,
                "principal": {"subjects": [], "roles": [], "qualifiers": [], "namespaces": [], "count": 0, "examples": []},
                "action": {"verbs": [], "ops": [], "negation_count": 0, "logical_ops": {}, "examples": []},
                "resource": {"labels": [], "scopes": [], "attributes": [], "namespaces": [], "count": 0, "examples": []},
                "context": {"conditions": [], "relation_pairs": [], "examples": []},
                "metadata": {"policy_ids": [], "confidence_scores": [], "warnings": [], "valid_count": 0, "total_count": 0}
            })

            # principal
            pc = b.get("principal_cluster", {})
            for s in pc.get("subjects", []) or []:
                add_unique(entry["principal"]["subjects"], s)
                ns = s.get("namespace") if isinstance(s, dict) else None
                if ns:
                    add_unique(entry["principal"]["namespaces"], ns)
                role = s.get("role") if isinstance(s, dict) else None
                if role:
                    add_unique(entry["principal"]["roles"], role)
                q = s.get("qualifiers") if isinstance(s, dict) else None
                if isinstance(q, dict):
                    for k in q.keys():
                        add_unique(entry["principal"]["qualifiers"], k)

            entry["principal"]["count"] += 1
            if len(entry["principal"]["examples"]) < 3:
                entry["principal"]["examples"].append(pc.get("subjects", [])[:1])

            # action
            ac = b.get("action_cluster", {})
            for a in ac.get("actions", []) or []:
                verb = (a.get("verb") if isinstance(a, dict) else str(a)) or None
                if verb:
                    add_unique(entry["action"]["verbs"], verb)
                if a.get("negated"):
                    entry["action"]["negation_count"] += 1
            for op in ac.get("ops", []) or []:
                add_unique(entry["action"]["ops"], op)
            lop = ac.get("logical_op") or None
            if lop:
                entry["action"]["logical_ops"][lop] = entry["action"]["logical_ops"].get(lop, 0) + 1
            if len(entry["action"]["examples"]) < 3:
                entry["action"]["examples"].append(ac.get("actions", [])[:1])

            # resource
            rc = b.get("resource_cluster", {})
            res_label = rc.get("resource")
            if res_label:
                add_unique(entry["resource"]["labels"], res_label)
            scope = rc.get("scope")
            if scope:
                add_unique(entry["resource"]["scopes"], scope)
            for at in rc.get("attributes", []) or []:
                add_unique(entry["resource"]["attributes"], at)
            ns = rc.get("namespace")
            if ns:
                add_unique(entry["resource"]["namespaces"], ns)
            entry["resource"]["count"] += 1
            if len(entry["resource"]["examples"]) < 3:
                entry["resource"]["examples"].append(rc)

            # context
            cc = b.get("context_cluster", {})
            for cond in cc.get("conditions", []) or []:
                add_unique(entry["context"]["conditions"], cond)
            for rp in cc.get("relations", []) or []:
                # store normalized relation dicts
                if isinstance(rp, dict):
                    entry["context"]["relation_pairs"].append(rp)
                else:
                    entry["context"]["relation_pairs"].append({"raw": str(rp)})
            if len(entry["context"]["examples"]) < 3 and cc.get("conditions"):
                entry["context"]["examples"].append(list(cc.get("conditions"))[:1])

            # metadata
            meta = entry["metadata"]
            pid = b.get("source_policy_id") or b.get("policy_id")
            if pid and len(meta["policy_ids"]) < 20:
                meta["policy_ids"].append(pid)
            cs = b.get("confidence_scores") or {}
            if cs:
                meta["confidence_scores"].append(cs)
            for w in b.get("warnings", []) or []:
                add_unique(meta["warnings"], w)
            if b.get("valid"):
                meta["valid_count"] += 1
            meta["total_count"] += 1

    # finalize: normalize lists, remove duplicates, cap sizes, and aggregate confidence
    out = []
    import statistics
    import json as _json
    for cid, ent in clusters.items():
        # compact principal.subjects by (namespace, role, ref_tokens)
        seen_subj = set()
        compact_subjects = []
        for s in ent["principal"]["subjects"]:
            try:
                ns = s.get("namespace") if isinstance(s, dict) else None
                role = s.get("role") if isinstance(s, dict) else None
                refs = tuple(s.get("ref_tokens") or []) if isinstance(s, dict) else (str(s),)
                key = (ns, role, refs)
            except Exception:
                key = (str(s),)
            if key in seen_subj:
                continue
            seen_subj.add(key)
            compact_subjects.append(s)
        ent["principal"]["subjects"] = compact_subjects[:50]

        # ensure principal lists are unique and limited
        ent["principal"]["roles"] = list(dict.fromkeys(ent["principal"]["roles"]))[:20]
        ent["principal"]["qualifiers"] = list(dict.fromkeys(ent["principal"]["qualifiers"]))[:20]
        ent["principal"]["namespaces"] = list(dict.fromkeys(ent["principal"]["namespaces"]))[:20]

        # actions: unique verbs/ops and limit examples
        ent["action"]["verbs"] = list(dict.fromkeys(ent["action"]["verbs"]))[:20]
        ent["action"]["ops"] = list(dict.fromkeys(ent["action"]["ops"]))[:20]
        ent["action"]["examples"] = ent["action"]["examples"][:3]

        # resources: unique
        ent["resource"]["labels"] = list(dict.fromkeys(ent["resource"]["labels"]))[:20]
        ent["resource"]["scopes"] = list(dict.fromkeys(ent["resource"]["scopes"]))[:10]
        ent["resource"]["attributes"] = list(dict.fromkeys(ent["resource"]["attributes"]))[:50]
        ent["resource"]["namespaces"] = list(dict.fromkeys(ent["resource"]["namespaces"]))[:20]
        ent["resource"]["examples"] = ent["resource"]["examples"][:3]

        # context conditions unique and limited
        ent["context"]["conditions"] = list(dict.fromkeys(ent["context"]["conditions"]))[:50]
        # dedupe relation_pairs by JSON string
        seen_rp = set()
        clean_rps = []
        for rp in ent["context"]["relation_pairs"]:
            try:
                key = _json.dumps(rp, sort_keys=True)
            except Exception:
                key = str(rp)
            if key in seen_rp:
                continue
            seen_rp.add(key)
            clean_rps.append(rp)
        ent["context"]["relation_pairs"] = clean_rps[:50]

        meta = ent["metadata"]
        # aggregate confidence: compute mean per key if present
        agg_conf = {}
        if meta["confidence_scores"]:
            keys = set().union(*(cs.keys() for cs in meta["confidence_scores"]))
            for k in keys:
                vals = [cs.get(k, 0.0) for cs in meta["confidence_scores"]]
                try:
                    agg_conf[k] = round(float(statistics.mean(vals)), 3)
                except Exception:
                    agg_conf[k] = None
        meta["confidence_scores"] = agg_conf
        # ensure unique policy_ids and warnings, cap sizes
        meta["policy_ids"] = list(dict.fromkeys(meta.get("policy_ids", [])))[:50]
        meta["warnings"] = list(dict.fromkeys(meta.get("warnings", [])))[:20]

        out.append({"env_cluster_id": cid, "aggregate_bundle": ent})

    return out
