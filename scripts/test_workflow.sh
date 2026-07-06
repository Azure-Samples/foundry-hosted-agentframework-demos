#!/bin/bash
# Run a suite of workflow-agent tests via `azd ai agent invoke`.
#
# Usage:
#   ./scripts/test_workflow.sh
#   ./scripts/test_workflow.sh --local
#
# Optional env vars:
#   AZD_ENV                    Passed to `azd -e <env>` when set
#   TEST_OUTPUT_DIR            Default: ./scripts/test_output_workflow

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v azd >/dev/null 2>&1; then
  echo "ERROR: azd not found in PATH"
  exit 1
fi

AGENT_NAME="hosted-agentframework-workflow"
LOCAL_MODE=0
OUTPUT_BASE="${TEST_OUTPUT_DIR:-$SCRIPT_DIR/test_output_workflow}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$OUTPUT_BASE/$TIMESTAMP"
SUMMARY_FILE="$RUN_DIR/summary.txt"
WARN_PATTERN='(^|[^[:alnum:]])429([^[:alnum:]]|$)|rate[ -]?limit( exceeded)?|too many requests|throttl(ed|ing)|service failed|Traceback|Exception:|^\s*File "'

print_usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --local                 Invoke local agent (azd ai agent run must be active)
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      LOCAL_MODE=1
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1"
      print_usage
      exit 1
      ;;
  esac
done

mkdir -p "$RUN_DIR"

echo "Workflow test run: $TIMESTAMP" | tee "$SUMMARY_FILE"
echo "Run directory: $RUN_DIR" | tee -a "$SUMMARY_FILE"
echo "Agent: $AGENT_NAME" | tee -a "$SUMMARY_FILE"
echo "Mode: $([[ $LOCAL_MODE -eq 1 ]] && echo local || echo hosted)" | tee -a "$SUMMARY_FILE"
echo "" | tee -a "$SUMMARY_FILE"

TEST_NAMES=()
TEST_PROMPTS=()

add_test() {
  TEST_NAMES+=("$1")
  TEST_PROMPTS+=("$2")
}

add_test "Workflow structure request" "Write a short article about remote work best practices and include a small bullet list of 4 practical tips."
add_test "Workflow action item ending" "Write a short article about ocean conservation and end with one action item readers can take today."
add_test "Workflow concise response" "Write a very concise short article about healthy sleep habits for software engineers."

build_cmd() {
  local prompt="$1"
  CMD=("azd")

  if [[ -n "${AZD_ENV:-}" ]]; then
    CMD+=("-e" "$AZD_ENV")
  fi

  CMD+=("ai" "agent" "invoke")

  if [[ $LOCAL_MODE -eq 1 ]]; then
    CMD+=("--local")
  else
    CMD+=("$AGENT_NAME")
  fi

  CMD+=("$prompt")
}

pass_count=0
fail_count=0

for i in "${!TEST_NAMES[@]}"; do
  idx=$((i + 1))
  name="${TEST_NAMES[$i]}"
  prompt="${TEST_PROMPTS[$i]}"

  out_file="$RUN_DIR/test_${idx}.out.txt"
  err_file="$RUN_DIR/test_${idx}.err.txt"

  echo "[$idx/${#TEST_NAMES[@]}] $name" | tee -a "$SUMMARY_FILE"
  echo "Prompt: $prompt" > "$RUN_DIR/test_${idx}.prompt.txt"

  build_cmd "$prompt"
  "${CMD[@]}" >"$out_file" 2>"$err_file"
  exit_code=$?

  status="PASS"
  if [[ $exit_code -ne 0 ]]; then
    status="FAIL"
  elif grep -Eiq "$WARN_PATTERN" "$out_file" "$err_file"; then
    status="WARN"
  fi

  case "$status" in
    PASS)
      pass_count=$((pass_count + 1))
      ;;
    WARN)
      fail_count=$((fail_count + 1))
      ;;
    FAIL)
      fail_count=$((fail_count + 1))
      ;;
  esac

  echo "Result: $status (exit=$exit_code)" | tee -a "$SUMMARY_FILE"
  if [[ "$status" != "PASS" ]]; then
    echo "See: $out_file and $err_file" | tee -a "$SUMMARY_FILE"
  fi
  echo "" | tee -a "$SUMMARY_FILE"
done

echo "Done. PASS=$pass_count FAIL_OR_WARN=$fail_count" | tee -a "$SUMMARY_FILE"
echo "Summary: $SUMMARY_FILE"

if [[ $fail_count -gt 0 ]]; then
  exit 1
fi

exit 0
