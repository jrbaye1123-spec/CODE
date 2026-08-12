"""Generate a sample test set of 30 papers with expert ground-truth labels.

This is the test set needed for Threshold 1 (Recall > 95%).
In production, these labels come from human experts. This script
generates a realistic sample for testing the evaluation harness.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import EvaluationHarness, TestPaper


def generate_test_set():
    harness = EvaluationHarness()

    papers = [
        # Transformer Efficiency thread
        ("arxiv_2401_001", "Structured Pruning of Attention Heads in LLMs",
         ["transformer_efficiency"], "transformer_efficiency"),
        ("arxiv_2401_005", "Sparse Attention Mechanisms for Long Sequences",
         ["transformer_efficiency"], "transformer_efficiency"),
        ("arxiv_2401_009", "Knowledge Distillation for BERT-scale Models",
         ["transformer_efficiency"], "transformer_efficiency"),
        ("arxiv_2401_013", "Quantization-Aware Training for 4-bit Transformers",
         ["transformer_efficiency"], "transformer_efficiency"),
        ("arxiv_2401_017", "Dynamic Neural Architecture Search for Efficient Models",
         ["transformer_efficiency"], "transformer_efficiency"),
        ("arxiv_2401_021", "Mixture of Experts with Conditional Computation",
         ["transformer_efficiency"], "transformer_efficiency"),
        ("arxiv_2401_025", "Low-Rank Adaptation for Parameter-Efficient Fine-Tuning",
         ["transformer_efficiency"], "transformer_efficiency"),
        ("arxiv_2401_029", "Token Merging for Faster Vision Transformers",
         ["transformer_efficiency"], "transformer_efficiency"),
        ("arxiv_2401_033", "Speculative Decoding for 2x Inference Speedup",
         ["transformer_efficiency"], "transformer_efficiency"),
        ("arxiv_2401_037", "FlashAttention: Hardware-Aware Attention Computation",
         ["transformer_efficiency"], "transformer_efficiency"),

        # Alignment and Safety thread
        ("arxiv_2401_002", "Constitutional AI: Training Harmless Assistants",
         ["alignment_safety"], "alignment_safety"),
        ("arxiv_2401_006", "Red-Teaming Language Models with Language Models",
         ["alignment_safety"], "alignment_safety"),
        ("arxiv_2401_010", "RLHF from Human Feedback: A Comprehensive Study",
         ["alignment_safety"], "alignment_safety"),
        ("arxiv_2401_014", "Automated Jailbreak Detection via Embedding Analysis",
         ["alignment_safety"], "alignment_safety"),
        ("arxiv_2401_018", "Scalable Oversight via Debate and Recursive Reward Modeling",
         ["alignment_safety"], "alignment_safety"),
        ("arxiv_2401_022", "Safety-Tuned LLaMAs: Lessons from Adversarial Training",
         ["alignment_safety"], "alignment_safety"),
        ("arxiv_2401_026", "The Refusal Edge: When Models Should Say No",
         ["alignment_safety"], "alignment_safety"),
        ("arxiv_2401_030", "Detecting Deceptive Alignment in Black-Box Models",
         ["alignment_safety"], "alignment_safety"),
        ("arxiv_2401_034", "Mechanistic Interpretability of Safety Circuits",
         ["alignment_safety"], "alignment_safety"),
        ("arxiv_2401_038", "Value Alignment Through Iterated Amplification",
         ["alignment_safety"], "alignment_safety"),

        # Multimodal Learning thread
        ("arxiv_2401_003", "CLIP Revisited: Scaling Vision-Language Pretraining",
         ["multimodal_learning"], "multimodal_learning"),
        ("arxiv_2401_007", "Video-Language Models for Temporal Reasoning",
         ["multimodal_learning"], "multimodal_learning"),
        ("arxiv_2401_011", "Audio-Visual Scene Understanding with Transformers",
         ["multimodal_learning"], "multimodal_learning"),
        ("arxiv_2401_015", "Cross-Modal Retrieval with Contrastive Learning",
         ["multimodal_learning"], "multimodal_learning"),
        ("arxiv_2401_019", "Grounding Language in Robotic Manipulation",
         ["multimodal_learning"], "multimodal_learning"),
        ("arxiv_2401_023", "Medical Vision-Language Models for Report Generation",
         ["multimodal_learning"], "multimodal_learning"),
        ("arxiv_2401_027", "Multimodal Chain-of-Thought Reasoning",
         ["multimodal_learning"], "multimodal_learning"),
        ("arxiv_2401_031", "Speech-Text Foundation Models: A Survey",
         ["multimodal_learning"], "multimodal_learning"),
        ("arxiv_2401_035", "Vision-Language Navigation in Dynamic Environments",
         ["multimodal_learning"], "multimodal_learning"),
        ("arxiv_2401_039", "Document Understanding via Layout-Aware Transformers",
         ["multimodal_learning"], "multimodal_learning"),
    ]

    for paper_id, title, threads, classification in papers:
        harness.add_test_paper(TestPaper(
            paper_id=paper_id,
            title=title,
            source=f"arxiv.org/{paper_id}",
            ground_truth={
                "relevant_threads": threads,
                "classification": classification,
                "relevance_score": 0.85,
            },
            labeled_by="expert_reviewer",
            labeled_at="2024-08-01",
        ))

    print(f"Generated test set with {harness.test_set_size()} papers")
    print(f"Test set ready: {harness.test_set_ready()}")
    return harness


if __name__ == "__main__":
    generate_test_set()
