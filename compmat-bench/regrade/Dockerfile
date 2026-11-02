# CompMat-Bench v1.0.0 官方评分环境：Python 3.11、docs/evaluation.md 列出的基础科学计算包，
# 以及按 env/env_wannier90_grader 说明编译的 Wannier90 3.1.0 输入读取器。
FROM python:3.11-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends gfortran liblapack-dev libblas-dev make \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 构建上下文由 prepare.sh 准备：官方 builder 目录与 Wannier90 v3.1.0 源码包（builder 自行校验 SHA-256）。
COPY build/env_wannier90_grader /tmp/env_wannier90_grader
COPY build/wannier90-v3.1.0.tar.gz /tmp/wannier90-v3.1.0.tar.gz
RUN python3 /tmp/env_wannier90_grader/build_wannier90_grader.py \
      --source /tmp/wannier90-v3.1.0.tar.gz \
      --output /opt/compmat-grader/wannier90 --lapack='-llapack -lblas' \
 && rm -rf /tmp/env_wannier90_grader /tmp/wannier90-v3.1.0.tar.gz

ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /bench
