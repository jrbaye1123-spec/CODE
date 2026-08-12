#!/bin/bash
# Summa-Gap AI — Master Build Script
# Complete pipeline from data preparation to inference server.
# Run: bash scripts/build_all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "============================================"
echo "SUMMA-GAP AI — BUILD PIPELINE"
echo "============================================"
echo "Project: $PROJECT_DIR"
echo ""

# Step 1: Install dependencies
echo "[1/5] Installing dependencies..."
pip install -r requirements.txt
echo "  Done."
echo ""

# Step 2: Prepare training data
echo "[2/5] Preparing training data..."
python3 scripts/prepare_data.py
echo "  Done."
echo ""

# Step 3: Train model (QLoRA)
echo "[3/5] Training model (QLoRA fine-tuning)..."
echo "  This step requires GPU access."
echo "  For single GPU (A100-80GB):"
echo "    python3 scripts/train_qlora.py --batch_size 4 --gradient_accumulation 4"
echo "  For 8x GPU:"
echo "    accelerate launch scripts/train_qlora.py --batch_size 8"
echo ""
echo "  Uncomment below to run automatically:"
echo "  # python3 scripts/train_qlora.py"
echo ""

# Step 4: Evaluate with logdet probe
echo "[4/5] Running logdet probe evaluation..."
python3 eval/logdet_probe.py --calibration_only
echo "  Done."
echo ""

# Step 5: Start quantum-proof server
echo "[5/5] Starting quantum-resistant inference server..."
echo "  python3 deploy/quantum_proof_wrapper.py --model_path models/summa-gap-8b-qlora/final"
echo ""

echo "============================================"
echo "BUILD PIPELINE SUMMARY"
echo "============================================"
echo ""
echo "Project directory: $PROJECT_DIR"
echo ""
echo "Structure:"
echo "  data/        — Training data (JSONL)"
echo "  scripts/     — Data prep + training"
echo "  eval/        — LogDet probe evaluation"
echo "  deploy/      — Quantum-proof server"
echo "  models/      — Trained checkpoints"
echo "  configs/     — Training configurations"
echo ""
echo "Quick start:"
echo "  1. Set HF_TOKEN for gated models"
echo "  2. Run: python3 scripts/prepare_data.py"
echo "  3. Run: python3 scripts/train_qlora.py"
echo "  4. Run: python3 eval/logdet_probe.py"
echo "  5. Run: python3 deploy/quantum_proof_wrapper.py"
echo ""
echo "The gap does not close. That is the engine."
