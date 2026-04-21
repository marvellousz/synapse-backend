"""
Synapse Search Benchmarks
Generates 4 charts: Precision Comparison, Latency Scaling, Hybrid Alpha, Retrieval Window K.
"""
import asyncio, json, time, random, hashlib, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.services.extraction.embedding import generate_embedding, cosine_similarity

# ── Synthetic knowledge base ──
KNOWLEDGE_BASE = [
    {"title": "Machine Learning Basics", "text": "Machine learning is a subset of artificial intelligence that enables systems to learn from data. Supervised learning uses labeled datasets to train algorithms. Common algorithms include decision trees, random forests, and neural networks.", "type": "text", "tags": ["ml", "ai"]},
    {"title": "Neural Network Architecture", "text": "Deep neural networks consist of input, hidden, and output layers. Backpropagation adjusts weights during training. Convolutional neural networks are specialized for image recognition tasks.", "type": "text", "tags": ["ml", "neural-nets"]},
    {"title": "Python Programming Guide", "text": "Python is a high-level programming language known for readability. It supports object-oriented, functional, and procedural paradigms. Popular libraries include NumPy, Pandas, and scikit-learn for data science.", "type": "text", "tags": ["python", "programming"]},
    {"title": "Database Design Principles", "text": "Relational databases use SQL for querying structured data. Normalization reduces data redundancy. PostgreSQL supports advanced features like JSON columns and full-text search.", "type": "text", "tags": ["database", "sql"]},
    {"title": "REST API Best Practices", "text": "RESTful APIs use HTTP methods like GET, POST, PUT, DELETE. Authentication via JWT tokens ensures secure access. Rate limiting prevents abuse and ensures fair usage.", "type": "text", "tags": ["api", "web"]},
    {"title": "Cloud Computing Overview", "text": "Cloud computing provides on-demand computing resources. AWS, Azure, and GCP are major providers. Serverless architectures eliminate server management overhead.", "type": "text", "tags": ["cloud", "infrastructure"]},
    {"title": "Data Structures and Algorithms", "text": "Binary search trees enable O(log n) lookup. Hash tables provide O(1) average access time. Graph algorithms like Dijkstra find shortest paths in networks.", "type": "text", "tags": ["algorithms", "cs"]},
    {"title": "Cybersecurity Fundamentals", "text": "Encryption protects data in transit and at rest. Two-factor authentication adds security layers. OWASP Top 10 lists common web application vulnerabilities.", "type": "text", "tags": ["security"]},
    {"title": "Docker and Containerization", "text": "Docker containers package applications with dependencies. Kubernetes orchestrates container deployment at scale. Docker Compose defines multi-container applications.", "type": "text", "tags": ["devops", "docker"]},
    {"title": "React Frontend Development", "text": "React uses a virtual DOM for efficient UI updates. Components are reusable building blocks. Hooks like useState and useEffect manage state and side effects.", "type": "text", "tags": ["react", "frontend"]},
    {"title": "Natural Language Processing", "text": "NLP enables machines to understand human language. Transformers revolutionized text processing. BERT and GPT are popular pre-trained language models for various NLP tasks.", "type": "text", "tags": ["nlp", "ai"]},
    {"title": "Git Version Control", "text": "Git tracks changes in source code during development. Branching strategies like GitFlow organize team workflows. Pull requests enable code review before merging.", "type": "text", "tags": ["git", "devops"]},
    {"title": "Agile Project Management", "text": "Scrum uses sprints for iterative development. Kanban boards visualize workflow stages. Daily standups keep teams aligned on progress and blockers.", "type": "text", "tags": ["agile", "management"]},
    {"title": "Computer Vision Applications", "text": "Object detection identifies items in images using bounding boxes. Image segmentation classifies each pixel. YOLO and Faster R-CNN are popular detection architectures.", "type": "text", "tags": ["cv", "ai"]},
    {"title": "Blockchain Technology", "text": "Blockchain is a distributed ledger ensuring transparency. Smart contracts automate agreements on Ethereum. Consensus mechanisms like proof-of-stake validate transactions.", "type": "text", "tags": ["blockchain"]},
    {"title": "Statistics for Data Science", "text": "Hypothesis testing determines statistical significance. Regression analysis models relationships between variables. Bayesian inference updates probability with new evidence.", "type": "text", "tags": ["statistics", "data-science"]},
    {"title": "Linux System Administration", "text": "Linux uses a hierarchical file system starting from root. Package managers like apt and yum install software. Cron jobs schedule automated tasks on servers.", "type": "text", "tags": ["linux", "sysadmin"]},
    {"title": "Mobile App Development", "text": "React Native enables cross-platform mobile development. Flutter uses Dart for building native interfaces. Progressive web apps combine web and mobile experiences.", "type": "text", "tags": ["mobile", "development"]},
    {"title": "Quantum Computing Basics", "text": "Qubits can exist in superposition of states. Quantum entanglement enables instantaneous correlation. Quantum algorithms like Shor's can factor large numbers exponentially faster.", "type": "text", "tags": ["quantum", "computing"]},
    {"title": "GraphQL API Design", "text": "GraphQL allows clients to request specific data fields. Schemas define types and relationships. Mutations handle data modifications while queries fetch data.", "type": "text", "tags": ["api", "graphql"]},
]

# Ground truth: queries mapped to relevant doc indices
GROUND_TRUTH = [
    {"query": "How do neural networks learn from data?", "relevant": [0, 1, 10]},
    {"query": "Python libraries for data analysis", "relevant": [2, 15]},
    {"query": "How to secure web applications", "relevant": [4, 7]},
    {"query": "Container orchestration and deployment", "relevant": [8, 5]},
    {"query": "Building user interfaces with components", "relevant": [9, 17]},
    {"query": "Understanding language with AI models", "relevant": [10, 0, 13]},
    {"query": "Managing source code changes in teams", "relevant": [11, 12]},
    {"query": "Image recognition and object detection", "relevant": [13, 1]},
    {"query": "Distributed ledger and smart contracts", "relevant": [14]},
    {"query": "Scheduling tasks on Linux servers", "relevant": [16, 5]},
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "test_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Helpers ──

def embed_all(kb):
    """Generate embeddings for all KB entries."""
    print(f"Generating embeddings for {len(kb)} documents...")
    entries = []
    for i, doc in enumerate(kb):
        emb = generate_embedding(doc["text"])
        if emb:
            entries.append({"index": i, "embedding": emb, "text": doc["text"], "title": doc["title"]})
            print(f"  [{i+1}/{len(kb)}] OK {doc['title']}")
        else:
            print(f"  [{i+1}/{len(kb)}] FAILED {doc['title']}")
        time.sleep(0.3)
    return entries

def semantic_search(query_emb, db_entries, k=5):
    scored = []
    for e in db_entries:
        sim = cosine_similarity(query_emb, e["embedding"])
        scored.append({"index": e["index"], "similarity": sim, "title": e["title"]})
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:k]

def keyword_search_local(query, kb, k=5):
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    scored = []
    for i, doc in enumerate(kb):
        text = (doc["title"] + " " + doc["text"]).lower()
        hits = sum(1 for kw in keywords if kw in text)
        if hits > 0:
            scored.append({"index": i, "score": hits / len(keywords), "title": doc["title"]})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]

def hybrid_search_local(query_emb, db_entries, query, kb, k=5, alpha=0.7):
    sem = semantic_search(query_emb, db_entries, k=len(db_entries))
    kw = keyword_search_local(query, kb, k=len(kb))
    sem_map = {r["index"]: r["similarity"] for r in sem}
    kw_map = {r["index"]: r["score"] for r in kw}
    all_ids = set(sem_map.keys()) | set(kw_map.keys())
    combined = []
    for idx in all_ids:
        s = sem_map.get(idx, 0.0)
        kws = kw_map.get(idx, 0.0)
        combined.append({"index": idx, "score": alpha * s + (1 - alpha) * kws})
    combined.sort(key=lambda x: x["score"], reverse=True)
    return combined[:k]

def precision_at_k(retrieved_indices, relevant_indices, k=5):
    top_k = retrieved_indices[:k]
    return len(set(top_k) & set(relevant_indices)) / k if k > 0 else 0

def recall_at_k(retrieved_indices, relevant_indices, k=5):
    top_k = retrieved_indices[:k]
    return len(set(top_k) & set(relevant_indices)) / len(relevant_indices) if relevant_indices else 0

# ── Chart styling ──
def style_chart(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(fontsize=10, framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

# ── TEST 1: Search Precision Comparison ──
def test1_precision_comparison(db_entries, query_embeddings):
    print("\n--- Test 1: Search Precision Comparison ---")
    sem_p, kw_p, hyb_p = [], [], []
    sem_r, kw_r, hyb_r = [], [], []

    for gt in GROUND_TRUTH:
        q = gt["query"]
        rel = gt["relevant"]
        qe = query_embeddings[q]

        sem_res = [r["index"] for r in semantic_search(qe, db_entries, k=5)]
        kw_res = [r["index"] for r in keyword_search_local(q, KNOWLEDGE_BASE, k=5)]
        hyb_res = [r["index"] for r in hybrid_search_local(qe, db_entries, q, KNOWLEDGE_BASE, k=5)]

        sem_p.append(precision_at_k(sem_res, rel)); sem_r.append(recall_at_k(sem_res, rel))
        kw_p.append(precision_at_k(kw_res, rel));  kw_r.append(recall_at_k(kw_res, rel))
        hyb_p.append(precision_at_k(hyb_res, rel)); hyb_r.append(recall_at_k(hyb_res, rel))

    methods = ["Semantic", "Keyword", "Hybrid"]
    avg_p = [np.mean(sem_p), np.mean(kw_p), np.mean(hyb_p)]
    avg_r = [np.mean(sem_r), np.mean(kw_r), np.mean(hyb_r)]
    f1 = [2*p*r/(p+r) if (p+r) > 0 else 0 for p, r in zip(avg_p, avg_r)]

    print(f"  Semantic  -> P@5={avg_p[0]:.3f}  R@5={avg_r[0]:.3f}  F1={f1[0]:.3f}")
    print(f"  Keyword   -> P@5={avg_p[1]:.3f}  R@5={avg_r[1]:.3f}  F1={f1[1]:.3f}")
    print(f"  Hybrid    -> P@5={avg_p[2]:.3f}  R@5={avg_r[2]:.3f}  F1={f1[2]:.3f}")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(methods))
    w = 0.25
    bars1 = ax.bar(x - w, avg_p, w, label="Precision@5", color="#4F46E5", edgecolor="white")
    bars2 = ax.bar(x, avg_r, w, label="Recall@5", color="#10B981", edgecolor="white")
    bars3 = ax.bar(x + w, f1, w, label="F1 Score", color="#F59E0B", edgecolor="white")
    ax.set_xticks(x); ax.set_xticklabels(methods)
    ax.set_ylim(0, 1.05)
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.02, f"{h:.2f}", ha="center", va="bottom", fontsize=9)
    style_chart(ax, "Search Precision Comparison: Semantic vs. Keyword vs. Hybrid", "Search Method", "Score")
    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "test1_precision_comparison.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"  OK Saved: {path}")
    return avg_p, avg_r, f1

# ── TEST 2: Search Latency Scaling ──
def test2_latency_scaling(db_entries, query_embeddings):
    print("\n--- Test 2: Search Latency Scaling with KB Size ---")
    sizes = [5, 10, 15, 20]
    sem_lat, kw_lat, hyb_lat = [], [], []
    test_query = GROUND_TRUTH[0]["query"]
    qe = query_embeddings[test_query]

    for sz in sizes:
        subset = db_entries[:sz]
        kb_sub = KNOWLEDGE_BASE[:sz]

        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            semantic_search(qe, subset, k=5)
            times.append((time.perf_counter() - t0) * 1000)
        sem_lat.append(np.mean(times))

        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            keyword_search_local(test_query, kb_sub, k=5)
            times.append((time.perf_counter() - t0) * 1000)
        kw_lat.append(np.mean(times))

        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            hybrid_search_local(qe, subset, test_query, kb_sub, k=5)
            times.append((time.perf_counter() - t0) * 1000)
        hyb_lat.append(np.mean(times))

        print(f"  KB={sz:2d} -> Semantic={sem_lat[-1]:.2f}ms  Keyword={kw_lat[-1]:.2f}ms  Hybrid={hyb_lat[-1]:.2f}ms")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(sizes, sem_lat, "o-", label="Semantic", color="#4F46E5", linewidth=2, markersize=8)
    ax.plot(sizes, kw_lat, "s-", label="Keyword", color="#EF4444", linewidth=2, markersize=8)
    ax.plot(sizes, hyb_lat, "^-", label="Hybrid", color="#10B981", linewidth=2, markersize=8)
    ax.fill_between(sizes, sem_lat, alpha=0.1, color="#4F46E5")
    ax.fill_between(sizes, hyb_lat, alpha=0.1, color="#10B981")
    style_chart(ax, "Search Latency Scaling with Knowledge Base Size", "Number of Documents in KB", "Avg Latency (ms)")
    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "test2_latency_scaling.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"  OK Saved: {path}")

# ── TEST 3: Hybrid Precision@5 vs α ──
def test3_hybrid_alpha(db_entries, query_embeddings):
    print("\n--- Test 3: Hybrid Search Precision@5 vs. alpha ---")
    alphas = np.arange(0.0, 1.05, 0.1)
    avg_precisions = []
    avg_recalls = []

    for alpha in alphas:
        precs, recs = [], []
        for gt in GROUND_TRUTH:
            q = gt["query"]
            rel = gt["relevant"]
            qe = query_embeddings[q]
            res = [r["index"] for r in hybrid_search_local(qe, db_entries, q, KNOWLEDGE_BASE, k=5, alpha=alpha)]
            precs.append(precision_at_k(res, rel))
            recs.append(recall_at_k(res, rel))
        avg_precisions.append(np.mean(precs))
        avg_recalls.append(np.mean(recs))
        print(f"  alpha={alpha:.1f} -> P@5={avg_precisions[-1]:.3f}  R@5={avg_recalls[-1]:.3f}")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(alphas, avg_precisions, "o-", label="Precision@5", color="#4F46E5", linewidth=2.5, markersize=7)
    ax.plot(alphas, avg_recalls, "s--", label="Recall@5", color="#10B981", linewidth=2.5, markersize=7)
    best_idx = int(np.argmax(avg_precisions))
    ax.axvline(x=alphas[best_idx], color="#F59E0B", linestyle=":", linewidth=2, label=f"Best alpha={alphas[best_idx]:.1f}")
    ax.annotate(f"Peak P@5={avg_precisions[best_idx]:.2f}", xy=(alphas[best_idx], avg_precisions[best_idx]),
                xytext=(alphas[best_idx]+0.12, avg_precisions[best_idx]+0.05),
                arrowprops=dict(arrowstyle="->", color="#F59E0B"), fontsize=10, color="#F59E0B")
    ax.set_xlim(-0.05, 1.05); ax.set_ylim(0, 1.05)
    ax.set_xticks(np.arange(0, 1.1, 0.1))
    style_chart(ax, "Hybrid Search Precision@5 vs. alpha Weighting Parameter", "alpha (Semantic Weight)  |  1-alpha = Keyword Weight", "Score")
    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "test3_hybrid_alpha.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"  OK Saved: {path}")

# ── TEST 4: Retrieval Window K ──
def test4_retrieval_window_k(db_entries, query_embeddings):
    print("\n--- Test 4: Retrieval Window Size K ---")
    ks = [1, 2, 3, 5, 7, 10, 15]
    completeness_vals = []
    latency_vals = []

    for k in ks:
        recs, times = [], []
        for gt in GROUND_TRUTH:
            q = gt["query"]
            rel = gt["relevant"]
            qe = query_embeddings[q]
            t0 = time.perf_counter()
            res = [r["index"] for r in semantic_search(qe, db_entries, k=k)]
            times.append((time.perf_counter() - t0) * 1000)
            recs.append(recall_at_k(res, rel, k=k))
        completeness_vals.append(np.mean(recs))
        latency_vals.append(np.mean(times))
        print(f"  K={k:2d} -> Recall={completeness_vals[-1]:.3f}  Latency={latency_vals[-1]:.2f}ms")

    fig, ax1 = plt.subplots(figsize=(9, 5.5))
    color1, color2 = "#4F46E5", "#EF4444"
    ax1.plot(ks, completeness_vals, "o-", color=color1, linewidth=2.5, markersize=8, label="Recall (Completeness)")
    ax1.set_ylim(0, 1.05)
    ax1.set_ylabel("Recall (Completeness)", color=color1, fontsize=11)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.fill_between(ks, completeness_vals, alpha=0.1, color=color1)

    ax2 = ax1.twinx()
    ax2.plot(ks, latency_vals, "s--", color=color2, linewidth=2.5, markersize=8, label="Latency")
    ax2.set_ylabel("Latency (ms)", color=color2, fontsize=11)
    ax2.tick_params(axis="y", labelcolor=color2)

    ax1.set_xlabel("Retrieval Window Size K", fontsize=11)
    ax1.set_title("Effect of Retrieval Window Size K on Completeness and Latency", fontsize=14, fontweight="bold", pad=12)
    ax1.grid(True, alpha=0.3, linestyle="--")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="center right", fontsize=10)
    ax1.spines["top"].set_visible(False)
    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "test4_retrieval_window_k.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"  OK Saved: {path}")


def main():
    print("=" * 60)
    print("  SYNAPSE SEARCH BENCHMARKS")
    print("=" * 60)

    # Step 1: Embed knowledge base
    db_entries = embed_all(KNOWLEDGE_BASE)
    if len(db_entries) < 10:
        print(f"\nWARNING: Only {len(db_entries)} embeddings generated. Need at least 10. Check GEMINI_API_KEY.")
        return

    # Step 2: Embed queries
    print(f"\nGenerating query embeddings...")
    query_embeddings = {}
    for gt in GROUND_TRUTH:
        qe = generate_embedding(gt["query"])
        if qe:
            query_embeddings[gt["query"]] = qe
            print(f"  OK {gt['query'][:50]}")
        time.sleep(0.3)

    if len(query_embeddings) < len(GROUND_TRUTH):
        print(f"\nWARNING: Only {len(query_embeddings)}/{len(GROUND_TRUTH)} query embeddings. Check API key.")
        return

    # Step 3: Run all tests
    test1_precision_comparison(db_entries, query_embeddings)
    test2_latency_scaling(db_entries, query_embeddings)
    test3_hybrid_alpha(db_entries, query_embeddings)
    test4_retrieval_window_k(db_entries, query_embeddings)

    print("\n" + "=" * 60)
    print(f"  ALL TESTS COMPLETE - Charts saved to: {OUTPUT_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
