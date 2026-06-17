#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-full}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

REFERENCE_CASES="${REFERENCE_CASES:-specs/007-legal-question-canonicalization/route-ambiguity-reference-cases.jsonl}"
LEGAL_PREVIEW="${LEGAL_PREVIEW:-data/corpus_expansion/new_law_VwVfG_20260613T013823Z/active_corpus_preview.json}"
OUT_DIR="${OUT_DIR:-data/evaluation/tg_qa_retrieval_benchmark}"
PREFIX="${PREFIX:-route_ambiguity_v1_four_law}"
DOCUMENT_VECTOR_SOURCE="${DOCUMENT_VECTOR_SOURCE:-${OUT_DIR}/real_data_007_last_2000_v1_four_law_vectors.jsonl}"
ENDPOINT_URL="${ENDPOINT_URL:-${EMBEDDING_ENDPOINT_URL:-http://127.0.0.1:18080/v1/embeddings}}"
MODEL_ID="${MODEL_ID:-${EMBEDDING_MODEL_ID:-jina-embeddings-v5-text-small-retrieval-GGUF}}"
BATCH_SIZE="${BATCH_SIZE:-10}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-240}"

FULL_BATCH="${OUT_DIR}/${PREFIX}_embedding_batch.jsonl"
FULL_BATCH_SUMMARY="${OUT_DIR}/${PREFIX}_embedding_batch_summary.json"
QUERY_BATCH="${OUT_DIR}/${PREFIX}_query_embedding_batch.jsonl"
QUERY_VECTORS="${OUT_DIR}/${PREFIX}_query_external_vectors.jsonl"
QUERY_VECTOR_SUMMARY="${OUT_DIR}/${PREFIX}_query_vectorization_summary.json"
COMBINED_VECTORS="${OUT_DIR}/${PREFIX}_external_vectors.jsonl"
SEMANTIC_CASES="${OUT_DIR}/${PREFIX}_semantic_cases.jsonl"
SEMANTIC_SUMMARY="${OUT_DIR}/${PREFIX}_semantic_summary.json"
ROUTE_REPORT="${OUT_DIR}/${PREFIX}_route_report.jsonl"
ROUTE_SUMMARY="${OUT_DIR}/${PREFIX}_route_summary.json"

prepare() {
  mkdir -p "${OUT_DIR}"
  python -m app evaluation tg-qa-corpus-bounded-semantic-embedding-batch \
    --reference-cases "${REFERENCE_CASES}" \
    --legal-preview "${LEGAL_PREVIEW}" \
    --law-code AufenthG \
    --law-code AsylG \
    --law-code BeschV \
    --law-code VwVfG \
    --output "${FULL_BATCH}" \
    --summary-output "${FULL_BATCH_SUMMARY}"
  jq -c 'select(.text_role == "semantic_query")' "${FULL_BATCH}" > "${QUERY_BATCH}"
}

embed_queries() {
  python -m app evaluation tg-qa-embed-batch \
    --embedding-batch "${QUERY_BATCH}" \
    --output "${QUERY_VECTORS}" \
    --summary-output "${QUERY_VECTOR_SUMMARY}" \
    --endpoint-url "${ENDPOINT_URL}" \
    --model-id "${MODEL_ID}" \
    --batch-size "${BATCH_SIZE}" \
    --timeout-seconds "${TIMEOUT_SECONDS}"
}

verify_query_vectors() {
  test -f "${QUERY_VECTOR_SUMMARY}"
  jq -e '.failed_count == 0 and .completed_count > 0' "${QUERY_VECTOR_SUMMARY}" >/dev/null
}

verify_reusable_documents() {
  test -f "${DOCUMENT_VECTOR_SOURCE}"
  local missing_document_count
  missing_document_count="$(
    comm -23 \
      <(jq -r 'select(.text_role == "legal_section_document") | .embedding_item_id' "${FULL_BATCH}" | sort) \
      <(jq -r 'select(.text_role == "legal_section_document" and .embedding_status == "completed") | .embedding_item_id' "${DOCUMENT_VECTOR_SOURCE}" | sort) \
      | wc -l
  )"
  if [[ "${missing_document_count}" -ne 0 ]]; then
    printf 'Reusable document vectors are missing %s required items.\n' "${missing_document_count}" >&2
    exit 1
  fi
}

finish() {
  verify_query_vectors
  verify_reusable_documents
  jq -c 'select(.text_role == "legal_section_document" and .embedding_status == "completed")' \
    "${DOCUMENT_VECTOR_SOURCE}" > "${COMBINED_VECTORS}"
  jq -c 'select(.text_role == "semantic_query" and .embedding_status == "completed")' \
    "${QUERY_VECTORS}" >> "${COMBINED_VECTORS}"
  python -m app evaluation tg-qa-corpus-bounded-semantic-benchmark \
    --reference-cases "${REFERENCE_CASES}" \
    --embedding-batch "${FULL_BATCH}" \
    --external-vectors "${COMBINED_VECTORS}" \
    --vectorization-summary "${QUERY_VECTOR_SUMMARY}" \
    --k 1 \
    --k 5 \
    --k 10 \
    --output "${SEMANTIC_CASES}" \
    --summary-output "${SEMANTIC_SUMMARY}"
  python -m app evaluation tg-qa-route-ambiguity-report \
    --reference-cases "${REFERENCE_CASES}" \
    --semantic-cases "${SEMANTIC_CASES}" \
    --k 1 \
    --k 5 \
    --k 10 \
    --output "${ROUTE_REPORT}" \
    --summary-output "${ROUTE_SUMMARY}"
  printf 'Route ambiguity semantic summary: %s\n' "${SEMANTIC_SUMMARY}"
  printf 'Route ambiguity route summary: %s\n' "${ROUTE_SUMMARY}"
}

case "${ACTION}" in
  prepare)
    prepare
    ;;
  embed-queries)
    embed_queries
    ;;
  finish)
    finish
    ;;
  full)
    prepare
    embed_queries
    finish
    ;;
  *)
    printf 'Usage: %s {prepare|embed-queries|finish|full}\n' "$0" >&2
    exit 2
    ;;
esac
