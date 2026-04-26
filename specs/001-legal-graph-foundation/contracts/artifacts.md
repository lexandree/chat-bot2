# Artifact Contracts

## Legal XML Preview Artifact

```json
{
  "preview_id": "string",
  "created_at": "ISO-8601 timestamp",
  "source_scope": {
    "source_families": ["law"],
    "law_codes": ["AufenthG"]
  },
  "missing_inputs": [
    {
      "path": "string",
      "required": false,
      "reason": "missing"
    }
  ],
  "source_documents": [
    {
      "source_document_id": "string",
      "source_family": "law",
      "jurisdiction": "DE",
      "language": "de",
      "law_code": "AufenthG",
      "title": "Aufenthaltsgesetz",
      "publication_date": "2004-07-30",
      "source_uri": "string",
      "checksum": "sha256:string"
    }
  ],
  "source_fragments": [
    {
      "source_fragment_id": "string",
      "source_document_id": "string",
      "law_code": "AufenthG",
      "section_reference": "§ 1",
      "normalized_reference": "§ 1",
      "title": "string",
      "body_text": "string",
      "order_index": 1,
      "checksum": "sha256:string"
    }
  ]
}
```

## Load Run Report

```json
{
  "load_run_id": "string",
  "selected_scope": {
    "law_codes": ["AufenthG"]
  },
  "write_semantics": "idempotent_upsert",
  "processed_count": 0,
  "skipped_count": 0,
  "failed_count": 0,
  "source_document_count": 0,
  "source_fragment_count": 0,
  "legal_section_count": 0,
  "legal_reference_count": 0,
  "unresolved_reference_count": 0,
  "warnings": [],
  "errors": []
}
```

## Embedding Run Report

```json
{
  "embedding_run_id": "string",
  "selected_scope": {
    "law_codes": ["AufenthG"]
  },
  "embedding_profile_id": "jina_v5_q8_1024_norm_v1",
  "model_id": "jina-embeddings-v5-text-small-retrieval-GGUF",
  "backend_name": "local_embedding_endpoint",
  "routing_mode": "local_only",
  "vector_dimensions": 1024,
  "normalized": true,
  "processed_count": 0,
  "skipped_count": 0,
  "failed_count": 0,
  "failure_reason": null
}
```

## Verification Report

```json
{
  "selected_scope": {
    "law_codes": ["AufenthG"]
  },
  "source_document_count": 0,
  "source_fragment_count": 0,
  "legal_act_count": 0,
  "legal_section_count": 0,
  "legal_fragment_count": 0,
  "legal_reference_count": 0,
  "unresolved_reference_count": 0,
  "embedding_count": 0,
  "embedding_profile_ids": [],
  "vector_dimensions": [],
  "backend_names": [],
  "candidate_review_placeholders_present": true,
  "warnings": [],
  "errors": []
}
```

## Deletion Report

```json
{
  "selected_scope": {
    "law_codes": ["AufenthG"]
  },
  "matched_records": 0,
  "removed_records": 0,
  "skipped_records": 0,
  "retained_related_records": 0,
  "warnings": [],
  "errors": []
}
```

## Structural Retrieval Result

```json
{
  "query_reference": {
    "law_code": "AufenthG",
    "section_reference": "1"
  },
  "matched_legal_section_id": "string",
  "source_references": ["string"],
  "relation_types": ["CITES"],
  "depth_limit": 1,
  "fanout_limit": 25,
  "node_limit": 100,
  "visited_count": 0,
  "unresolved_target_evidence": []
}
```

Structural retrieval artifacts MUST NOT include answer text fields such as
`answer_text`, `answer`, or `generated_answer`; generated answers are out of
scope.
