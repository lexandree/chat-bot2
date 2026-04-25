# Multi-hop Reasoning Knowledge Graph: Research Summary

*Date: March 20, 2026*

This document synthesizes modern approaches to building and reasoning over Knowledge Graphs (KGs) capable of multi-hop inference, specifically tailored for text-heavy, complex domains like legal and bureaucratic assistance.

## 1. Data Ingestion & Transformation (Text to Graph)

Before reasoning can occur, unstructured text (laws, chat logs, forum posts) must be mapped into the Graph.

### A. Preprocessing & Extraction
- **Discourse & Coreference Resolution:** A critical first step for long legal documents. Before extracting entities, models must resolve pronouns ("he", "the applicant") to their canonical entities and break documents into logical discourse units.
- **Entity & Relation Extraction:** 
  - *Modern Standard:* Transformer-based models fine-tuned on legal text (e.g., Legal-BERT).
  - *SME/Cost-Effective Approach:* Weak supervision and layout-aware extraction, supplemented by LLM prompting for complex, nested legal concepts.
- **Provenance Tracking (CRITICAL):** Every extracted entity and relationship must store metadata: source document, page/span, confidence score, and timestamp. This is essential for compliance and debugging (reducing hallucination cascades).

### B. Entity Canonicalization & Linking (Entity Resolution)
- Merging multiple mentions of the same real-world entity into a single Graph Node.
- *Methodology:* Use deterministic Registry IDs (e.g., official paragraph numbers) where available. For ambiguous entities (e.g., "Jobcenter", "Arbeitsamt"), use semantic embedding similarity combined with human-in-the-loop review loops.

## 2. Graph Storage & Linking

- **Property Graphs (Neo4j, ArangoDB):** Recommended for multi-hop traversal and analytics. They natively store attributes on nodes/edges and scale predictably for path searches.
- **Hybrid Storage (Graph + Vector):** The standard pattern for modern RAG. Canonical entities and paragraphs are stored with dense vector embeddings (e.g., using Neo4j's native Vector Index or Milvus/FAISS).
  - *Workflow:* Vector retrieval identifies the "entry points" (Candidate Nodes) based on user query similarity. Exact graph traversals are then executed from these entry points.

## 3. Modern Multi-hop Reasoning Techniques

Once the graph is built, how does the system answer complex queries (e.g., tracking a user's status to a specific benefit, accounting for local exceptions)?

### A. Symbolic and Path-based Methods
- Algorithms (like Path Ranking or Rule-aware Reinforcement Learning) explicitly search for paths between nodes.
- **Pros:** 100% Interpretable and Explainable. You can show the user the exact chain of logic (e.g., *Status -> Law -> Benefit*).
- **Cons:** Rigid. Struggles with missing links or noisy data.

### B. Graph Neural Networks (GNNs)
- Deep learning models (like R-GCN or GAT) that learn multi-hop propagation patterns by aggregating information from a node's neighbors over several "hops."
- **Pros:** Excellent for predicting missing links or classifying nodes based on deep structural patterns.
- **Cons:** "Black-box" nature makes it hard to explain *why* a specific answer was reached (which is dangerous in legal advice).

### C. Hybrid RAG (LLM + KG Integration) - *Recommended Approach*
The most practical approach for our "SME Hivemind" architecture:
1. **Entry:** Use vector search to map the user's messy query to a specific `UserQuery` or `Trigger` node in the KG.
2. **Traversal:** Use symbolic graph queries (Cypher) to retrieve the relevant subgraph (e.g., up to 2-3 hops away: Law -> Requirements -> Benefits -> Exceptions).
3. **Generation:** Pass the retrieved, structured subgraph (along with its provenance metadata) into an LLM context window. The LLM acts as the "Reasoner," summarizing the subgraph into a natural language answer.
4. **Explainability:** Because the subgraph provides explicit constraints, the LLM is forced to cite the specific nodes and paths it used.

## 4. Addressing Time & Decay (Temporal Graphs)
Legal data decays (laws change, advice becomes outdated). 
- Nodes/Edges must include `created_at` and `expires_at` properties.
- Hybrid methods must incorporate timestamp checks when composing multi-hop inferences, ignoring edges flagged as `Deprecated` or `Outdated`.

## Conclusion for the Graph Bot Architecture
1. **Pipeline:** Raw Text -> LLM Extractor (identifies Entities/Relations) -> Neo4j (stores Entities, Relations, and Vectors).
2. **Reasoning:** User Query -> Vector Match -> Subgraph Retrieval via Cypher (2-3 hops) -> LLM Synthesis -> Output to User.
3. **Safety:** Implement strict confidence thresholds and rely heavily on the Human-in-the-Loop (`Compounding Knowledge Loop`) to convert `Draft` findings into `Verified` structural links.
