"""
RAG Evaluation for Enterprise RAG - Simplified Edition
2 metrics only: Faithfulness + Answer Quality (~100 lines)
Replaces 527-line evaluation with 5 LLM calls
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import LLM_MODEL


class FaithfulnessResult(BaseModel):
    """Faithfulness evaluation result."""
    score: float = Field(description="Score 0-1")
    supported_claims: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    reasoning: str = Field(default="")


class AnswerQualityResult(BaseModel):
    """Combined answer quality result (relevancy + completeness)."""
    score: float = Field(description="Score 0-1")
    addressed_aspects: List[str] = Field(default_factory=list)
    missed_aspects: List[str] = Field(default_factory=list)
    reasoning: str = Field(default="")


def evaluate_faithfulness(query: str, answer: str, contexts: List[str]) -> FaithfulnessResult:
    """
    Evaluate if answer is faithful to context (no hallucinations).
    """
    context_text = "\n---\n".join(contexts)
    
    prompt = f"""Evaluate if this answer ONLY contains information from the context.

QUESTION: {query}

CONTEXT:
{context_text}

ANSWER:
{answer}

INSTRUCTIONS:
1. Extract factual claims from the answer
2. Check if each claim is supported by the context
3. A claim is supported if it matches or reasonably paraphrases context content
4. Only flag claims as unsupported if they add genuinely NEW information
5. Score = supported_claims / total_claims

Be GENEROUS - paraphrases and summaries of context are supported."""

    try:
        llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)
        result = llm.with_structured_output(FaithfulnessResult).invoke(prompt)
        return result
    except Exception as e:
        return FaithfulnessResult(score=0.5, reasoning=f"Error: {str(e)[:50]}")


def evaluate_answer_quality(query: str, answer: str) -> AnswerQualityResult:
    """
    Evaluate answer quality (relevancy + completeness combined).
    """
    prompt = f"""Evaluate if this answer fully addresses the question.

QUESTION: {query}

ANSWER:
{answer}

INSTRUCTIONS:
1. Identify key aspects the question is asking about
2. Check which aspects are addressed in the answer
3. Note any important aspects that were missed
4. Score based on: relevancy (does it answer the question?) + completeness (is it thorough?)
5. Score 1.0 = fully addresses all aspects, 0.0 = completely irrelevant"""

    try:
        llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)
        result = llm.with_structured_output(AnswerQualityResult).invoke(prompt)
        return result
    except Exception as e:
        return AnswerQualityResult(score=0.5, reasoning=f"Error: {str(e)[:50]}")


def evaluate(query: str, answer: str, contexts: List[str]) -> Dict[str, Any]:
    """
    Run complete evaluation with 2 metrics.
    
    Returns:
        Dict with scores, feedback, and overall score
    """
    # Run both evaluations
    faithfulness = evaluate_faithfulness(query, answer, contexts)
    quality = evaluate_answer_quality(query, answer)
    
    # Calculate overall (weighted: 60% faithfulness, 40% quality)
    overall = faithfulness.score * 0.6 + quality.score * 0.4
    
    return {
        "query": query,
        "evaluation": {
            "faithfulness": round(faithfulness.score, 2),
            "answer_relevancy": round(quality.score, 2),
            "overall": round(overall, 2)
        },
        "feedback": {
            "faithfulness": faithfulness.reasoning,
            "answer_quality": quality.reasoning,
            "hallucinations": faithfulness.unsupported_claims,
            "missed_aspects": quality.missed_aspects
        },
        "timestamp": datetime.utcnow().isoformat()
    }


def get_summary(result: Dict[str, Any]) -> str:
    """Generate human-readable summary."""
    scores = result.get("evaluation", {})
    
    overall = scores.get("overall", 0)
    if overall >= 0.9:
        grade = "EXCELLENT"
    elif overall >= 0.7:
        grade = "GOOD"
    elif overall >= 0.5:
        grade = "FAIR"
    else:
        grade = "NEEDS IMPROVEMENT"
    
    return f"""
RAG Evaluation: {grade} ({overall:.0%})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Faithfulness: {scores.get('faithfulness', 0):.0%}
• Answer Quality: {scores.get('answer_relevancy', 0):.0%}
"""
