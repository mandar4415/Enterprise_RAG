"""
RAG Evaluation Module for Deep Agent - Policy Edition
Implements comprehensive evaluation metrics using RAGAS framework

Metrics Covered:
1. Context Precision & Recall - How good is retrieval?
2. Faithfulness - Does LLM stick to retrieved context?
3. Answer Relevancy - Does answer address the question?
4. End-to-End Evaluation - Overall pipeline performance
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.core.config import LLM_MODEL_NAME, LLM_TEMPERATURE


# =============================================================================
# EVALUATION DATA MODELS
# =============================================================================

@dataclass
class EvaluationSample:
    """Single evaluation sample with query, context, answer, and optional ground truth."""
    query: str
    retrieved_contexts: List[str]
    generated_answer: str
    ground_truth: Optional[str] = None  # For precision/recall if available
    sources: Optional[List[Dict]] = None


@dataclass
class EvaluationResult:
    """Complete evaluation result with all metrics."""
    # Core RAGAS metrics
    faithfulness_score: float  # 0-1: Does answer stick to context?
    answer_relevancy_score: float  # 0-1: Does answer address the question?
    context_precision_score: float  # 0-1: How relevant is retrieved context?
    context_recall_score: Optional[float]  # 0-1: Did we get all relevant info? (needs ground truth)
    
    # Additional metrics
    context_utilization_score: float  # 0-1: How much context was actually used?
    response_completeness_score: float  # 0-1: Is the answer complete?
    
    # Overall score
    overall_score: float
    
    # Detailed feedback
    feedback: Dict[str, str]
    
    # Metadata
    timestamp: str
    query: str


# =============================================================================
# PYDANTIC MODELS FOR LLM STRUCTURED OUTPUT
# =============================================================================

class FaithfulnessEval(BaseModel):
    """Evaluate if answer is faithful to the context."""
    score: float = Field(description="Score from 0.0 to 1.0")
    claims_in_answer: List[str] = Field(description="Key claims made in the answer")
    claims_supported: List[str] = Field(description="Claims that are supported by context")
    claims_unsupported: List[str] = Field(description="Claims NOT supported by context (hallucinations)")
    reasoning: str = Field(description="Explanation of the evaluation")


class AnswerRelevancyEval(BaseModel):
    """Evaluate if answer is relevant to the question."""
    score: float = Field(description="Score from 0.0 to 1.0")
    question_aspects: List[str] = Field(description="Key aspects of the question")
    aspects_addressed: List[str] = Field(description="Aspects that were addressed")
    aspects_missed: List[str] = Field(description="Aspects that were NOT addressed")
    reasoning: str = Field(description="Explanation of the evaluation")


class ContextPrecisionEval(BaseModel):
    """Evaluate precision of retrieved context."""
    score: float = Field(description="Score from 0.0 to 1.0")
    total_chunks: int = Field(description="Total number of retrieved chunks")
    relevant_chunks: int = Field(description="Number of chunks relevant to the query")
    irrelevant_chunks: List[int] = Field(description="Indices of irrelevant chunks (0-indexed)")
    reasoning: str = Field(description="Explanation of the evaluation")


class ContextUtilizationEval(BaseModel):
    """Evaluate how well the context was utilized in the answer."""
    score: float = Field(description="Score from 0.0 to 1.0")
    context_pieces_used: int = Field(description="Number of context pieces actually used")
    context_pieces_total: int = Field(description="Total context pieces available")
    reasoning: str = Field(description="Explanation of the evaluation")


class CompletenessEval(BaseModel):
    """Evaluate if the answer is complete."""
    score: float = Field(description="Score from 0.0 to 1.0")
    is_complete: bool = Field(description="Whether the answer fully addresses the question")
    missing_elements: List[str] = Field(description="What's missing from the answer")
    reasoning: str = Field(description="Explanation of the evaluation")


# =============================================================================
# RAG EVALUATOR CLASS
# =============================================================================

class RAGEvaluator:
    """
    Comprehensive RAG pipeline evaluator.
    Measures: Faithfulness, Answer Relevancy, Context Precision, Context Utilization
    """
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL_NAME,
            temperature=0.0  # Use 0 for consistent evaluation
        )
    
    def evaluate_faithfulness(self, sample: EvaluationSample) -> FaithfulnessEval:
        """
        Evaluate if the answer is faithful to the retrieved context.
        Detects hallucinations by checking if claims are supported.
        """
        context_text = "\n---\n".join(sample.retrieved_contexts)
        
        prompt = f"""You are evaluating the FAITHFULNESS of a RAG system's answer.

TASK: Determine if the answer ONLY contains information from the provided context.
Any information NOT in the context is a HALLUCINATION.

QUESTION: {sample.query}

RETRIEVED CONTEXT:
{context_text}

GENERATED ANSWER:
{sample.generated_answer}

INSTRUCTIONS:
1. Extract all factual claims from the answer
2. Check each claim against the context
3. Claims NOT found in context are hallucinations
4. Score = (supported claims) / (total claims)

Provide your evaluation:
"""
        
        try:
            result = self.llm.with_structured_output(FaithfulnessEval).invoke(prompt)
            return result
        except Exception as e:
            return FaithfulnessEval(
                score=0.5,
                claims_in_answer=["Error evaluating"],
                claims_supported=[],
                claims_unsupported=[],
                reasoning=f"Evaluation error: {str(e)[:100]}"
            )
    
    def evaluate_answer_relevancy(self, sample: EvaluationSample) -> AnswerRelevancyEval:
        """
        Evaluate if the answer actually addresses the user's question.
        """
        prompt = f"""You are evaluating the ANSWER RELEVANCY of a RAG system.

TASK: Determine if the answer actually addresses what the user asked.
A correct answer is useless if it doesn't solve the user's problem.

QUESTION: {sample.query}

GENERATED ANSWER:
{sample.generated_answer}

INSTRUCTIONS:
1. Identify key aspects/parts of the question
2. Check which aspects are addressed in the answer
3. Note any aspects that were missed
4. Score = (aspects addressed) / (total aspects)

Provide your evaluation:
"""
        
        try:
            result = self.llm.with_structured_output(AnswerRelevancyEval).invoke(prompt)
            return result
        except Exception as e:
            return AnswerRelevancyEval(
                score=0.5,
                question_aspects=["Error evaluating"],
                aspects_addressed=[],
                aspects_missed=[],
                reasoning=f"Evaluation error: {str(e)[:100]}"
            )
    
    def evaluate_context_precision(self, sample: EvaluationSample) -> ContextPrecisionEval:
        """
        Evaluate precision of retrieved context.
        Of everything retrieved, how much was actually relevant?
        """
        context_text = ""
        for i, ctx in enumerate(sample.retrieved_contexts):
            context_text += f"\n[Chunk {i}]:\n{ctx}\n"
        
        prompt = f"""You are evaluating the CONTEXT PRECISION of a RAG retrieval system.

TASK: Of all retrieved chunks, how many are ACTUALLY RELEVANT to answering the question?

QUESTION: {sample.query}

RETRIEVED CHUNKS:
{context_text}

INSTRUCTIONS:
1. For each chunk, determine if it contains information relevant to the question
2. Count relevant vs irrelevant chunks
3. List indices of irrelevant chunks
4. Score = (relevant chunks) / (total chunks)

Provide your evaluation:
"""
        
        try:
            result = self.llm.with_structured_output(ContextPrecisionEval).invoke(prompt)
            return result
        except Exception as e:
            return ContextPrecisionEval(
                score=0.5,
                total_chunks=len(sample.retrieved_contexts),
                relevant_chunks=0,
                irrelevant_chunks=[],
                reasoning=f"Evaluation error: {str(e)[:100]}"
            )
    
    def evaluate_context_utilization(self, sample: EvaluationSample) -> ContextUtilizationEval:
        """
        Evaluate how well the retrieved context was utilized in the answer.
        """
        context_text = ""
        for i, ctx in enumerate(sample.retrieved_contexts):
            context_text += f"\n[Chunk {i}]:\n{ctx}\n"
        
        prompt = f"""You are evaluating CONTEXT UTILIZATION of a RAG system.

TASK: How much of the retrieved context was actually USED in the answer?

QUESTION: {sample.query}

RETRIEVED CONTEXT:
{context_text}

GENERATED ANSWER:
{sample.generated_answer}

INSTRUCTIONS:
1. Check which context chunks contributed to the answer
2. Count how many chunks were actually used
3. Score = (chunks used) / (total relevant chunks)

Provide your evaluation:
"""
        
        try:
            result = self.llm.with_structured_output(ContextUtilizationEval).invoke(prompt)
            return result
        except Exception as e:
            return ContextUtilizationEval(
                score=0.5,
                context_pieces_used=0,
                context_pieces_total=len(sample.retrieved_contexts),
                reasoning=f"Evaluation error: {str(e)[:100]}"
            )
    
    def evaluate_completeness(self, sample: EvaluationSample) -> CompletenessEval:
        """
        Evaluate if the answer is complete.
        """
        prompt = f"""You are evaluating ANSWER COMPLETENESS of a RAG system.

TASK: Is the answer complete? Does it fully address all parts of the question?

QUESTION: {sample.query}

GENERATED ANSWER:
{sample.generated_answer}

INSTRUCTIONS:
1. Identify what the question is asking for
2. Check if all parts are addressed
3. Note any missing elements
4. Score based on completeness

Provide your evaluation:
"""
        
        try:
            result = self.llm.with_structured_output(CompletenessEval).invoke(prompt)
            return result
        except Exception as e:
            return CompletenessEval(
                score=0.5,
                is_complete=False,
                missing_elements=["Error evaluating"],
                reasoning=f"Evaluation error: {str(e)[:100]}"
            )
    
    def evaluate(self, sample: EvaluationSample) -> EvaluationResult:
        """
        Run complete evaluation on a single sample.
        Returns all metrics and overall score.
        """
        # Run all evaluations
        faithfulness = self.evaluate_faithfulness(sample)
        relevancy = self.evaluate_answer_relevancy(sample)
        precision = self.evaluate_context_precision(sample)
        utilization = self.evaluate_context_utilization(sample)
        completeness = self.evaluate_completeness(sample)
        
        # Calculate overall score (weighted average)
        weights = {
            'faithfulness': 0.30,  # Most important - no hallucinations
            'relevancy': 0.25,     # Answer must address the question
            'precision': 0.20,     # Good retrieval matters
            'utilization': 0.10,   # Using what we retrieve
            'completeness': 0.15   # Complete answers
        }
        
        overall_score = (
            faithfulness.score * weights['faithfulness'] +
            relevancy.score * weights['relevancy'] +
            precision.score * weights['precision'] +
            utilization.score * weights['utilization'] +
            completeness.score * weights['completeness']
        )
        
        # Compile feedback
        feedback = {
            "faithfulness": faithfulness.reasoning,
            "answer_relevancy": relevancy.reasoning,
            "context_precision": precision.reasoning,
            "context_utilization": utilization.reasoning,
            "completeness": completeness.reasoning,
            "hallucinations_detected": faithfulness.claims_unsupported,
            "missed_aspects": relevancy.aspects_missed,
            "irrelevant_chunks": precision.irrelevant_chunks
        }
        
        return EvaluationResult(
            faithfulness_score=faithfulness.score,
            answer_relevancy_score=relevancy.score,
            context_precision_score=precision.score,
            context_recall_score=None,  # Needs ground truth
            context_utilization_score=utilization.score,
            response_completeness_score=completeness.score,
            overall_score=overall_score,
            feedback=feedback,
            timestamp=datetime.utcnow().isoformat(),
            query=sample.query
        )
    
    def evaluate_batch(self, samples: List[EvaluationSample]) -> Dict[str, Any]:
        """
        Evaluate multiple samples and return aggregate metrics.
        """
        results = []
        for sample in samples:
            result = self.evaluate(sample)
            results.append(result)
        
        # Calculate averages
        avg_faithfulness = sum(r.faithfulness_score for r in results) / len(results)
        avg_relevancy = sum(r.answer_relevancy_score for r in results) / len(results)
        avg_precision = sum(r.context_precision_score for r in results) / len(results)
        avg_utilization = sum(r.context_utilization_score for r in results) / len(results)
        avg_completeness = sum(r.response_completeness_score for r in results) / len(results)
        avg_overall = sum(r.overall_score for r in results) / len(results)
        
        return {
            "num_samples": len(samples),
            "aggregate_metrics": {
                "avg_faithfulness": round(avg_faithfulness, 3),
                "avg_answer_relevancy": round(avg_relevancy, 3),
                "avg_context_precision": round(avg_precision, 3),
                "avg_context_utilization": round(avg_utilization, 3),
                "avg_completeness": round(avg_completeness, 3),
                "avg_overall_score": round(avg_overall, 3)
            },
            "individual_results": [
                {
                    "query": r.query,
                    "faithfulness": r.faithfulness_score,
                    "relevancy": r.answer_relevancy_score,
                    "precision": r.context_precision_score,
                    "overall": r.overall_score
                }
                for r in results
            ],
            "timestamp": datetime.utcnow().isoformat()
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def evaluate_single_query(
    query: str,
    contexts: List[str],
    answer: str,
    ground_truth: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to evaluate a single query.
    
    Args:
        query: The user's question
        contexts: List of retrieved context strings
        answer: The generated answer
        ground_truth: Optional expected answer for recall calculation
        
    Returns:
        Dictionary with all evaluation metrics
    """
    evaluator = RAGEvaluator()
    sample = EvaluationSample(
        query=query,
        retrieved_contexts=contexts,
        generated_answer=answer,
        ground_truth=ground_truth
    )
    result = evaluator.evaluate(sample)
    
    return {
        "query": result.query,
        "scores": {
            "faithfulness": result.faithfulness_score,
            "answer_relevancy": result.answer_relevancy_score,
            "context_precision": result.context_precision_score,
            "context_utilization": result.context_utilization_score,
            "completeness": result.response_completeness_score,
            "overall": result.overall_score
        },
        "feedback": result.feedback,
        "timestamp": result.timestamp
    }


def evaluate_batch(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate a batch of query-answer pairs.
    
    Args:
        samples: List of dicts with 'query', 'contexts', 'answer' keys
        
    Returns:
        Aggregate evaluation metrics
    """
    evaluator = RAGEvaluator()
    eval_samples = [
        EvaluationSample(
            query=s['query'],
            retrieved_contexts=s['contexts'],
            generated_answer=s['answer'],
            ground_truth=s.get('ground_truth')
        )
        for s in samples
    ]
    return evaluator.evaluate_batch(eval_samples)


# =============================================================================
# QUICK EVALUATION SUMMARY
# =============================================================================

def get_evaluation_summary(result: Dict[str, Any]) -> str:
    """
    Generate a human-readable evaluation summary.
    """
    scores = result.get('scores', {})
    
    summary = f"""
RAG EVALUATION SUMMARY
======================
Query: {result.get('query', 'N/A')[:100]}...

SCORES (0-1 scale, higher is better):
-------------------------------------
Faithfulness:      {scores.get('faithfulness', 0):.2f} {'[GOOD]' if scores.get('faithfulness', 0) >= 0.8 else '[NEEDS IMPROVEMENT]'}
Answer Relevancy:  {scores.get('answer_relevancy', 0):.2f} {'[GOOD]' if scores.get('answer_relevancy', 0) >= 0.8 else '[NEEDS IMPROVEMENT]'}
Context Precision: {scores.get('context_precision', 0):.2f} {'[GOOD]' if scores.get('context_precision', 0) >= 0.7 else '[NEEDS IMPROVEMENT]'}
Context Util:      {scores.get('context_utilization', 0):.2f}
Completeness:      {scores.get('completeness', 0):.2f}

OVERALL SCORE:     {scores.get('overall', 0):.2f} {'[EXCELLENT]' if scores.get('overall', 0) >= 0.85 else '[GOOD]' if scores.get('overall', 0) >= 0.7 else '[NEEDS IMPROVEMENT]'}

KEY ISSUES:
-----------
"""
    
    feedback = result.get('feedback', {})
    if feedback.get('hallucinations_detected'):
        summary += f"- Hallucinations: {feedback['hallucinations_detected']}\n"
    if feedback.get('missed_aspects'):
        summary += f"- Missed aspects: {feedback['missed_aspects']}\n"
    if feedback.get('irrelevant_chunks'):
        summary += f"- Irrelevant chunks retrieved: {feedback['irrelevant_chunks']}\n"
    
    if not any([feedback.get('hallucinations_detected'), feedback.get('missed_aspects'), feedback.get('irrelevant_chunks')]):
        summary += "- No major issues detected\n"
    
    return summary
