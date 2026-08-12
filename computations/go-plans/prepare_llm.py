"""
Prepare training data for llama-finetune.

Converts Go instruction Q&A pairs into the format expected by llama.cpp's
llama-finetune tool. The tool expects raw text for next-token prediction.

For DeepSeek-R1-Distill-Qwen-7B, we use the chat template format.
"""

import json
import os


def convert_to_finetune_text(jsonl_path: str, output_path: str):
    """
    Convert instruction JSONL to raw text for llama-finetune.
    
    Uses DeepSeek-R1 chat template:
    <｜User｜>instruction\ninput<｜Assistant｜>output
    
    Each example is separated by newlines. The model learns to predict
    the assistant's response given the user's instruction.
    """
    with open(jsonl_path) as f:
        examples = [json.loads(line) for line in f if line.strip()]
    
    with open(output_path, 'w') as out:
        for ex in examples:
            instruction = ex["instruction"]
            user_input = ex.get("input", "")
            output = ex["output"]
            
            # Format as conversation
            if user_input:
                prompt = f"<|User|>{instruction}\n\n{user_input}<|Assistant|>"
            else:
                prompt = f"<|User|>{instruction}<|Assistant|>"
            
            response = output
            
            # Write the full text — model will be trained to predict
            # the assistant response given the user prompt
            out.write(f"{prompt}{response}\n\n")
    
    print(f"Converted {len(examples)} examples -> {output_path}")


def convert_to_chatml(jsonl_path: str, output_path: str):
    """
    Convert to ChatML format (alternative for Qwen models).
    
    <|im_start|>system
    You are a Go expert...
    <|im_end|>
    <|im_start|>user
    instruction
    <|im_end|>
    <|im_start|>assistant
    response
    <|im_end|>
    """
    system_prompt = (
        "You are a Go (Baduk/Weiqi) expert AI trained on Shin Jinseo's complete strategic framework. "
        "You provide accurate, detailed answers about Go rules, openings, tactics, and strategy."
    )
    
    with open(jsonl_path) as f:
        examples = [json.loads(line) for line in f if line.strip()]
    
    with open(output_path, 'w') as out:
        for ex in examples:
            instruction = ex["instruction"]
            user_input = ex.get("input", "")
            output = ex["output"]
            
            if user_input:
                user_msg = f"{instruction}\n\n{user_input}"
            else:
                user_msg = instruction
            
            text = (
                f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
                f"<|im_start|>user\n{user_msg}<|im_end|>\n"
                f"<|im_start|>assistant\n{output}<|im_end|>\n"
            )
            out.write(text)
    
    print(f"Converted {len(examples)} examples (ChatML) -> {output_path}")


def create_lora_training_script(
    model_path: str,
    train_file: str,
    lora_output: str,
    output_script: str,
) -> str:
    """
    Create a shell script for running llama-finetune with LoRA.
    """
    # Key parameters for training on 13GB RAM with 7B Q4 model
    script = f"""#!/bin/bash
# LoRA fine-tune DeepSeek-R1-Distill-Qwen-7B on Go knowledge
# Estimated time: 1-3 hours on CPU (16 cores, 13GB RAM)

MODEL="{model_path}"
TRAIN_DATA="{train_file}"
LORA_OUT="{lora_output}"

/home/nakamichi/llama.cpp/build/bin/llama-finetune \\
    --model "$MODEL" \\
    --file "$TRAIN_DATA" \\
    --lora "$LORA_OUT" \\
    --threads 14 \\
    --ctx-size 2048 \\
    --batch-size 4 \\
    --ubatch-size 4 \\
    --epochs 3 \\
    --learning-rate 1e-4 \\
    --weight-decay 1e-4 \\
    --val-split 0.05 \\
    --adamw \\
    --flash-attn off \\
    --no-perf

echo "LoRA adapter saved to: $LORA_OUT"
echo ""
echo "To use the fine-tuned model:"
echo "  llama-cli --model $MODEL --lora $LORA_OUT -p 'Explain Go rules'"
"""
    
    with open(output_script, 'w') as f:
        f.write(script)
    
    os.chmod(output_script, 0o755)
    print(f"Training script created: {output_script}")
    return output_script


if __name__ == "__main__":
    jsonl_path = "go_instructions.jsonl"
    
    # Ensure the instruction file exists
    if not os.path.exists(jsonl_path):
        from llm_training import generate_finetune_jsonl
        generate_finetune_jsonl(jsonl_path)
    
    # Convert to finetune format
    convert_to_finetune_text(jsonl_path, "go_train_data.txt")
    convert_to_chatml(jsonl_path, "go_train_data_chatml.txt")
    
    # Create training script
    create_lora_training_script(
        model_path="/home/nakamichi/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
        train_file="go_train_data.txt",
        lora_output="go_expert_lora.gguf",
        output_script="run_lora_finetune.sh",
    )
    
    print("\nReady for fine-tuning!")
    print("  bash run_lora_finetune.sh")
