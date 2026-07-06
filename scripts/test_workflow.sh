#!/bin/bash
# Run a suite of workflow-agent tests via `azd ai agent invoke`.
#
# Usage:
#   ./scripts/test_workflow.sh
#   ./scripts/test_workflow.sh --local
#   ./scripts/test_workflow.sh --agent hosted-agentframework-workflow
#   ./scripts/test_workflow.sh --version 3
#
# Optional env vars:
#   AGENT_NAME                 Default: hosted-agentframework-workflow
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

AGENT_NAME="${AGENT_NAME:-hosted-agentframework-workflow}"
LOCAL_MODE=0
AGENT_VERSION=""
TIMEOUT_SECS=180
OUTPUT_BASE="${TEST_OUTPUT_DIR:-$SCRIPT_DIR/test_output_workflow}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$OUTPUT_BASE/$TIMESTAMP"
SUMMARY_FILE="$RUN_DIR/summary.txt"

print_usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --local                 Invoke local agent (azd ai agent run must be active)
  --agent <name>          Agent name to invoke (default: $AGENT_NAME)
  --version <v>           Hosted agent version to invoke
  --timeout <seconds>     Timeout per invoke (default: $TIMEOUT_SECS)
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      LOCAL_MODE=1
      shift
      ;;
    --agent)
      AGENT_NAME="${2:-}"
      if [[ -z "$AGENT_NAME" ]]; then
        echo "ERROR: --agent requires a value"
        exit 1
      fi
      shift 2
      ;;
    --version)
      AGENT_VERSION="${2:-}"
      if [[ -z "$AGENT_VERSION" ]]; then
        echo "ERROR: --version requires a value"
        exit 1
      fi
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECS="${2:-}"
      if [[ -z "$TIMEOUT_SECS" ]]; then
        echo "ERROR: --timeout requires a value"
        exit 1
      fi
      shift 2
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
if [[ -n "$AGENT_VERSION" ]]; then
  echo "Version: $AGENT_VERSION" | tee -a "$SUMMARY_FILE"
fi
echo "Timeout per test: ${TIMEOUT_SECS}s" | tee -a "$SUMMARY_FILE"
echo "" | tee -a "$SUMMARY_FILE"

TEST_NAMES=()
TEST_PROMPTS=()
TEST_NEW_SESSION=()

add_test() {
  TEST_NAMES+=("$1")
  TEST_PROMPTS+=("$2")
  TEST_NEW_SESSION+=("$3")
}

add_test "Workflow basic formatting" "Write a short article (2 paragraphs) about electric bikes for city commuting." "0"
add_test "Workflow technical topic" "Write a short article (2 paragraphs) explaining retrieval augmented generation for a beginner audience." "0"
add_test "Workflow structure request" "Write a short article about remote work best practices and include a small bullet list of 4 practical tips." "0"
add_test "Workflow creativity" "Write a short article about why community gardens matter in cities." "0"
add_test "Workflow new session" "Write a short article about ocean conservation and end with one action item readers can take today." "1"
add_test "Workflow concise response" "Write a very concise short article about healthy sleep habits for software engineers." "0"

build_cmd() {
  local prompt="$1"
  local new_session="$2"
  local cmd=("azd")

  if [[ -n "${AZD_ENV:-}" ]]; then
    cmd+=("-e" "$AZD_ENV")
  fi

  cmd+=("ai" "agent" "invoke")

  if [[ $LOCAL_MODE -eq 1 ]]; then
    cmd+=("--local")
    cmd+=("$prompt")
  else
    cmd+=("$AGENT_NAME")
    cmd+=("$prompt")
  fi

  if [[ "$new_session" == "1" ]]; then
    cmd+=("--new-session")
  fi

  if [[ -n "$AGENT_VERSION" ]]; then
    cmd+=("--version" "$AGENT_VERSION")
  fi

  cmd+=("--timeout" "$TIMEOUT_SECS")

  printf '%q ' "${cmd[@]}"
}

pass_count=0
fail_count=0

for i in "${!TEST_NAMES[@]}"; do
  idx=$((i + 1))
  name="${TEST_NAMES[$i]}"
  prompt="${TEST_PROMPTS[$i]}"
  new_session="${TEST_NEW_SESSION[$i]}"

  out_file="$RUN_DIR/test_${idx}.out.txt"
  err_file="$RUN_DIR/test_${idx}.err.txt"

  echo "[$idx/${#TEST_NAMES[@]}] $name" | tee -a "$SUMMARY_FILE"
  echo "Prompt: $prompt" > "$RUN_DIR/test_${idx}.prompt.txt"
  echo "New session: $new_session" >> "$RUN_DIR/test_${idx}.prompt.txt"

  cmd_string="$(build_cmd "$prompt" "$new_session")"

  # shellcheck disable=SC2086
  eval "$cmd_string" >"$out_file" 2>"$err_file"
  exit_code=$?

  status="PASS"
  if [[ $exit_code -ne 0 ]]; then
    status="FAIL"
  elif grep -Eiq "429|rate[ -]?limit( exceeded)?|too many requests|throttl(ed|ing)|service failed|Traceback|Exception" "$out_file" "$err_file"; then
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
