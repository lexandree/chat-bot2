#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

set -a
source .env
set +a

DATA_DIR="data/evaluation/tg_qa_canonicalization"
REGISTRY="${REGISTRY:-specs/007-legal-question-canonicalization/prompt-regression-cases.json}"
PROMPT_VERSION="${PROMPT_VERSION:-tg_question_canonicalizer_v22_positive}"
MODEL_ID="${MODEL_ID:-qwen3.6-plus}"
MODEL_LABEL="${MODEL_LABEL:-qwen36}"
PREFIX="${PREFIX:-real_data_007_prompt_regression_${PROMPT_VERSION}_${MODEL_LABEL}}"

BATCH="$DATA_DIR/${PREFIX}_batch.jsonl"
MANIFEST="$DATA_DIR/${PREFIX}_manifest.json"
RESULTS="$DATA_DIR/${PREFIX}_results.jsonl"
SUMMARY="$DATA_DIR/${PREFIX}_summary.json"
REPORT="$DATA_DIR/${PREFIX}_report.json"
REPORT_TSV="$DATA_DIR/${PREFIX}_report.tsv"
REPORT_HTML="$DATA_DIR/${PREFIX}_review.html"

BASELINE_RESULTS="${BASELINE_RESULTS:-$DATA_DIR/real_data_007_prompt_regression_accepted_${MODEL_LABEL}_results.jsonl}"
BASELINE_REPORT="${BASELINE_REPORT:-$DATA_DIR/real_data_007_prompt_regression_accepted_${MODEL_LABEL}_report.json}"
REVIEW_DECISIONS="${REVIEW_DECISIONS:-$DATA_DIR/${PREFIX}_review_decisions.jsonl}"
BASELINE_REVIEW_DECISIONS="${BASELINE_REVIEW_DECISIONS:-$DATA_DIR/real_data_007_prompt_regression_accepted_${MODEL_LABEL}_review_decisions.jsonl}"

ENDPOINT_URL="${ENDPOINT_URL:-$OPENCODE_CHAT_COMPLETIONS_URL}"
PROVIDER="${PROVIDER:-openai}"
STRUCTURED_OUTPUT_METHOD="${STRUCTURED_OUTPUT_METHOD:-json_mode}"
MAX_TOKENS="${MAX_TOKENS:-4096}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
PROVIDER_MAX_ATTEMPTS="${PROVIDER_MAX_ATTEMPTS:-3}"
PROVIDER_RETRY_DELAY_SECONDS="${PROVIDER_RETRY_DELAY_SECONDS:-15}"
STOP_AFTER_CONSECUTIVE_PROVIDER_FAILURES="${STOP_AFTER_CONSECUTIVE_PROVIDER_FAILURES:-3}"
EXTRA_BODY_JSON="${EXTRA_BODY_JSON-}"
if [[ -z "$EXTRA_BODY_JSON" ]]; then
  EXTRA_BODY_JSON='{"enable_thinking":false}'
fi
if ! EXTRA_BODY_JSON="$(jq -ce 'if type == "object" then . else error("expected JSON object") end' <<<"$EXTRA_BODY_JSON")"; then
  echo "Invalid EXTRA_BODY_JSON; expected one JSON object." >&2
  exit 2
fi

announce() {
  echo "LLM: $1"
  echo "OUT: $2"
}

prepare() {
  announce "cumulative prompt-regression batch prompt=$PROMPT_VERSION" "$BATCH"
  python scripts/evaluation/build_007_prompt_regression_suite.py \
    --registry "$REGISTRY" \
    --stage canonicalizer \
    --prompt-version "$PROMPT_VERSION" \
    --output "$BATCH" \
    --manifest-output "$MANIFEST"
}

run_canonicalizer() {
  local max_items
  max_items="$(wc -l < "$BATCH")"
  announce "$MODEL_ID cumulative prompt regression prompt=$PROMPT_VERSION items=$max_items" "$RESULTS"
  local -a cmd=(
    env
    PYTHONPATH=src
    TG_QUESTION_CANONICALIZATION_PROMPT_VERSION="$PROMPT_VERSION"
    python -m app evaluation tg-qa-canonicalization-llm-run
    --batch "$BATCH"
    --output "$RESULTS"
    --summary-output "$SUMMARY"
    --endpoint-url "$ENDPOINT_URL"
    --model-id "$MODEL_ID"
    --provider "$PROVIDER"
    --canonicalization-run-id "tg-question-canonicalization-run:${PREFIX}"
    --structured-output-method "$STRUCTURED_OUTPUT_METHOD"
    --api-key-env OPENCODE_API_KEY
    --max-items "$max_items"
    --max-tokens "$MAX_TOKENS"
    --timeout-seconds "$TIMEOUT_SECONDS"
    --provider-max-attempts "$PROVIDER_MAX_ATTEMPTS"
    --provider-retry-delay-seconds "$PROVIDER_RETRY_DELAY_SECONDS"
    --stop-after-consecutive-provider-failures "$STOP_AFTER_CONSECUTIVE_PROVIDER_FAILURES"
    --no-resume
  )
  if [[ -n "$EXTRA_BODY_JSON" && "$EXTRA_BODY_JSON" != "{}" ]]; then
    cmd+=(--extra-body-json "$EXTRA_BODY_JSON")
  fi
  "${cmd[@]}"
}

compare() {
  announce "cumulative prompt-regression comparison" "$REPORT_HTML"
  local -a baseline_args=()
  if [[ -f "$BASELINE_RESULTS" ]]; then
    baseline_args=(--baseline-results "$BASELINE_RESULTS")
  fi
  python scripts/evaluation/compare_007_prompt_regression.py \
    --manifest "$MANIFEST" \
    --results "$RESULTS" \
    "${baseline_args[@]}" \
    --output "$REPORT" \
    --tsv-output "$REPORT_TSV" \
    --html-output "$REPORT_HTML"
}

require_reviewed_regression_rows() {
  local required_task_ids accepted_task_ids missing_task_ids
  required_task_ids="$(jq -c '[.rows[] | select(.manual_review_required) | .task_id] | unique | sort' "$REPORT")"
  if [[ ! -f "$REVIEW_DECISIONS" ]]; then
    echo "Refusing to promote: review decision sidecar is required: $REVIEW_DECISIONS" >&2
    exit 2
  fi
  if [[ "$required_task_ids" == "[]" ]]; then
    return
  fi
  accepted_task_ids="$(jq -s -c '[.[] | select(.decision == "accept" or .decision == "approved") | .task_id] | map(select(. != null and . != "")) | unique | sort' "$REVIEW_DECISIONS")"
  missing_task_ids="$(jq -cn --argjson required "$required_task_ids" --argjson accepted "$accepted_task_ids" '$required - $accepted')"
  if [[ "$missing_task_ids" != "[]" ]]; then
    echo "Refusing to promote: manual-review rows lack accepted imported decisions: $missing_task_ids" >&2
    exit 2
  fi
}

promote_baseline() {
  if [[ "${CONFIRM_PROMOTE:-0}" != "1" ]]; then
    echo "Refusing to promote without CONFIRM_PROMOTE=1 after manual review." >&2
    exit 2
  fi
  if [[ ! -f "$REPORT" || ! -f "$RESULTS" ]]; then
    echo "Run compare first; missing $REPORT or $RESULTS" >&2
    exit 2
  fi
  local automatic_fail_count
  automatic_fail_count="$(jq -r '.counts.automatic_fail // 0' "$REPORT")"
  if [[ "$automatic_fail_count" != "0" ]]; then
    echo "Refusing to promote: automatic_fail=$automatic_fail_count" >&2
    exit 2
  fi
  require_reviewed_regression_rows
  cp "$RESULTS" "$BASELINE_RESULTS"
  cp "$REPORT" "$BASELINE_REPORT"
  cp "$REVIEW_DECISIONS" "$BASELINE_REVIEW_DECISIONS"
  echo "Promoted accepted baseline: $BASELINE_RESULTS"
}

status() {
  for path in "$MANIFEST" "$SUMMARY" "$REPORT" "$BASELINE_REPORT"; do
    if [[ -f "$path" ]]; then
      echo "== $path"
      jq '{
        selected_count,
        missing_count,
        historical_smoke_task_count,
        unregistered_historical_smoke_task_count,
        completed_count,
        failed_count,
        prompt_version,
        model_id,
        counts
      }' "$path"
    else
      echo "missing: $path"
    fi
  done
  echo "review_html: $REPORT_HTML"
  echo "review_decisions: $REVIEW_DECISIONS"
  echo "accepted_baseline: $BASELINE_RESULTS"
}

case "${1:-status}" in
  prepare) prepare ;;
  run) run_canonicalizer ;;
  compare) compare ;;
  promote-baseline) promote_baseline ;;
  status) status ;;
  full)
    prepare
    run_canonicalizer
    compare
    ;;
  *)
    cat <<'USAGE' >&2
Usage:
  bash scripts/evaluation/run_007_cumulative_prompt_regression.sh prepare
  bash scripts/evaluation/run_007_cumulative_prompt_regression.sh run
  bash scripts/evaluation/run_007_cumulative_prompt_regression.sh compare
  CONFIRM_PROMOTE=1 bash scripts/evaluation/run_007_cumulative_prompt_regression.sh promote-baseline
  bash scripts/evaluation/run_007_cumulative_prompt_regression.sh status
  bash scripts/evaluation/run_007_cumulative_prompt_regression.sh full

Set a new explicit PREFIX for every candidate prompt/model run. Promotion is
manual and updates the stable accepted baseline only after review.
USAGE
    exit 2
    ;;
esac
