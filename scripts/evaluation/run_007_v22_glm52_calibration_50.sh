#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

set -a
source .env
set +a

DATA_DIR="data/evaluation/tg_qa_canonicalization"
PREFIX="${PREFIX:-real_data_007_v22_control_plane_calibration_50}"
BATCH="${BATCH:-$DATA_DIR/${PREFIX}_batch.jsonl}"
RESULTS="${RESULTS:-$DATA_DIR/${PREFIX}_glm52_results.jsonl}"
SUMMARY="${SUMMARY:-$DATA_DIR/${PREFIX}_glm52_summary.json}"
CHECKPOINT="${CHECKPOINT:-$DATA_DIR/${PREFIX}_glm52_checkpoint.json}"
RUN_BUNDLE="${RUN_BUNDLE:-$DATA_DIR/${PREFIX}_glm52_run_bundle.json}"
LOG_PATH="${LOG_PATH:-$DATA_DIR/${PREFIX}_glm52.log}"
EVIDENCE="${EVIDENCE:-$DATA_DIR/${PREFIX}_glm52_evidence.jsonl}"
MANIFEST="${MANIFEST:-$DATA_DIR/${PREFIX}_glm52_manifest.json}"
MODEL_ID="${MODEL_ID:-glm-5.2}"
PROMPT_VERSION="${PROMPT_VERSION:-tg_question_canonicalizer_v22_positive}"
RUN_ID="${RUN_ID:-tg-question-canonicalization-run:${PREFIX}-glm52}"
MAX_ITEMS="${MAX_ITEMS:-50}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
MAX_TOKENS="${MAX_TOKENS:-4096}"
PROVIDER_MAX_ATTEMPTS="${PROVIDER_MAX_ATTEMPTS:-3}"
PROVIDER_RETRY_DELAY_SECONDS="${PROVIDER_RETRY_DELAY_SECONDS:-15}"
STOP_AFTER_CONSECUTIVE_PROVIDER_FAILURES="${STOP_AFTER_CONSECUTIVE_PROVIDER_FAILURES:-3}"
EXTRA_BODY_JSON="${EXTRA_BODY_JSON-}"
if [[ -z "$EXTRA_BODY_JSON" ]]; then
  EXTRA_BODY_JSON='{}'
fi
if ! EXTRA_BODY_JSON="$(jq -ce 'if type == "object" then . else error("expected JSON object") end' <<<"$EXTRA_BODY_JSON")"; then
  echo "Invalid EXTRA_BODY_JSON; expected one JSON object." >&2
  exit 2
fi
NO_RESUME="${NO_RESUME:-0}"

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "missing required artifact: $1" >&2
    exit 1
  fi
}

run() {
  require_file "$BATCH"
  local count
  count="$(wc -l < "$BATCH")"
  if (( count > 100 )); then
    echo "refusing bounded GLM calibration: batch has $count records (limit: 100)" >&2
    exit 2
  fi
  local -a cmd=(
    env PYTHONPATH=src TG_QUESTION_CANONICALIZATION_PROMPT_VERSION="$PROMPT_VERSION"
    python -m app evaluation tg-qa-canonicalization-llm-run
    --batch "$BATCH"
    --output "$RESULTS"
    --summary-output "$SUMMARY"
    --checkpoint-output "$CHECKPOINT"
    --run-bundle-output "$RUN_BUNDLE"
    --log-path "$LOG_PATH"
    --endpoint-url "$OPENCODE_CHAT_COMPLETIONS_URL"
    --model-id "$MODEL_ID"
    --canonicalization-run-id "$RUN_ID"
    --structured-output-method json_mode
    --api-key-env OPENCODE_API_KEY
    --max-items "$MAX_ITEMS"
    --max-tokens "$MAX_TOKENS"
    --timeout-seconds "$TIMEOUT_SECONDS"
    --provider-max-attempts "$PROVIDER_MAX_ATTEMPTS"
    --provider-retry-delay-seconds "$PROVIDER_RETRY_DELAY_SECONDS"
    --stop-after-consecutive-provider-failures "$STOP_AFTER_CONSECUTIVE_PROVIDER_FAILURES"
  )
  if [[ "$EXTRA_BODY_JSON" != "{}" && -n "$EXTRA_BODY_JSON" ]]; then
    cmd+=(--extra-body-json "$EXTRA_BODY_JSON")
  fi
  if [[ "$NO_RESUME" == "1" ]]; then
    cmd+=(--no-resume)
  fi
  "${cmd[@]}"
}

import_evidence() {
  require_file "$BATCH"
  require_file "$RESULTS"
  env PYTHONPATH=src TG_QUESTION_CANONICALIZATION_PROMPT_VERSION="$PROMPT_VERSION" \
    python -m app evaluation tg-qa-canonicalization-import \
    --batch "$BATCH" \
    --results "$RESULTS" \
    --output "$EVIDENCE" \
    --manifest-output "$MANIFEST" \
    --canonicalization-run-id "$RUN_ID"
}

status() {
  for path in "$SUMMARY" "$CHECKPOINT" "$RUN_BUNDLE" "$MANIFEST"; do
    if [[ -f "$path" ]]; then
      echo "== $path"
      jq '{
        artifact_type,
        stage,
        model_id: (.model_id // .runtime_profile.model_id),
        prompt_version: (.prompt_version // .runtime_profile.prompt_version),
        runtime_profile_hash,
        canonicalization_batch_id,
        canonicalization_batch_hash: (.canonicalization_batch_hash // .runtime_profile.input_batch_hash),
        processed_count: (
          if has("processed_count") then .processed_count
          elif has("processed_task_ids") then (.processed_task_ids | length)
          else null
          end
        ),
        completed_count: (.completed_count // .status_counts.completed),
        failed_count: (.failed_count // .status_counts.failed),
        stopped_by_provider_failure_guard,
        trust_boundary
      } | with_entries(select(.value != null))' "$path"
    else
      echo "missing: $path"
    fi
  done
}

case "${1:-status}" in
  run) run ;;
  import) import_evidence ;;
  full)
    run
    import_evidence
    status
    ;;
  status) status ;;
  *)
    cat <<'USAGE' >&2
Usage:
  bash scripts/evaluation/run_007_v22_glm52_calibration_50.sh run
  bash scripts/evaluation/run_007_v22_glm52_calibration_50.sh import
  bash scripts/evaluation/run_007_v22_glm52_calibration_50.sh full
  bash scripts/evaluation/run_007_v22_glm52_calibration_50.sh status

This runner is limited to 100 records. It defaults to OpenCode glm-5.2 and
the v22 prompt profile. It creates private result, checkpoint, run-bundle, and
manifest artifacts; it does not finalize or promote output.
USAGE
    exit 2
    ;;
esac
