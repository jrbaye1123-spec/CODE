"""
Fine-tune GPT-2 on vault training data.
398 instruction pairs → 3 epochs → vault-knowledgeable model.

Runs on CPU. Takes ~20 minutes for gpt2-medium.
"""

import json
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)
from torch.optim import AdamW

# ── Config ───────────────────────────────────────────────────────────
MODEL_NAME = "gpt2"  # 124M params — CPU-trainable
TRAINING_FILE = Path.home() / "gpt2_moe_1m/vault_rag/training_data/chat_tuning.jsonl"
OUTPUT_DIR = Path.home() / "gpt2_moe_1m/vault-gpt-finetuned"

EPOCHS = 3
BATCH_SIZE = 1  # CPU-friendly
GRADIENT_ACCUMULATION = 8  # effective batch = 8
LEARNING_RATE = 5e-5
WARMUP_STEPS = 20
MAX_LENGTH = 512  # shorter sequences = faster training, less memory
SAVE_STEPS = 100

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[finetune] Device: {device}", file=sys.stderr)


# ── Load training data ───────────────────────────────────────────────

class VaultDataset(Dataset):
    """Tokenized vault instruction pairs."""

    def __init__(self, jsonl_path: Path, tokenizer, max_length: int):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.examples = []

        with open(jsonl_path) as f:
            for line in f:
                data = json.loads(line)
                msgs = data["messages"]
                # Format: Instruction + Response
                text = (
                    f"### Instruction: {msgs[1]['content']}\n"
                    f"### Response: {msgs[2]['content']}"
                )
                self.examples.append(text)

        print(f"[finetune] Loaded {len(self.examples)} training examples", file=sys.stderr)

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        text = self.examples[idx]
        tokens = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        input_ids = tokens["input_ids"].squeeze(0)
        attention_mask = tokens["attention_mask"].squeeze(0)
        # Labels = input_ids (causal LM)
        labels = input_ids.clone()
        labels[attention_mask == 0] = -100  # ignore padding
        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


# ── Fine-tune ────────────────────────────────────────────────────────

def finetune(epochs=None, resume_from=None):
    if epochs is None:
        epochs = EPOCHS
    print(f"[finetune] Loading {MODEL_NAME}...", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.pad_token = tokenizer.eos_token

    if resume_from:
        print(f"[finetune] Resuming from {resume_from}", file=sys.stderr)
        model = AutoModelForCausalLM.from_pretrained(
            resume_from,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
        ).to(device)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float32,  # CPU-safe
            low_cpu_mem_usage=True,
        ).to(device)

    dataset = VaultDataset(TRAINING_FILE, tokenizer, MAX_LENGTH)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE)
    total_steps = (len(dataloader) // GRADIENT_ACCUMULATION) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=WARMUP_STEPS,
        num_training_steps=total_steps,
    )

    model.train()
    global_step = 0
    total_loss = 0.0
    t0 = time.time()

    print(f"[finetune] Training {epochs} epochs, "
          f"{len(dataloader)} steps/epoch, "
          f"batch={BATCH_SIZE}×{GRADIENT_ACCUMULATION}", file=sys.stderr)
    print(f"[finetune] Estimated time: ~20 min on CPU", file=sys.stderr)

    for epoch in range(epochs):
        epoch_loss = 0.0
        optimizer.zero_grad()

        for step, batch in enumerate(dataloader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            loss = outputs.loss / GRADIENT_ACCUMULATION
            loss.backward()

            epoch_loss += loss.item()

            if (step + 1) % GRADIENT_ACCUMULATION == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1

                if global_step % 50 == 0:
                    elapsed = time.time() - t0
                    avg_loss = total_loss / global_step if global_step > 0 else 0
                    print(f"  step {global_step}/{total_steps} | "
                          f"loss: {avg_loss:.4f} | "
                          f"{elapsed:.0f}s elapsed", file=sys.stderr)

            total_loss += loss.item()

            if global_step > 0 and global_step % SAVE_STEPS == 0:
                checkpoint_dir = OUTPUT_DIR / f"checkpoint-{global_step}"
                model.save_pretrained(checkpoint_dir)
                tokenizer.save_pretrained(checkpoint_dir)
                print(f"  saved checkpoint to {checkpoint_dir}", file=sys.stderr)

        avg_epoch_loss = epoch_loss / len(dataloader)
        print(f"  epoch {epoch+1}/{epochs} complete | avg loss: {avg_epoch_loss:.4f}",
              file=sys.stderr)

    # ── Save final ──────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    elapsed = time.time() - t0
    print(f"\n[finetune] Done. {global_step} steps in {elapsed:.0f}s.", file=sys.stderr)
    print(f"[finetune] Model saved to {OUTPUT_DIR}", file=sys.stderr)

    return OUTPUT_DIR


# ── Test ──────────────────────────────────────────────────────────────

def test_model(model_dir: Path):
    """Quick test: generate a response with the fine-tuned model."""
    from transformers import pipeline

    print(f"\n[test] Loading fine-tuned model from {model_dir}...", file=sys.stderr)
    generator = pipeline(
        "text-generation",
        model=str(model_dir),
        tokenizer=str(model_dir),
        device=-1 if device == "cpu" else 0,
    )

    prompts = [
        "### Instruction: Explain what the Lawvere fixed point is.\n### Response:",
        "### Instruction: What is the Wheeler-DeWitt equation?\n### Response:",
        "### Instruction: Describe the mixture of experts architecture.\n### Response:",
    ]

    for prompt in prompts:
        print(f"\n{'='*60}")
        print(f"PROMPT: {prompt}")
        result = generator(
            prompt,
            max_new_tokens=150,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
        )
        generated = result[0]["generated_text"]
        # Show only the response part
        if "### Response:" in generated:
            response = generated.split("### Response:")[-1].strip()
        else:
            response = generated[len(prompt):].strip()
        print(f"RESPONSE: {response[:300]}")


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-only", type=str, help="Skip training, test existing model dir")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--resume", type=str, help="Resume from checkpoint dir")
    args = parser.parse_args()

    if args.test_only:
        test_model(Path(args.test_only))
    else:
        model_dir = finetune(epochs=args.epochs, resume_from=args.resume)
        test_model(model_dir)
