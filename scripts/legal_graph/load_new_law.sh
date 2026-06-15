#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-preflight}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

MANIFEST="${MANIFEST:-config/legal_xml_active_corpus.json}"
NEW_LAW_CODE="${NEW_LAW_CODE:-}"
RUN_ID="${RUN_ID:-new_law_${NEW_LAW_CODE:-unset}_$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${OUT_DIR:-data/corpus_expansion/${RUN_ID}}"
PREVIEW="${PREVIEW:-${OUT_DIR}/active_corpus_preview.json}"
PREFLIGHT_REPORT="${PREFLIGHT_REPORT:-${OUT_DIR}/new_law_preflight.json}"
CLASSIFIER_POLICY="${CLASSIFIER_POLICY:-legal-ref-context-v1}"
WRITE_EMBEDDINGS="${WRITE_EMBEDDINGS:-1}"
EMBEDDING_BATCH_SIZE="${EMBEDDING_BATCH_SIZE:-16}"
LOAD_ENV="${LOAD_ENV:-1}"

if [[ "${LOAD_ENV}" == "1" && -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${NEW_LAW_CODE}" ]]; then
  printf 'NEW_LAW_CODE is required.\n' >&2
  exit 2
fi
if [[ ! -f "${MANIFEST}" ]]; then
  printf 'Active corpus manifest not found: %s\n' "${MANIFEST}" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  printf 'jq is required.\n' >&2
  exit 2
fi

mkdir -p "${OUT_DIR}"

mapfile -t ACTIVE_LAW_CODES < <(jq -er '.inputs | map(.law_code) | unique | .[]' "${MANIFEST}")
if [[ "${#ACTIVE_LAW_CODES[@]}" -eq 0 ]]; then
  printf 'Active corpus manifest contains no law codes: %s\n' "${MANIFEST}" >&2
  exit 2
fi

ACTIVE_LAW_ARGS=()
for law_code in "${ACTIVE_LAW_CODES[@]}"; do
  ACTIVE_LAW_ARGS+=(--law-code "${law_code}")
done

run_step() {
  local step_name="$1"
  shift
  printf '\nSTEP: %s\n' "${step_name}"
  printf 'COMMAND:'
  printf ' %q' "$@"
  printf '\n'
  "$@" | tee "${OUT_DIR}/${step_name}.stdout.json"
}

preflight() {
  run_step preflight \
    python -m app corpus new-law-preflight \
    --manifest "${MANIFEST}" \
    --new-law-code "${NEW_LAW_CODE}" \
    --preview-output "${PREVIEW}" \
    --output "${PREFLIGHT_REPORT}" \
    --classifier-policy "${CLASSIFIER_POLICY}"
  jq -e '.status == "ready" and .graph_writes_performed == false' "${PREFLIGHT_REPORT}" >/dev/null
}

require_graph_writes() {
  if [[ "${ALLOW_GRAPH_WRITES:-0}" != "1" ]]; then
    printf 'Graph-write stages require ALLOW_GRAPH_WRITES=1.\n' >&2
    exit 2
  fi
}

load_graph() {
  require_graph_writes
  run_step schema_bootstrap python -m app schema bootstrap
  run_step graph_load_new_law \
    python -m app graph load --preview "${PREVIEW}" --law-code "${NEW_LAW_CODE}"
  run_step graph_verify_new_law \
    python -m app graph verify --law-code "${NEW_LAW_CODE}"
}

post_load() {
  require_graph_writes
  run_step relationships_refresh_active_corpus \
    python -m app relationships refresh \
    "${ACTIVE_LAW_ARGS[@]}" \
    --classifier-policy "${CLASSIFIER_POLICY}"
  run_step relationships_verify_active_corpus \
    python -m app relationships verify \
    "${ACTIVE_LAW_ARGS[@]}" \
    --classifier-policy "${CLASSIFIER_POLICY}"

  if [[ "${WRITE_EMBEDDINGS}" == "1" ]]; then
    run_step embeddings_write_new_law \
      python -m app embeddings write \
      --law-code "${NEW_LAW_CODE}" \
      --batch-size "${EMBEDDING_BATCH_SIZE}"
  else
    printf '\nSTEP: embeddings_write_new_law skipped because WRITE_EMBEDDINGS=%s\n' "${WRITE_EMBEDDINGS}"
  fi

  run_step graph_verify_active_corpus \
    python -m app graph verify "${ACTIVE_LAW_ARGS[@]}"
  run_step relationships_quality_active_corpus \
    python -m app relationships quality \
    "${ACTIVE_LAW_ARGS[@]}" \
    --classifier-policy "${CLASSIFIER_POLICY}" \
    --output "${OUT_DIR}/relationship_quality.json"
  run_step corpus_readiness_active_corpus \
    python -m app corpus readiness \
    "${ACTIVE_LAW_ARGS[@]}" \
    --output "${OUT_DIR}/corpus_readiness.json"
  run_step graph_snapshot_active_corpus \
    python -m app graph snapshot \
    "${ACTIVE_LAW_ARGS[@]}" \
    --output "${OUT_DIR}/active_corpus_snapshot.json"
}

write_run_manifest() {
  local graph_load_requested="0"
  local relationships_refresh_requested="0"
  local retrieval_artifacts_require_rebuild="0"
  case "${ACTION}" in
    load)
      graph_load_requested="1"
      retrieval_artifacts_require_rebuild="1"
      ;;
    post-load)
      relationships_refresh_requested="1"
      retrieval_artifacts_require_rebuild="1"
      ;;
    full)
      graph_load_requested="1"
      relationships_refresh_requested="1"
      retrieval_artifacts_require_rebuild="1"
      ;;
  esac

  jq -n \
    --arg run_id "${RUN_ID}" \
    --arg action "${ACTION}" \
    --arg manifest "${MANIFEST}" \
    --arg new_law_code "${NEW_LAW_CODE}" \
    --arg preview "${PREVIEW}" \
    --arg preflight_report "${PREFLIGHT_REPORT}" \
    --arg out_dir "${OUT_DIR}" \
    --arg classifier_policy "${CLASSIFIER_POLICY}" \
    --arg write_embeddings "${WRITE_EMBEDDINGS}" \
    --arg embedding_batch_size "${EMBEDDING_BATCH_SIZE}" \
    --arg graph_load_requested "${graph_load_requested}" \
    --arg relationships_refresh_requested "${relationships_refresh_requested}" \
    --arg retrieval_artifacts_require_rebuild "${retrieval_artifacts_require_rebuild}" \
    --argjson active_law_codes "$(printf '%s\n' "${ACTIVE_LAW_CODES[@]}" | jq -R . | jq -s .)" \
    '{
      artifact_type: "legal_corpus_expansion_run_manifest",
      run_id: $run_id,
      action: $action,
      status: "completed",
      manifest_path: $manifest,
      new_law_code: $new_law_code,
      active_law_codes: $active_law_codes,
      preview_path: $preview,
      preflight_report_path: $preflight_report,
      output_directory: $out_dir,
      classifier_policy_version: $classifier_policy,
      graph_load_requested: ($graph_load_requested == "1"),
      relationships_refresh_requested: ($relationships_refresh_requested == "1"),
      embeddings_requested: (($relationships_refresh_requested == "1") and ($write_embeddings == "1")),
      embedding_batch_size: ($embedding_batch_size | tonumber),
      retrieval_artifacts_require_rebuild: ($retrieval_artifacts_require_rebuild == "1"),
      notes: (
        (if $relationships_refresh_requested == "1"
         then ["relationship refresh covered the complete active corpus scope"]
         else [] end)
        +
        (if $retrieval_artifacts_require_rebuild == "1"
         then ["semantic retrieval artifacts are not rebuilt by this graph-load runner"]
         else ["offline preflight made no graph or retrieval-artifact changes"] end)
      )
    }' > "${OUT_DIR}/run_manifest.json"
  printf '\nCompleted: %s\n' "${OUT_DIR}/run_manifest.json"
  if [[ "${retrieval_artifacts_require_rebuild}" == "1" ]]; then
    printf 'Semantic retrieval artifacts must now be rebuilt for the expanded corpus.\n'
  fi
}

case "${ACTION}" in
  preflight)
    preflight
    write_run_manifest
    ;;
  load)
    preflight
    load_graph
    write_run_manifest
    ;;
  post-load)
    preflight
    post_load
    write_run_manifest
    ;;
  full)
    preflight
    load_graph
    post_load
    write_run_manifest
    ;;
  *)
    printf 'Usage: NEW_LAW_CODE=<code> %s {preflight|load|post-load|full}\n' "$0" >&2
    exit 2
    ;;
esac
