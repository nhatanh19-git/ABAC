#!/usr/bin/env python
"""Run Module 2 (policy bundling) for the entire policy dataset with one command.

Usage:
    python scripts/run_module2.py
    python scripts/run_module2.py --no-save   # run but don't write bundles file
"""
import json
import os
import argparse
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from nlacp.paths import POLICY_DATASET_PATH, POLICY_BUNDLES_PATH, ENV_CONTEXT_CLUSTERS_PATH, AGGREGATED_BUNDLES_PATH
from nlacp.module2 import run_module2, cluster_env_context, aggregate_bundles_by_env


def main(save: bool = True, cluster_opts: dict = None):
    if not os.path.exists(POLICY_DATASET_PATH):
        print(f"[ERROR] {POLICY_DATASET_PATH} not found.")
        return 1

    with open(POLICY_DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    def _normalize_relation_pairs(rplist):
        if not rplist:
            return []
        out = []
        for r in rplist:
            if isinstance(r, dict):
                out.append(r)
            elif isinstance(r, (list, tuple)):
                # common pattern: [attribute, value]
                if len(r) == 2:
                    out.append({"attribute": r[0], "value": r[1], "rel_type": "unknown"})
                else:
                    out.append({"raw": " ".join(map(str, r)), "rel_type": "unknown"})
            else:
                out.append({"raw": str(r), "rel_type": "unknown"})
        return out

    bundles = []
    for policy in data.get("policies", []):
        raw_rel = policy.get("relation_pairs") or []
        rels = _normalize_relation_pairs(raw_rel)
        module1_output = {
            "subjects": policy.get("subjects") or policy.get("subject") or [],
            "actions": policy.get("actions") or policy.get("action") or [],
            "resource": policy.get("resource") or {},
            "environments": policy.get("environments") or policy.get("environment") or [],
            "context": policy.get("context") or [],
            "relation_pairs": rels
        }
        bundle = run_module2(module1_output)
        bundle["source_policy_id"] = policy.get("id")
        bundles.append(bundle)

    if save:
        os.makedirs(os.path.dirname(POLICY_BUNDLES_PATH), exist_ok=True)
        with open(POLICY_BUNDLES_PATH, "w", encoding="utf-8") as f:
            json.dump({"policy_bundles": bundles}, f, indent=4, ensure_ascii=False)
        print(f"Saved {len(bundles)} policy bundles to {POLICY_BUNDLES_PATH}")
        # cluster env/context across bundles and save
        try:
            clustering = cluster_env_context(bundles, **(cluster_opts or {}))
            os.makedirs(os.path.dirname(ENV_CONTEXT_CLUSTERS_PATH), exist_ok=True)
            with open(ENV_CONTEXT_CLUSTERS_PATH, "w", encoding="utf-8") as f:
                json.dump(clustering, f, indent=4, ensure_ascii=False)
            print(f"Saved env/context clusters to {ENV_CONTEXT_CLUSTERS_PATH}")
            # annotate bundles with env cluster ids for traceability
            mapping = clustering.get("mapping", {})
            for b in bundles:
                ctx = b.get("context_cluster", {})
                envs = ctx.get("env", []) or []
                env_cluster_ids = [mapping.get(str(e), None) for e in envs]
                b["context_cluster"]["env_cluster_ids"] = env_cluster_ids
            # re-save bundles with annotations
            with open(POLICY_BUNDLES_PATH, "w", encoding="utf-8") as f:
                json.dump({"policy_bundles": bundles}, f, indent=4, ensure_ascii=False)
            # build aggregated bundles grouped by env_cluster
            try:
                aggregated = aggregate_bundles_by_env(bundles, clustering)
                with open(AGGREGATED_BUNDLES_PATH, 'w', encoding='utf-8') as f:
                    json.dump({"aggregated_bundles": aggregated}, f, indent=4, ensure_ascii=False)
                print(f"Saved aggregated bundles to {AGGREGATED_BUNDLES_PATH}")
            except Exception as e:
                print(f"[WARN] aggregation failed: {e}")
        except Exception as e:
            print(f"[WARN] env/context clustering failed: {e}")
    else:
        print(f"Processed {len(bundles)} policies (not saved).")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-save", action="store_true", help="Do not save bundles file")
    parser.add_argument("--method", type=str, default=None, help="Clustering method: auto|dbscan|agglomerative")
    parser.add_argument("--eps", type=float, default=None, help="DBSCAN eps (cosine distance)")
    parser.add_argument("--min-samples", type=int, default=None, help="DBSCAN min_samples")
    parser.add_argument("--n-clusters", type=int, default=None, help="Agglomerative n_clusters")
    parser.add_argument("--distance-threshold", type=float, default=None, help="Agglomerative distance_threshold")
    args = parser.parse_args()
    cluster_opts = {}
    if args.method is not None:
        cluster_opts["method"] = args.method
    if args.eps is not None:
        cluster_opts["eps"] = args.eps
    if args.min_samples is not None:
        cluster_opts["min_samples"] = args.min_samples
    if args.n_clusters is not None:
        cluster_opts["n_clusters"] = args.n_clusters
    if args.distance_threshold is not None:
        cluster_opts["distance_threshold"] = args.distance_threshold

    raise SystemExit(main(save=not args.no_save, cluster_opts=cluster_opts))
