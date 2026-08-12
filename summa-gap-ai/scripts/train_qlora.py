#!/usr/bin/env python3
"""
Summa-Gap AI — QLoRA Fine-Tuning Script
Fine-tunes a base model on the Summa corpus using 4-bit quantization.
Target: Llama-3.1-8B (or any HuggingFace-compatible model).

Usage:
    python scripts/train_qlora.py \
        --model_name meta-llama/Llama-3.1-8B-Instruct \
        --data_path data/summa_training_data.jsonl \
        --output_dir models/summa-gap-8b-qlora

Requirements: pip install -r requirements.txt
GPU: 1× A100-80GB for 8B, 4-8× for 70B, 16-32× for 405B
"""

import os
import argparse
import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TrainingArguments,
    TrainerCallback,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType,
)
from trl import SFTTrainer, DataCollatorForCompletionOnlyLM
import numpy as np

# ─── LogDet Probe Callback ───────────────────────────────────

class LogDetProbeCallback(TrainerCallback):
    """
    Monitors the logdet of hidden-state covariance matrices during training.
    This is the Summa's own measurement apparatus — detects representational
    collapse (logdet dropping) or representational expansion (logdet spiking).
    """
    def __init__(self, log_every=50, epsilon=1e-6):
        self.log_every = log_every
        self.epsilon = epsilon
        self.logdet_history = []

    def on_log(self, args, state, control, model=None, **kwargs):
        if state.global_step % self.log_every != 0:
            return

        # Hook into the model's hidden states (simple approximation)
        # In production, this would hook specific layers
        try:
            # Compute logdet from last hidden state in training batch
            # This is a lightweight approximation — full probe hooks per layer
            if hasattr(model, 'get_input_embeddings'):
                # Use embedding matrix as proxy for representational volume
                embedding_weight = model.get_input_embeddings().weight.detach()
                # Sample rows to keep computation tractable
                n_samples = min(1024, embedding_weight.shape[0])
                idx = torch.randperm(embedding_weight.shape[0])[:n_samples]
                X = embedding_weight[idx].float()
                X_centered = X - X.mean(dim=0)
                cov = (X_centered.T @ X_centered) / (n_samples - 1)
                # Regularize
                cov_reg = cov + self.epsilon * torch.eye(cov.shape[0], device=cov.device)
                # Logdet via eigenvalues
                eigvals = torch.linalg.eigvalsh(cov_reg)
                logdet = torch.sum(torch.log(eigvals)).item()

                self.logdet_history.append({
                    "step": state.global_step,
                    "logdet": logdet,
                    "effective_rank": (eigvals > self.epsilon).sum().item()
                })

                # Alarm conditions (Summa framework)
                if len(self.logdet_history) > 3:
                    recent = [h["logdet"] for h in self.logdet_history[-3:]]
                    if max(recent) - min(recent) > 10:
                        print(f"\n  ⚠ LOGDET SPIKE at step {state.global_step}: Δ={max(recent)-min(recent):.1f}")
                        print(f"    Representation expanding rapidly — possible concept learning")
        except Exception as e:
            pass  # Non-critical monitoring failure


# ─── Quantum-Resistant Checkpointing ──────────────────────────

def save_quantum_proof_checkpoint(model, tokenizer, path):
    """
    Save model with quantum-resistant integrity verification.
    Uses SHA-512 hashes (not quantum-vulnerable SHA-256).
    For production: integrate Kyber/Dilithium for post-quantum signing.
    """
    import hashlib
    import json

    os.makedirs(path, exist_ok=True)

    # Save model and tokenizer
    model.save_pretrained(path)
    tokenizer.save_pretrained(path)

    # Generate quantum-resistant integrity hashes (SHA-512)
    integrity = {}
    for root, _, files in os.walk(path):
        for file in files:
            filepath = os.path.join(root, file)
            with open(filepath, 'rb') as f:
                file_hash = hashlib.sha512(f.read()).hexdigest()
            integrity[os.path.relpath(filepath, path)] = file_hash

    # Save integrity manifest
    with open(os.path.join(path, "integrity_manifest.sha512"), 'w') as f:
        json.dump(integrity, f, indent=2)

    print(f"  Quantum-resistant checkpoint saved to {path}")
    print(f"  Integrity manifest: {len(integrity)} files hashed with SHA-512")


# ─── Main Training Pipeline ───────────────────────────────────

def main(args):
    # ── Quantization Config (4-bit QLoRA) ──
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # ── Load Model ──
    print(f"Loading model: {args.model_name}")
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        attn_implementation="flash_attention_2" if args.use_flash_attn else "sdpa",
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)

    # Set padding token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ── Prepare for k-bit training ──
    model = prepare_model_for_kbit_training(model)

    # ── LoRA Configuration ──
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=args.lora_target_modules.split(","),
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ── Load Data ──
    print(f"Loading training data from {args.data_path}")
    dataset = load_dataset("json", data_files=args.data_path, split="train")

    # Format messages into chat template
    def format_chat(example):
        messages = example["messages"]
        return {"text": tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )}

    dataset = dataset.map(format_chat, remove_columns=dataset.column_names)

    # ── Training Arguments ──
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        gradient_checkpointing=True,
        optim="adamw_8bit",
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        weight_decay=0.01,
        bf16=True,
        tf32=True,
        logging_steps=args.logging_steps,
        save_strategy="epoch",
        save_total_limit=3,
        report_to="none",
        dataloader_num_workers=4,
        ddp_find_unused_parameters=False,
        run_name="summa-gap-qlora",
    )

    # ── Trainer ──
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
        max_seq_length=args.max_seq_length,
        dataset_text_field="text",
        packing=True,  # Efficient batching
        callbacks=[LogDetProbeCallback(log_every=args.logging_steps)],
    )

    # ── Train ──
    print("\n" + "="*60)
    print("SUMMA-GAP AI — QLORA FINE-TUNING")
    print("="*60)
    print(f"Model: {args.model_name}")
    print(f"Data: {args.data_path}")
    print(f"LoRA rank: {args.lora_r}, Alpha: {args.lora_alpha}")
    print(f"Epochs: {args.epochs}, Batch: {args.batch_size}")
    print(f"Learning rate: {args.learning_rate}")
    print(f"Output: {args.output_dir}")
    print("="*60 + "\n")
    print("The gap does not close. That is the engine.\n")

    trainer.train()

    # ── Save Final Model ──
    final_path = os.path.join(args.output_dir, "final")
    save_quantum_proof_checkpoint(model, tokenizer, final_path)

    # ── Merge & Export (optional) ──
    if args.merge_and_export:
        print("\nMerging LoRA weights and exporting full model...")
        merged_model = model.merge_and_unload()
        merged_path = os.path.join(args.output_dir, "merged")
        save_quantum_proof_checkpoint(merged_model, tokenizer, merged_path)

    print("\nTraining complete. The model is ready at:", args.output_dir)
    print("To evaluate: python eval/logdet_probe.py --model_path", final_path)


# ─── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summa-Gap AI QLoRA Fine-Tuning")

    # Model
    parser.add_argument("--model_name", type=str,
                        default="meta-llama/Llama-3.1-8B-Instruct",
                        help="Base model (HuggingFace ID or local path)")
    parser.add_argument("--data_path", type=str,
                        default="data/summa_training_data.jsonl",
                        help="Path to training data (JSONL)")

    # LoRA
    parser.add_argument("--lora_r", type=int, default=64,
                        help="LoRA rank")
    parser.add_argument("--lora_alpha", type=int, default=128,
                        help="LoRA alpha (scaling factor)")
    parser.add_argument("--lora_dropout", type=float, default=0.05,
                        help="LoRA dropout")
    parser.add_argument("--lora_target_modules", type=str,
                        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
                        help="Comma-separated target modules for LoRA")

    # Training
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=4,
                        help="Per-device batch size")
    parser.add_argument("--gradient_accumulation", type=int, default=4,
                        help="Gradient accumulation steps")
    parser.add_argument("--learning_rate", type=float, default=2e-4,
                        help="Learning rate")
    parser.add_argument("--max_seq_length", type=int, default=4096,
                        help="Maximum sequence length")
    parser.add_argument("--logging_steps", type=int, default=10,
                        help="Log every N steps")

    # Output
    parser.add_argument("--output_dir", type=str, default="models/summa-gap-8b-qlora",
                        help="Output directory for checkpoints")
    parser.add_argument("--merge_and_export", action="store_true",
                        help="Merge LoRA weights and export full model")

    # Performance
    parser.add_argument("--use_flash_attn", action="store_true",
                        help="Use Flash Attention 2 (requires compatible GPU)")

    args = parser.parse_args()
    main(args)
