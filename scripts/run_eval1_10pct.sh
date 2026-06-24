#!/usr/bin/env bash
set -euo pipefail

clause-eval ingest \
  --data data/raw/clause/datasets \
  --output data/splits/all_instances.jsonl

clause-eval make-splits \
  --input data/splits/all_instances.jsonl \
  --dev-output data/splits/dev.jsonl \
  --test-output data/splits/test.jsonl \
  --test-fraction 0.30 \
  --seed 42

clause-eval sample \
  --input data/splits/test.jsonl \
  --output data/splits/test_10pct_stratified.jsonl \
  --fraction 0.10 \
  --seed 42

clause-eval build-eval1 \
  --input data/splits/test_10pct_stratified.jsonl \
  --output data/eval/eval1_test_10pct.jsonl \
  --seed 42

clause-eval run \
  --input data/eval/eval1_test_10pct.jsonl \
  --output runs/eval1_mock_predictions.jsonl \
  --task eval1 \
  --provider mock \
  --model mock \
  --temperature 0

clause-eval metrics \
  --input runs/eval1_mock_predictions.jsonl \
  --task eval1 \
  --output reports/eval1_mock_metrics.json

clause-eval bootstrap \
  --input runs/eval1_mock_predictions.jsonl \
  --task eval1 \
  --output reports/eval1_mock_bootstrap.json \
  --n-bootstrap 5000 \
  --seed 42
