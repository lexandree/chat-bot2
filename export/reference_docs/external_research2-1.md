Идея сильная. Это уже не просто “RAG поверх закона”, а нормальный retrieval engine для права. Самый удачный ход у тебя — не пытаться заставить один эмбеддинг “понять весь параграф”, а разнести смысл по слоям: атомарное правило для поиска, родительский параграф для возврата контекста.

Где я бы усилил архитектуру.

**1. Сделай не один уровень чанков, а три.**
Сейчас у тебя фактически два уровня: `Paragraph -> AtomicRule`. Я бы добавил еще `Section/Article` и искал сразу в multi-resolution схеме:
`AtomicRule` — для recall,
`Paragraph` — для локального контекста,
`Section/Article` — для финального юридического смысла.
Иначе будет частая проблема: атомарное правило находится отлично, но теряет оговорки, исключения, условия применимости и отсылки, которые в праве критичны.

**2. В секции про blurry embeddings я бы поправил не только chunking, но и режим эмбеддинга.**
Для текущих retrieval-вариантов `jina-embeddings-v5` Jina явно указывает асимметричное кодирование с префиксами `Query:` и `Document:`, сравнение по cosine, а GGUF retrieval-модели для llama.cpp идут с `last-token pooling`, а не с mean pooling. Если у тебя в пайплайне где-то остался mean pooling или симметричное кодирование без префиксов, качество может проседать еще до любых проблем длинного контекста. ([Jina AI][1])

**3. “Хирургический сплиттинг” я бы применял не только к гигантам.**
В немецком праве проблемны не только аномально длинные параграфы, но и обычные параграфы с плотной модальностью: `soweit`, `sofern`, `es sei denn`, исключения, оговорки, cross-reference. Поэтому лучше завести rule-based splitter по юридическим маркерам и уже потом добивать LLM-декомпозицией только сложные случаи. Иначе ты будешь ловить false negatives именно на “нормальных” по длине, но юридически перегруженных кусках.

**4. Для немецкого языка NER + лемматизация — полезно, но недостаточно.**
Самый опасный пробел тут — decompounding. Юридические композиты часто не являются именованными сущностями, поэтому NER их регулярно пропускает. Я бы добавил отдельный слой:

* decompounding / subword fallback,
* словарь нормативных терминов,
* concept normalization,
* alias-таблицу для терминов и вариантов написания.

Для Neo4j это хорошо сочетается с full-text индексами: они построены на Lucene, поддерживают language-specific analyzers и умеют давать relevance score, а не просто exact match. Для немецкого корпуса это особенно полезно как вторая ось recall рядом с векторами. ([Graph Database & Analytics][2])

**5. Node Similarity — да, но только на правильной проекции графа и скорее offline.**
По документации GDS `Node Similarity` сравнивает узлы через общих соседей, ожидает по сути двудольную проекцию и имеет тяжелую асимптотику: `O(n^3)` по времени и `O(n^2)` по памяти. То есть идея хорошая, но не на “сыром” юридическом графе и не как default on-the-fly. Лучше строить отдельные bipartite-проекции вроде `Rule -> Concept`, `Rule -> CitationTarget`, `Rule -> DoctrineTerm` и считать similarity там пакетно с записью результатов в граф. ([Graph Database & Analytics][3])

**6. PageRank и community detection нужны как priors, а не как сильный ranking-сигнал.**
PageRank в Neo4j измеряет важность узла по входящим связям и важности ссылающихся узлов — для “фундаментальности нормы” это подходит. Leiden действительно лучше Louvain там, где важна связность сообществ: он как раз был введен, чтобы избегать плохо связанных community. Но если эти сигналы дать в общий скор слишком большой массой, система начнет любить “центральные” нормы и недолюбливать редкие, но точные специальные положения. Для права это типичная ошибка. ([Graph Database & Analytics][4])

**7. Я бы разделил retrieval и ranking на два этапа.**
Текущая формула
[
Score = w_1 \cdot Vector_Sim + w_2 \cdot Keyword_Match + w_3 \cdot GDS_Rank
]
нормальна как baseline, но не как финальная система. Лучше так:

1. **Candidate generation**: vector + fulltext + concept-match + citation-neighbors.
2. **Reranking**: уже на топ-50/100 кандидатов с более дорогими признаками.

Это особенно логично, потому что `llama-server` уже умеет continuous batching и имеет отдельный reranking endpoint; кроме того, в server-параметрах `--batch-size` и `--ubatch-size` разделены как логический и физический максимум батча. ([GitHub][5])

**8. В Neo4j я бы переходил на `SEARCH`, а не держался за старый vector query API.**
В текущей документации Neo4j `SEARCH` — предпочтительный способ работы с vector indexes начиная с 2026.01. Он позволяет делать in-index filtering через `WHERE` прямо внутри ANN-поиска. Для legal retrieval это очень сильная штука: можно фильтровать по юрисдикции, году редакции, типу акта, валидности, ведомству, суду, уровню нормы, не сваливаясь в грубый post-filtering. ([Graph Database & Analytics][6])

**9. Самая недооцененная часть — temporal validity.**
Для права это не “опция”, а ядро модели данных. Норма без времени действия — полунорма. Я бы обязательно добавил:

* `valid_from`, `valid_to`,
* `version_of`,
* `repeals`, `amends`, `supersedes`,
* отдельное хранение редакций,
* поиск “as of date”.

Иначе retrieval будет иногда идеально находить уже не действующий текст. Это один из самых дорогих классов ошибок.

**10. Еще один пробел — типизация связей.**
Сейчас у тебя “подразумеваемые связи” описаны хорошо, но я бы жестче разделил:

* `CITES`
* `AMENDS`
* `IMPLEMENTS`
* `EXCEPTION_TO`
* `DEFINES`
* `REQUIRES`
* `APPLIES_IF`
* `EXCLUDES_IF`
* `SEMANTICALLY_RELATED`

Для юридического поиска “похоже” и “исключает” — противоположные вещи. Без полярности и типа связи граф легко начинает галлюцинировать полезность.

**11. Нужно вшить explainability как first-class output.**
Не просто вернуть параграф, а вернуть:

* почему найдено,
* какой канал сработал,
* какие concept-узлы совпали,
* есть ли прямое цитирование,
* есть ли только латентная связь,
* какая редакция нормы использована.

Для legal search это не nice-to-have, а условие доверия к системе.

**12. Я бы слегка переписал финальное ТЗ.**
Не “от фильтрации батчей до финальной формулы”, а так:

* ingestion
* structural parsing
* legal-aware splitting
* concept extraction + decompounding
* multi-level embeddings
* fulltext / vector / concept indexes
* graph projection for GDS
* offline GDS enrichment
* candidate generation
* reranking
* explanation layer
* temporal validation
* evaluation harness

Это переводит проект из “умного поиска” в инженерно устойчивую систему.

Если сжать до главного, мои три ключевые правки такие:

1. **multi-resolution retrieval вместо только `Paragraph -> AtomicRule`**
2. **двухэтапный retrieval + rerank вместо одной линейной формулы**
3. **temporal/versioned legal graph как обязательная часть модели**

И мой главный технический риск в твоем дизайне такой:
ты очень хорошо думаешь про семантику, но пока чуть недодаешь веса **времени действия нормы**, **типу юридической связи** и **калибровке ранжирования**. Для правового поиска именно эти три вещи чаще убивают качество, чем “плохой embedding”.

Могу дальше собрать это в более жесткий blueprint: схема узлов/ребер Neo4j, этапы пайплайна и пример Cypher/GDS-стека под твою архитектуру.

[1]: https://jina.ai/models/jina-embeddings-v5-text-small/ "jina-embeddings-v5-text-small - Search Foundation Models"
[2]: https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/full-text-indexes/ "Full-text indexes - Cypher Manual"
[3]: https://neo4j.com/docs/graph-data-science/current/algorithms/node-similarity/ "Node Similarity - Neo4j Graph Data Science"
[4]: https://neo4j.com/docs/graph-data-science/current/algorithms/page-rank/ "PageRank - Neo4j Graph Data Science"
[5]: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md "llama.cpp/tools/server/README.md at master · ggml-org/llama.cpp · GitHub"
[6]: https://neo4j.com/docs/cypher-manual/current/clauses/search/ "SEARCH - Cypher Manual"
