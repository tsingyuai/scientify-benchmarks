#!/usr/bin/env bash
# Independently regrade the Scientify CompMat-Bench submissions with the official v1.0.0 task graders.
# Requirements: docker, curl, unzip, sha256sum (or shasum), python3.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
WORK=${WORK:-"$HERE/work"}
REPO=${REPO:-tsingyuai/scientify-benchmarks}
SUBMISSIONS_TAG=${SUBMISSIONS_TAG:-compmat-bench-v1.0.0-submissions}
mkdir -p "$WORK"
cd "$WORK"

sha() { if command -v sha256sum >/dev/null; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }

echo "== 1/5 Official CompMat-Bench v1.0.0 release"
base=https://github.com/cz2014/CompMat-Bench/releases/download/v1.0.0
[ -f compmat_bench_core.zip ] || curl -fsSL -o compmat_bench_core.zip "$base/compmat_bench_core.zip"
curl -fsSL -o CHECKSUMS.sha256 "$base/CHECKSUMS.sha256"
grep ' compmat_bench_core.zip$' CHECKSUMS.sha256 | sha -c --quiet -
[ -d compmat_bench ] || unzip -q compmat_bench_core.zip

echo "== 2/5 Scientify submissions"
url=https://github.com/$REPO/releases/download/$SUBMISSIONS_TAG/compmat-bench-submissions.tar
[ -f compmat-bench-submissions.tar ] || curl -fsSL -o compmat-bench-submissions.tar "$url"
rm -rf submissions && mkdir submissions && tar -xf compmat-bench-submissions.tar -C submissions
(cd submissions && sha -c --quiet "$ROOT/SHA256SUMS")

echo "== 3/5 Grader image (Python 3.11 + Wannier90 3.1.0 input reader)"
rm -rf "$HERE/build" && mkdir -p "$HERE/build"
cp -R compmat_bench/env/env_wannier90_grader "$HERE/build/"
curl -fsSL -o "$HERE/build/wannier90-v3.1.0.tar.gz" \
  https://github.com/wannier-developers/wannier90/archive/refs/tags/v3.1.0.tar.gz
docker build -q -t compmat-grader:v1.0.0 "$HERE" >/dev/null

echo "== 4/5 Reference submissions must all score 1"
docker run --rm -v "$WORK/compmat_bench:/bench:ro" compmat-grader:v1.0.0 bash -c '
  fail=0
  for t in tasks/task_*_step_*; do
    s=$(python3 "$t/grader/grader.py" "$t/grader/reference_submission" 2>&1 | grep -E "^SCORE:" | tail -1)
    [ "$s" = "SCORE: 1" ] || { echo "reference failed: $t"; fail=1; }
  done
  exit $fail'

echo "== 5/5 Regrade Scientify submissions"
rm -rf grades && mkdir grades
docker run --rm -v "$WORK/compmat_bench:/bench:ro" -v "$WORK/submissions:/submissions:ro" \
  -v "$WORK/grades:/out" -v "$HERE/regrade.sh:/regrade.sh:ro" compmat-grader:v1.0.0 bash /regrade.sh \
  | grep -E '^task_' > regrade-summary.txt

python3 - "$ROOT/results.csv" regrade-summary.txt <<'PY'
import csv, sys
expected = {r['task_id']: int(r['score']) for r in csv.DictReader(open(sys.argv[1]))}
got = {}
for line in open(sys.argv[2]):
    task, _, score = line.split()
    got[task] = int(score)
diff = [t for t in expected if got.get(t) != expected[t]]
print(f"regraded {len(got)}/{len(expected)} tasks, passed {sum(got.values())}, "
      f"pass rate {100 * sum(got.values()) / len(expected):.2f}%")
print("matches results.csv" if not diff else f"MISMATCH: {diff}")
sys.exit(1 if diff else 0)
PY
