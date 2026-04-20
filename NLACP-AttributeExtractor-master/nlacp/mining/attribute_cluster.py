import json
import os
import numpy as np
from collections import Counter
from sklearn.cluster import DBSCAN
import spacy
from sklearn.neighbors import NearestNeighbors

# ===================================================================
# attribute_cluster.py  (nlacp/mining/)
# Module 2: Attribute Clustering (Alohaly et al. 2019)
#   GloVe Vectors + auto-tune eps + DBSCAN min_samples=2
# ===================================================================

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from nlacp.paths import POLICY_DATASET_PATH as DATASET_PATH, ATTRIBUTE_CLUSTERS_PATH as OUTPUT_PATH

# Dùng model lớn có GloVe vectors
from nlacp.utils.nlp_utils import get_spacy_model
nlp_vec = get_spacy_model()


def load_dataset():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_attribute_names(dataset):
    attributes = []
    for policy in dataset.get("policies", []):
        for attr in policy.get("attributes", []):
            name = attr.get("name") or attr.get("value") or ""
            if name:
                attributes.append(name.lower())
    return list(set(attributes))


def vectorize_attributes(attributes):
    vectors = []
    for attr in attributes:
        vec = nlp_vec(attr).vector   # 300d GloVe-like
        vectors.append(vec)
    return np.array(vectors)


def compute_auto_eps(X, min_pts=2):
    """
    Theo Alohaly 2019: vẽ k-distance graph, lấy trung bình khoảng cách
    đến k nearest neighbor để xác định eps phù hợp với dataset.
    """
    if X.shape[0] < min_pts:
        return 0.5   # fallback nếu quá ít điểm

    nbrs = NearestNeighbors(n_neighbors=min_pts, metric="euclidean").fit(X)
    distances, _ = nbrs.kneighbors(X)
    eps = float(np.mean(distances[:, -1]))
    import logging
    logging.debug(f"Auto-computed eps = {eps:.4f}")
    return eps


def run_dbscan(X):
    eps    = compute_auto_eps(X, min_pts=2)   # auto-tune
    model  = DBSCAN(eps=eps, min_samples=2, metric="euclidean")   # metric euclidean cho GloVe
    labels = model.fit_predict(X)
    return labels


def _compute_cluster_short_name(attr_list):
    stop = {"a", "an", "the", "of", "in", "at", "on", "by", "to", "for"}
    all_tokens = []
    for attr in attr_list:
        all_tokens.extend(str(attr).lower().split())
    filtered = [t for t in all_tokens if t not in stop and len(t) > 2]
    if not filtered:
        return attr_list[0] if attr_list else "cluster"
    return Counter(filtered).most_common(1)[0][0]


def build_clusters(attributes, labels):
    clusters = {}
    for attr, label in zip(attributes, labels):
        clusters.setdefault(label, []).append(attr)

    result = {"clusters": []}
    for label, attrs in clusters.items():
        result["clusters"].append({
            "cluster_id": int(label),
            "short_name": _compute_cluster_short_name(attrs),
            "attributes": attrs
        })
    return result


def save_clusters(data):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def main():
    print("\n" + "="*50)
    print("  Module 2: Attribute Clustering")
    print("  Word Vectors (GloVe/spaCy) + Auto-tune eps + DBSCAN (min_samples=2)")
    print("="*50 + "\n")

    dataset    = load_dataset()
    attributes = extract_attribute_names(dataset)

    print("Attributes found:", attributes)

    if not attributes:
        print("Khong co attributes nao de cluster.")
        return

    X      = vectorize_attributes(attributes)
    labels = run_dbscan(X)

    clusters = build_clusters(attributes, labels)
    save_clusters(clusters)

    print(f"\nClusters ({len(clusters['clusters'])} total):")
    for c in clusters["clusters"]:
        label = "OUTLIER" if c["cluster_id"] == -1 else f"Cluster {c['cluster_id']}"
        print(f"  {label}: {c['attributes']}")

    print("\nAttribute clusters saved.")


if __name__ == "__main__":
    main()