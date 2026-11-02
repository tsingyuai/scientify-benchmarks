#!/usr/bin/env bash
# 在容器内运行：逐题解压 submissions/<task_id>.tar.gz，用官方 grader 评分，结果写入 /out/<task_id>.txt。
set -u
cd /bench
for archive in /submissions/*.tar.gz; do
  task=$(basename "$archive" .tar.gz)
  work=$(mktemp -d)
  tar -xzf "$archive" -C "$work"
  timeout 600 python3 "tasks/$task/grader/grader.py" "$work" > "/out/$task.txt" 2>&1
  echo "$task $(grep -E '^SCORE:' "/out/$task.txt" | tail -1)"
  rm -rf "$work"
done
