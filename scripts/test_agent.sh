#!/bin/bash
# Run a suite of agent tool-path tests via `azd ai agent invoke`.
#
# Usage:
#   ./scripts/test_agent.sh
#   ./scripts/test_agent.sh --local
#
# Optional env vars:
#   AZD_ENV                    Passed to `azd -e <env>` when set
#   TEST_OUTPUT_DIR            Default: ./scripts/test_output_agent

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v azd >/dev/null 2>&1; then
  echo "ERROR: azd not found in PATH"
  exit 1
fi

AGENT_NAME="hosted-agentframework-agent"
LOCAL_MODE=0
OUTPUT_BASE="${TEST_OUTPUT_DIR:-$SCRIPT_DIR/test_output_agent}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$OUTPUT_BASE/$TIMESTAMP"
SUMMARY_FILE="$RUN_DIR/summary.txt"

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

echo "Agent test run: $TIMESTAMP" | tee "$SUMMARY_FILE"
echo "Run directory: $RUN_DIR" | tee -a "$SUMMARY_FILE"
echo "Agent: $AGENT_NAME" | tee -a "$SUMMARY_FILE"
echo "Mode: $([[ $LOCAL_MODE -eq 1 ]] && echo local || echo hosted)" | tee -a "$SUMMARY_FILE"
echo "" | tee -a "$SUMMARY_FILE"

# Query catalog
TEST_NAMES=()
TEST_PROMPTS=()

add_test() {
  TEST_NAMES+=("$1")
  TEST_PROMPTS+=("$2")
}

add_test "KB plan comparison" "What are the main differences between Northwind Health Plus and Northwind Standard? Include emergency, mental health, and out-of-network coverage."
add_test "KB numeric details" "Under Northwind Health Plus, what are the office visit copays for primary care, specialist, and mental health visits?"
add_test "KB appeals workflow" "How do appeals work for Northwind Health Plus, including deadlines and what to submit?"
add_test "Custom date tool" "What is today's date? Return only ISO format."
add_test "Custom deadline tool" "What are the enrollment open and close dates for benefits this year?"
add_test "Custom tools together" "Given today's date and enrollment deadlines, am I currently in the enrollment window? Show your reasoning briefly."
add_test "Web search HSA" "What are the 2026 IRS HSA contribution limits for self-only and family coverage? Please use current public sources and cite them."
add_test "Web plus internal" "Based on our Zava benefits guidance and current public guidance, what should an employee consider before choosing HDHP + HSA vs PPO?"
add_test "Code interpreter table" "Create a simple comparison table of expected annual employee cost for three scenarios: A) 10 primary care visits B) 4 specialist visits C) 2 urgent care visits. Use plan copays from the available benefits docs where possible, and show assumptions clearly."
add_test "Code interpreter sensitivity" "Run a sensitivity analysis for annual out-of-pocket spend from 0 to 20 specialist visits for Northwind Health Plus, using known copays and clearly labeled assumptions. Return a compact table."
add_test "Multi-tool orchestration" "I need to decide by enrollment close. Summarize deadlines, key plan differences, and any missing external info you can verify online. Then give me a 5-step decision checklist."
add_test "Uncertain response behavior" "What is Zava's fertility benefit lifetime maximum in dollars? If you cannot verify from internal docs, say so clearly and suggest where to confirm."

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
  elif grep -Eiq "rate limit|429|throttl|service failed" "$out_file" "$err_file"; then
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
