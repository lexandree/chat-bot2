**Отлично сформулировано!** 👍  

План очень цельный, продуманный и именно под локальное железо (GTX 1060 6 ГБ) — это редкость. Ты правильно поставил в центр **семантическую плотность + немецкую лингвистическую специфику + графовый интеллект**. Это уже не просто RAG, а настоящий **GraphRAG + Legal Knowledge Graph**.  

Ниже — честная критика, дополнения и конкретные рекомендации по реализации. Разбил по твоим пунктам + добавил пару новых блоков.

### 1. Аппаратный стек и модель данных — мелкие риски
удалено, не спрашивал, а информировал.

### 2. Хирургический сплиттинг — сильная сторона, но нужно доработать
**Плюс**: Parent-Paragraph → [:HAS_RULE] → Child-AtomicRule — идеальная архитектура.

**Критика / дополнения**:
- Не только «гигантские» параграфы. Даже средние (500–1500 токенов) в немецком праве часто содержат 3–7 отдельных утверждений.
- **Предлагаю двухуровневый подход**:
  1. **Быстрый сплит** (spacy + heuristic): по точкам, двоеточиям, «soweit», «sofern», «es sei denn» и т.д.
  2. **LLM-декомпозиция** только для оставшихся «мутных» кусков (threshold ~800 токенов).
- **Structured output** обязателен:
  ```json
  {
    "propositions": [
      {"text": "...", "type": "obligation|right|definition|exception|condition", "subject": "...", "object": "..."}
    ]
  }
  ```
  Few-shot примеры **только из немецкого права** (BGB, StGB, VVG и т.д.) — критично для качества.

### 3. Немецкий язык (Komposita) — здесь можно выжать максимум
Ты абсолютно прав — это самая большая боль векторных моделей в немецком праве.

**Дополнения**:
- **Compound splitting**: библиотека `compound-word-splitter` + spaCy `de_core_news_lg` + кастомные правила для юридических терминов (`Schadensersatzpflicht → Schaden + Ersatz + Pflicht`).
- **Concept Nodes** — сделать отдельным типом узлов с метками:
  - `[:SYNONYM]`, `[:ABBREVIATION]`, `[:RELATED_TO]`, `[:OPPOSITE_TO]`.
  - Каждый AtomicRule → [:MENTIONS] → ConceptNode (много ко многим).
- NER + лемматизация: лучше **spaCy + fine-tuned German Legal BERT** (если найдём open-source 2025–2026 года) или просто LLM-prompt на втором проходе.

### 4–5. Графовый интеллект и гибридный поиск — самые важные доработки
**GDS**:
- **100% pre-calculated**. На GTX 1060 on-the-fly PageRank/NodeSimilarity будет убивать latency.
- После каждой массовой загрузки батча запускаем:
  - `gds.pageRank`
  - `gds.nodeSimilarity` → создаём ребра `[:SEMANTICALLY_RELATED {weight: score}]`
  - `gds.louvain` или `gds.leiden` для community detection

**Гибридный score** — твоя формула хорошая, но **критически важно нормализовать**:

**Рекомендуемый вариант (самый robust)**:
```cypher
Score = 0.45 * VectorSim_norm 
      + 0.30 * BM25_norm 
      + 0.25 * GDS_rank_norm
```
Или ещё лучше — **Reciprocal Rank Fusion (RRF)** как основной метод + weighted sum как fallback.

**Neo4j-реализация**:
- Vector index (hnsw)
- Full-text index (или Lucene) для BM25
- Cypher: `CALL db.index.vector.queryNodes(...)` + `CALL db.index.fulltext.queryNodes(...)` → потом RRF в одном запросе.

### 6. Подразумеваемые связи — дополнения
Отлично. Дополнительно:
- **Явные ссылки** — отдельный тип ребра `[:REFERENCES {article: "§ 823 Abs. 1 BGB", date: "2025-01-01"}]`
- **Иерархия документа** (очень важно для права!):
  ```cypher
  (Law:LegalAct {name: "BGB"})
  -[:HAS]-> (Chapter)
  -[:HAS]-> (Section)
  -[:HAS]-> (Paragraph)
  -[:HAS_RULE]-> (AtomicRule)
  ```
- **Temporal graph** — законы меняются. Добавь свойство `valid_from` / `valid_to` или отдельные версии узлов.

### Новые предложения (обязательно добавить в ТЗ)

1. **Query expansion через Concept Nodes**  
   Если запрос содержит «Schadensersatzpflicht» → автоматически расширяем по синонимам/родственным концептам.

2. **Post-retrieval reranking**  
   Даже лёгким cross-encoder’ом (например, `cross-encoder/ms-marco-MiniLM-L-12-v2` в 4-bit) можно поднять качество на 15–20%. Запускаем только top-20.

3. **Evaluation framework** (без него нельзя)  
   - Собрать 50–100 тестовых запросов + golden answers из реальных юридических кейсов.
   - Метрики: nDCG@10, Recall@5, Legal Precision (насколько ответ ссылается на правильные нормы).

4. **Обработка обновлений законов**  
   При новой версии параграфа — создавать новый узел и `[:SUPERSEDED_BY]` ребро.

### Итог
Твой план уже можно брать за основу **технического задания для пайплайна**.  

**Что я предлагаю сделать дальше**:
1. Составить полный **graph schema** (все лейблы, отношения, свойства, constraints).
2. Написать **prompt + few-shot** для proposition extraction.
3. Определить точные веса и метод fusion (RRF vs weighted sum).
4. Начать писать ingestion pipeline (от PDF/JSON закона → atomic rules → graph).

Если хочешь — могу прямо сейчас набросать:
- полный Cypher-схему графа,
- пример промпта для декомпозиции,
- или первый черновик ingestion-пайплайна.

Готов углубляться в любой пункт. Что скажешь? 🔥