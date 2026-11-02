"""Build CompMat-Bench result tables and charts from official grader outputs.

Usage: python3 build_results.py <compmat_bench release dir> <grader output dir> <submissions dir> <repo compmat-bench dir>
"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

release, grades, subs, out = map(Path, sys.argv[1:5])

# Run metadata recorded by the Scientify harness for each task (final attempt number and format repairs).
meta = json.loads((out / 'tools' / 'run_metadata.json').read_text())

BASELINES = [  # official full94 pass counts, trajectory_manifest.json of the v1.0.0 release
    ('Codex (GPT-5.6)', 86),
    ('GPT-5.6-sol', 85),
    ('Gemini 3.8 Flash', 84),
    ('DeepSeek V4.1 Flash', 62),
]


def yaml_field(text, key):
    m = re.search(rf'^{key}: (.*)$', text, re.M)
    return m.group(1).strip() if m else ''


def count_checks(node):
    """Count every grader check object (a dict carrying a boolean `passed`), including nested ones."""
    passed = total = 0
    if isinstance(node, dict):
        if isinstance(node.get('passed'), bool):
            passed, total = int(node['passed']), 1
        for v in node.values():
            p, t = count_checks(v)
            passed += p
            total += t
    elif isinstance(node, list):
        for v in node:
            p, t = count_checks(v)
            passed += p
            total += t
    return passed, total


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


rows = []
for task_dir in sorted(release.glob('tasks/task_*_step_*')):
    tid = task_dir.name
    spec = (task_dir / 'task.yaml').read_text()
    text = (grades / f'{tid}.txt').read_text()
    score = int(re.findall(r'^SCORE:\s*([01])\s*$', text, re.M)[-1])
    body = text[: text.rfind('SCORE:')]
    start = body.find('{')
    report = json.loads(body[start: body.rfind('}') + 1])
    passed, total = count_checks(report)
    archive = subs / f'{tid}.tar.gz'
    task_out = out / 'tasks' / tid
    task_out.mkdir(parents=True, exist_ok=True)
    (task_out / 'grade.txt').write_text(text)
    rows.append({
        'task_id': tid,
        'title': yaml_field(spec, 'title'),
        'role': yaml_field(spec, 'role'),
        'codes': [c.strip() for c in yaml_field(spec, 'codes').strip('[]').split(',') if c.strip()],
        'source_date': yaml_field(spec, 'source_date'),
        'score': score,
        'checks_passed': passed,
        'checks_total': total,
        'final_attempt': meta['final_attempt'][tid],
        'format_repair': meta['format_repairs'].get(tid),
        'submission_sha256': sha256(archive),
        'submission_bytes': archive.stat().st_size,
    })

n_pass = sum(r['score'] for r in rows)
summary = {
    'benchmark': 'CompMat-Bench',
    'version': 'v1.0.0',
    'split': 'single-step (full94)',
    'tasks': len(rows),
    'passed': n_pass,
    'pass_rate_percent': round(100 * n_pass / len(rows), 2),
    'checks_passed': sum(r['checks_passed'] for r in rows),
    'checks_total': sum(r['checks_total'] for r in rows),
    'baselines': [{'name': n, 'passed': p, 'pass_rate_percent': round(100 * p / 94, 2)} for n, p in BASELINES],
}
(out / 'results.json').write_text(json.dumps({'summary': summary, 'tasks': rows}, indent=2, ensure_ascii=False) + '\n')
with open(out / 'results.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['task_id', 'role', 'codes', 'score', 'checks_passed', 'checks_total', 'final_attempt', 'format_repair', 'submission_sha256'])
    for r in rows:
        w.writerow([r['task_id'], r['role'], ' '.join(r['codes']), r['score'], r['checks_passed'], r['checks_total'], r['final_attempt'], 'yes' if r['format_repair'] else '', r['submission_sha256']])
(out / 'SHA256SUMS').write_text(''.join(f"{r['submission_sha256']}  {r['task_id']}.tar.gz\n" for r in rows))

# ---- charts: white card background so they read in both GitHub themes ----
ACCENT, MUTED, TRACK, INK, INK2 = '#2563eb', '#9ca3af', '#eef0f3', '#111827', '#6b7280'
FONT = "font-family='-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif'"
assets = out / 'assets'
assets.mkdir(exist_ok=True)

bars = [('Scientify', n_pass)] + BASELINES
W, left, right, top, rowh = 760, 170, 70, 64, 40
H = top + rowh * len(bars) + 52
svg = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}' {FONT}>",
       f"<rect width='{W}' height='{H}' rx='12' fill='#ffffff' stroke='#e5e7eb'/>",
       f"<text x='24' y='34' font-size='17' font-weight='600' fill='{INK}'>CompMat-Bench v1.0.0 · single-step pass rate (94 tasks)</text>"]
span = W - left - right
for i, (name, p) in enumerate(bars):
    y = top + i * rowh
    pct = 100 * p / 94
    me = name == 'Scientify'
    svg.append(f"<text x='{left - 14}' y='{y + 15}' font-size='14' text-anchor='end' fill='{INK if me else INK2}' font-weight='{600 if me else 400}'>{name}</text>")
    svg.append(f"<rect x='{left}' y='{y + 3}' width='{span}' height='16' rx='4' fill='{TRACK}'/>")
    svg.append(f"<rect x='{left}' y='{y + 3}' width='{span * pct / 100:.1f}' height='16' rx='4' fill='{ACCENT if me else MUTED}'><title>{name}: {p}/94 = {pct:.2f}%</title></rect>")
    svg.append(f"<text x='{W - right + 10}' y='{y + 15}' font-size='14' fill='{INK if me else INK2}' font-weight='{600 if me else 400}'>{pct:.2f}%</text>")
svg.append(f"<text x='24' y='{H - 32}' font-size='12' fill='{INK2}'>Baselines: official full94 trajectories published with the CompMat-Bench v1.0.0 release.</text>")
svg.append(f"<text x='24' y='{H - 14}' font-size='12' fill='{INK2}'>Scientify: official task graders run on the submissions in this repository.</text>")
svg.append('</svg>')
(assets / 'leaderboard.svg').write_text('\n'.join(svg))

# 94-task grid: one cell per task, grouped by task role; failures carry an × so the state is not colour-only.
groups = [('analyze', 'Analyse computed data'), ('gen_input', 'Prepare simulation inputs')]
cell, gap, per_row, gx = 22, 4, 24, 24
W2 = gx * 2 + per_row * (cell + gap)
y = 60
parts = []
for role, label in groups:
    items = [r for r in rows if r['role'] == role]
    ok = sum(r['score'] for r in items)
    parts.append(f"<text x='{gx}' y='{y}' font-size='14' font-weight='600' fill='{INK}'>{label}</text>")
    parts.append(f"<text x='{W2 - gx}' y='{y}' font-size='14' text-anchor='end' fill='{INK2}'>{ok}/{len(items)} passed</text>")
    y += 12
    for i, r in enumerate(items):
        cx = gx + (i % per_row) * (cell + gap)
        cy = y + (i // per_row) * (cell + gap)
        tip = f"{r['task_id']} · {r['checks_passed']}/{r['checks_total']} checks · score {r['score']}"
        if r['score']:
            parts.append(f"<rect x='{cx}' y='{cy}' width='{cell}' height='{cell}' rx='4' fill='{ACCENT}'><title>{tip}</title></rect>")
        else:
            parts.append(f"<rect x='{cx}' y='{cy}' width='{cell}' height='{cell}' rx='4' fill='#ffffff' stroke='{MUTED}' stroke-width='1.5'><title>{tip}</title></rect>")
            parts.append(f"<text x='{cx + cell / 2}' y='{cy + 16}' font-size='14' text-anchor='middle' fill='{INK2}'>×</text>")
    y += ((len(items) - 1) // per_row + 1) * (cell + gap) + 30
H2 = y + 10
svg2 = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W2}' height='{H2}' viewBox='0 0 {W2} {H2}' {FONT}>",
        f"<rect width='{W2}' height='{H2}' rx='12' fill='#ffffff' stroke='#e5e7eb'/>",
        f"<text x='{gx}' y='34' font-size='17' font-weight='600' fill='{INK}'>All 94 tasks · filled = passed, × = failed</text>"] + parts + ['</svg>']
(assets / 'task-grid.svg').write_text('\n'.join(svg2))
print(json.dumps(summary, indent=2))
