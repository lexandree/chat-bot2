#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-full}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

REFERENCE_CASES="${REFERENCE_CASES:-specs/007-legal-question-canonicalization/clean-retrieval-reference-cases.jsonl}"
LEGAL_PREVIEW="${LEGAL_PREVIEW:-data/import_preview/legal_xml_preview_003_smoke.json}"
OUT_DIR="${OUT_DIR:-data/evaluation/tg_qa_retrieval_benchmark}"
PREFIX="${PREFIX:-clean_curated_v1}"
DOCUMENT_VECTOR_SOURCE="${DOCUMENT_VECTOR_SOURCE:-${OUT_DIR}/real_data_007_last_2000_v1_semantic_external_vectors.jsonl}"
DOCUMENT_VECTOR_SUMMARY="${DOCUMENT_VECTOR_SUMMARY:-${OUT_DIR}/real_data_007_last_2000_v1_semantic_vectorization_summary.json}"
ENDPOINT_URL="${ENDPOINT_URL:-${EMBEDDING_ENDPOINT_URL:-http://127.0.0.1:18080/v1/embeddings}}"
MODEL_ID="${MODEL_ID:-${EMBEDDING_MODEL_ID:-jina-embeddings-v5-text-small-retrieval-GGUF}}"

FULL_BATCH="${OUT_DIR}/${PREFIX}_semantic_embedding_batch.jsonl"
FULL_BATCH_SUMMARY="${OUT_DIR}/${PREFIX}_semantic_embedding_batch_summary.json"
QUERY_BATCH="${OUT_DIR}/${PREFIX}_query_embedding_batch.jsonl"
QUERY_VECTORS="${OUT_DIR}/${PREFIX}_query_external_vectors.jsonl"
QUERY_VECTOR_SUMMARY="${OUT_DIR}/${PREFIX}_query_vectorization_summary.json"
COMBINED_VECTORS="${OUT_DIR}/${PREFIX}_external_vectors.jsonl"
SEMANTIC_CASES="${OUT_DIR}/${PREFIX}_semantic_cases.jsonl"
SEMANTIC_SUMMARY="${OUT_DIR}/${PREFIX}_semantic_summary.json"
REVIEW_BATCH="${OUT_DIR}/${PREFIX}_relevance_review_24.jsonl"
REVIEW_SUMMARY="${OUT_DIR}/${PREFIX}_relevance_review_24_summary.json"
REVIEW_HTML="${OUT_DIR}/${PREFIX}_relevance_review_24.html"
REVIEW_HTML_SUMMARY="${OUT_DIR}/${PREFIX}_relevance_review_24_html_summary.json"

prepare() {
  mkdir -p "${OUT_DIR}"
  python -m app evaluation tg-qa-corpus-bounded-semantic-embedding-batch \
    --reference-cases "${REFERENCE_CASES}" \
    --legal-preview "${LEGAL_PREVIEW}" \
    --law-code AufenthG \
    --law-code AsylG \
    --law-code BeschV \
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
    --batch-size 16 \
    --timeout-seconds 240
}

verify_reusable_documents() {
  test -f "${DOCUMENT_VECTOR_SOURCE}"
  test -f "${DOCUMENT_VECTOR_SUMMARY}"
  jq -e --arg model_id "${MODEL_ID}" \
    '.model_id == $model_id and .failed_count == 0' "${DOCUMENT_VECTOR_SUMMARY}" >/dev/null
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
  verify_reusable_documents
  jq -c 'select(.text_role == "legal_section_document" or (.candidate_id | startswith("tg-qa-clean-retrieval-case:")))' \
    "${DOCUMENT_VECTOR_SOURCE}" "${QUERY_VECTORS}" > "${COMBINED_VECTORS}"
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
  python -m app evaluation tg-qa-retrieval-relevance-review-batch \
    --semantic-cases "${SEMANTIC_CASES}" \
    --embedding-batch "${FULL_BATCH}" \
    --max-cases 24 \
    --top-k 10 \
    --output "${REVIEW_BATCH}" \
    --summary-output "${REVIEW_SUMMARY}"
  python -m app evaluation tg-qa-retrieval-relevance-review-html \
    --review-batch "${REVIEW_BATCH}" \
    --output "${REVIEW_HTML}" \
    --summary-output "${REVIEW_HTML_SUMMARY}"
  printf 'Review HTML: %s\n' "${REVIEW_HTML}"
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
