"""
nlacp/paths.py — Centralized path definitions for the project.
All modules should import paths from here to avoid hardcoding.
"""
import os

# nlacp/ -> project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dataset
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
RELATION_CANDIDATE_PATH = os.path.join(DATASET_DIR, "relation_candidate.json")

# Outputs
POLICY_DATASET_PATH      = os.path.join(BASE_DIR, "outputs", "policies", "policy_dataset.json")
POLICY_DATASET_GOLD_PATH = os.path.join(BASE_DIR, "outputs", "policies", "policy_dataset_gold.json")
ATTRIBUTE_CLUSTERS_PATH = os.path.join(BASE_DIR, "outputs", "clusters",  "attribute_clusters.json")
NAMESPACE_HIERARCHY_PATH = os.path.join(BASE_DIR, "outputs", "hierarchy", "namespace_hierarchy.json")
POLICY_BUNDLES_PATH = os.path.join(BASE_DIR, "outputs", "clusters", "policy_bundles.json")
ENV_CONTEXT_CLUSTERS_PATH = os.path.join(BASE_DIR, "outputs", "clusters", "env_context_clusters.json")
AGGREGATED_BUNDLES_PATH = os.path.join(BASE_DIR, "outputs", "clusters", "aggregate_policy_bundles.json")

# Namespace Constants
NS_ENV_TIME      = "env:time"
NS_ENV_LOC       = "env:location"
