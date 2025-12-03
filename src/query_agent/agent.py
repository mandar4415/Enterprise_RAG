"""
Query Agent for Deep Agent - Policy Edition
Implements Agentic RAG with Corrective RAG and Multi-Step Planning using LangGraph
"""
from typing import List, Dict, Any, Optional, Literal, TypedDict, Annotated
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.core.config import (
    LLM_MODEL_NAME,
    LLM_TEMPERATURE,
    TOP_K_RESULTS,
    MAX_CORRECTION_ATTEMPTS,
    MAX_PLANNING_STEPS,
    EMBEDDING_DIMENSION,
    TOP_K_RERANK_CANDIDATES,
    TOP_K_AFTER_RERANK,
    SIMILARITY_THRESHOLD,
    ENABLE_RERANKING
)
from src.db.models import DocumentChunk, Document
from src.db.connection import get_db_context
from src.ingestion.pipeline import embedding_model
from src.retrieval.reranker import rerank_chunks


# =============================================================================
# PYDANTIC MODELS FOR STRUCTURED OUTPUT
# =============================================================================

class GradeDocuments(BaseModel):
    """Grade documents using a binary score for relevance check."""
    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )
    reasoning: str = Field(
        description="Brief explanation of why the documents are relevant or not"
    )


class QueryPlan(BaseModel):
    """Plan for breaking down complex queries into sub-queries."""
    is_complex: bool = Field(
        description="Whether the query requires multi-step planning"
    )
    sub_queries: List[str] = Field(
        default_factory=list,
        description="List of sub-queries to answer the main question"
    )
    reasoning: str = Field(
        description="Explanation of the query analysis"
    )


class RewrittenQuery(BaseModel):
    """Rewritten query for better retrieval."""
    improved_query: str = Field(
        description="The improved, more specific query"
    )
    reasoning: str = Field(
        description="Explanation of how the query was improved"
    )


# =============================================================================
# STATE DEFINITION FOR LANGGRAPH
# =============================================================================

class AgentState(TypedDict):
    """State for the RAG agent graph."""
    # Input
    original_query: str
    document_ids: Optional[List[int]]  # Optional filter for specific documents
    
    # Query processing
    current_query: str
    sub_queries: List[str]
    sub_query_index: int
    
    # Retrieved context
    retrieved_chunks: List[Dict[str, Any]]
    context: str
    
    # Agent decisions
    needs_retrieval: bool
    documents_relevant: bool
    correction_attempts: int
    
    # Sub-query results
    sub_results: List[Dict[str, Any]]
    
    # Final output
    answer: str
    sources: List[Dict[str, Any]]
    reasoning_steps: List[str]


# =============================================================================
# LLM INITIALIZATION
# =============================================================================

def get_llm():
    """Get the LLM instance for the agent."""
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL_NAME,
        temperature=LLM_TEMPERATURE,
        max_retries=2
    )


# =============================================================================
# RETRIEVAL FUNCTIONS
# =============================================================================

def retrieve_similar_chunks(
    query: str,
    top_k: int = TOP_K_RESULTS,
    document_ids: Optional[List[int]] = None,
    db: Optional[Session] = None,
    use_reranking: bool = ENABLE_RERANKING
) -> List[Dict[str, Any]]:
    """
    Retrieve the most similar document chunks for a query using pgvector.
    Optionally applies cross-encoder re-ranking for improved precision.
    
    Args:
        query: The search query
        top_k: Number of results to return
        document_ids: Optional list of document IDs to filter by
        db: Optional database session
        use_reranking: Whether to apply re-ranking (default: True)
        
    Returns:
        List of chunk dictionaries with content and metadata
    """
    # Generate query embedding
    query_embedding = embedding_model.encode_single(query)
    
    # If re-ranking is enabled, retrieve more candidates initially
    initial_top_k = TOP_K_RERANK_CANDIDATES if use_reranking else top_k
    
    def do_search(session: Session) -> List[Dict[str, Any]]:
        # Build base query with pgvector cosine distance
        base_query = session.query(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(query_embedding).label('distance')
        ).join(Document)
        
        # Apply document filter if specified
        if document_ids:
            base_query = base_query.filter(DocumentChunk.document_id.in_(document_ids))
        
        # Order by distance and limit results
        results = base_query.order_by('distance').limit(initial_top_k).all()
        
        chunks = []
        for chunk, distance in results:
            similarity = 1 - distance  # Convert distance to similarity
            
            # Apply similarity threshold filter
            if similarity < SIMILARITY_THRESHOLD:
                continue
                
            chunks.append({
                "id": chunk.id,
                "document_id": chunk.document_id,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "document_name": chunk.document.filename,
                "document_title": chunk.document.title,
                "similarity_score": similarity
            })
        return chunks
    
    if db:
        chunks = do_search(db)
    else:
        with get_db_context() as session:
            chunks = do_search(session)
    
    # Apply re-ranking if enabled and we have chunks
    if use_reranking and chunks:
        chunks = rerank_chunks(query, chunks, top_k=top_k)
    else:
        # Just take top_k if no re-ranking
        chunks = chunks[:top_k]
    
    return chunks


def format_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a context string for the LLM."""
    if not chunks:
        return "No relevant documents found."
    
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        # Include relevance score for transparency
        score = chunk.get('rerank_score', chunk.get('similarity_score', 0))
        context_parts.append(
            f"[Source {i}: {chunk['document_title']} (chunk {chunk['chunk_index']}, relevance: {score:.2f})]\n"
            f"{chunk['content']}\n"
        )
    
    return "\n---\n".join(context_parts)


# =============================================================================
# AGENT NODE FUNCTIONS
# =============================================================================

def analyze_query(state: AgentState) -> AgentState:
    """
    Analyze the query to determine if it's simple or needs multi-step planning.
    """
    llm = get_llm()
    
    prompt = f"""Analyze this policy-related question and determine if it requires multi-step planning.

Question: {state['original_query']}

A question needs multi-step planning if:
1. It asks about multiple topics that need separate lookups
2. It requires comparing information from different sources
3. It has conditional parts (e.g., "if X, then what about Y")
4. It asks about relationships between different policies

Respond with a JSON object containing:
- is_complex: true/false
- sub_queries: list of simpler sub-questions if complex, empty if simple
- reasoning: brief explanation

Example complex query: "What is the policy for using personal devices for work, and which department handles the security audit?"
This breaks into: ["What is the policy for using personal devices for work?", "Which department handles security audits for personal devices?"]
"""
    
    try:
        response = llm.with_structured_output(QueryPlan).invoke(prompt)
        
        if response.is_complex and len(response.sub_queries) > 0:
            state['sub_queries'] = response.sub_queries[:MAX_PLANNING_STEPS]
            state['current_query'] = response.sub_queries[0]
            state['sub_query_index'] = 0
            state['reasoning_steps'].append(f"Query Analysis: Complex query detected. Breaking into {len(state['sub_queries'])} sub-queries.")
        else:
            state['sub_queries'] = []
            state['current_query'] = state['original_query']
            state['reasoning_steps'].append("Query Analysis: Simple query - proceeding with direct retrieval.")
        
        state['needs_retrieval'] = True
        
    except Exception as e:
        # Fallback: treat as simple query
        state['sub_queries'] = []
        state['current_query'] = state['original_query']
        state['needs_retrieval'] = True
        state['reasoning_steps'].append(f"Query Analysis: Defaulting to simple query processing. ({str(e)[:50]})")
    
    return state


def retrieve_documents(state: AgentState) -> AgentState:
    """
    Retrieve relevant documents for the current query.
    Uses re-ranking for improved context precision.
    """
    chunks = retrieve_similar_chunks(
        state['current_query'],
        document_ids=state.get('document_ids'),
        use_reranking=ENABLE_RERANKING
    )
    
    state['retrieved_chunks'] = chunks
    state['context'] = format_context(chunks)
    
    if ENABLE_RERANKING and chunks:
        avg_score = sum(c.get('rerank_score', 0) for c in chunks) / len(chunks)
        state['reasoning_steps'].append(
            f"Retrieval: Found {len(chunks)} relevant chunks (re-ranked, avg score: {avg_score:.2f})"
        )
    else:
        state['reasoning_steps'].append(f"Retrieval: Found {len(chunks)} relevant document chunks.")
    
    return state


def grade_documents(state: AgentState) -> AgentState:
    """
    Grade the retrieved documents for relevance.
    """
    if not state['retrieved_chunks']:
        state['documents_relevant'] = False
        state['reasoning_steps'].append("Grading: No documents to grade.")
        return state
    
    llm = get_llm()
    
    prompt = f"""You are a grader assessing relevance of retrieved documents to a user question.

Question: {state['current_query']}

Retrieved Documents:
{state['context']}

Determine if ANY of the documents contain information relevant to answering the question.
Look for:
- Direct answers to the question
- Related policies or procedures
- Contextual information that helps answer the question

Respond with:
- binary_score: 'yes' if at least some documents are relevant, 'no' if none are relevant
- reasoning: brief explanation of your assessment
"""
    
    try:
        response = llm.with_structured_output(GradeDocuments).invoke(prompt)
        state['documents_relevant'] = response.binary_score.lower() == 'yes'
        state['reasoning_steps'].append(f"Grading: Documents {'relevant' if state['documents_relevant'] else 'not relevant'}. {response.reasoning}")
    except Exception as e:
        # If grading fails, assume documents are relevant to avoid over-correction
        state['documents_relevant'] = True
        state['reasoning_steps'].append(f"Grading: Assuming relevant (grading error: {str(e)[:30]})")
    
    return state


def rewrite_query(state: AgentState) -> AgentState:
    """
    Rewrite the query to improve retrieval results (Corrective RAG).
    """
    state['correction_attempts'] += 1
    
    llm = get_llm()
    
    prompt = f"""The following search query did not return relevant results for a policy document search.

Original Query: {state['current_query']}

Please rewrite this query to be more effective for searching policy documents. Consider:
1. Using more specific policy-related terminology
2. Focusing on the core intent of the question
3. Including relevant synonyms or related terms
4. Making the query more concise and focused

Provide:
- improved_query: the rewritten query
- reasoning: brief explanation of changes made
"""
    
    try:
        response = llm.with_structured_output(RewrittenQuery).invoke(prompt)
        state['current_query'] = response.improved_query
        state['reasoning_steps'].append(f"Query Rewrite (attempt {state['correction_attempts']}): {response.reasoning}")
    except Exception as e:
        state['reasoning_steps'].append(f"Query Rewrite failed: {str(e)[:30]}")
    
    return state


def generate_answer(state: AgentState) -> AgentState:
    """
    Generate an answer based on the retrieved context.
    """
    llm = get_llm()
    
    system_prompt = """You are an expert policy assistant helping employees understand company policies and procedures.

CRITICAL RULES - YOU MUST FOLLOW THESE:
1. ONLY use information that is EXPLICITLY stated in the provided context
2. DO NOT add any information from your general knowledge
3. DO NOT make inferences or assumptions beyond what the context states
4. If the context doesn't contain enough information, clearly say "Based on the provided documents, I don't have information about [topic]"
5. Always cite which source document(s) you're using with (Source X) format
6. Be concise and professional
7. If you're uncertain about something, express that uncertainty

IMPORTANT: Hallucinating information not in the context is a serious error. When in doubt, say you don't have that information."""
    
    if state['sub_queries'] and len(state['sub_queries']) > 1:
        # Multi-step: generate partial answer for sub-query
        user_prompt = f"""Based ONLY on the following policy documents, answer this specific question:

Question: {state['current_query']}

Context from policy documents:
{state['context']}

REMEMBER: Only use information explicitly stated in the context above. Do not add any information from your training data.
Provide a focused answer to this specific question. Cite sources using (Source X) format."""
    else:
        # Simple query: generate final answer
        user_prompt = f"""Based ONLY on the following policy documents, answer this question:

Question: {state['original_query']}

Context from policy documents:
{state['context']}

REMEMBER: 
- Only use information explicitly stated in the context above
- Do not add any information from your training data  
- If information is missing, say so clearly
- Cite sources using (Source X) format

Provide a comprehensive but concise answer."""
    
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        response = llm.invoke(messages)
        
        if state['sub_queries'] and len(state['sub_queries']) > 1:
            # Store sub-result
            state['sub_results'].append({
                "query": state['current_query'],
                "answer": response.content,
                "sources": state['retrieved_chunks'][:3]  # Top 3 sources
            })
            state['reasoning_steps'].append(f"Sub-answer generated for: {state['current_query'][:50]}...")
        else:
            state['answer'] = response.content
            state['sources'] = [
                {
                    "document": chunk['document_title'],
                    "chunk": chunk['chunk_index'],
                    "relevance_score": round(chunk.get('rerank_score', chunk.get('similarity_score', 0)), 3),
                    "preview": chunk['content'][:200] + "..."
                }
                for chunk in state['retrieved_chunks'][:5]
            ]
            state['reasoning_steps'].append("Answer generated from context.")
            
    except Exception as e:
        error_msg = f"I apologize, but I encountered an error generating the answer: {str(e)[:100]}"
        if state['sub_queries'] and len(state['sub_queries']) > 1:
            state['sub_results'].append({
                "query": state['current_query'],
                "answer": error_msg,
                "sources": []
            })
        else:
            state['answer'] = error_msg
            state['sources'] = []
        state['reasoning_steps'].append(f"Answer generation error: {str(e)[:30]}")
    
    return state


def synthesize_final_answer(state: AgentState) -> AgentState:
    """
    Synthesize sub-results into a final comprehensive answer (for multi-step queries).
    """
    if not state['sub_results']:
        state['answer'] = "I couldn't find relevant information to answer your question."
        state['sources'] = []
        return state
    
    llm = get_llm()
    
    # Format sub-results for synthesis
    sub_results_text = "\n\n".join([
        f"Sub-question: {r['query']}\nAnswer: {r['answer']}"
        for r in state['sub_results']
    ])
    
    prompt = f"""You've gathered answers to multiple sub-questions. Now synthesize them into a single, coherent response.

Original Question: {state['original_query']}

Sub-question Answers:
{sub_results_text}

Create a well-organized, comprehensive answer that:
1. Addresses all parts of the original question
2. Flows logically from one topic to the next
3. Maintains a professional tone
4. Clearly indicates if any part couldn't be fully answered
"""
    
    try:
        response = llm.invoke(prompt)
        state['answer'] = response.content
        
        # Collect all sources from sub-results
        all_sources = []
        for result in state['sub_results']:
            for source in result.get('sources', []):
                if source not in all_sources:
                    all_sources.append({
                        "document": source.get('document_title', 'Unknown'),
                        "chunk": source.get('chunk_index', 0),
                        "preview": source.get('content', '')[:200] + "..."
                    })
        state['sources'] = all_sources[:5]
        state['reasoning_steps'].append("Final answer synthesized from sub-query results.")
        
    except Exception as e:
        # Fallback: concatenate sub-results
        state['answer'] = "\n\n".join([
            f"**{r['query']}**\n{r['answer']}"
            for r in state['sub_results']
        ])
        state['reasoning_steps'].append(f"Synthesis error, using concatenated results: {str(e)[:30]}")
    
    return state


def generate_direct_answer(state: AgentState) -> AgentState:
    """
    Generate a direct answer without retrieval (for very simple queries).
    """
    llm = get_llm()
    
    prompt = f"""You are a helpful policy assistant. The user has asked a simple question that may not require looking up specific policies.

Question: {state['original_query']}

If this is a general question you can answer directly, provide a helpful response.
If this question requires specific policy information, indicate that you need to search the policy documents.
"""
    
    try:
        response = llm.invoke(prompt)
        state['answer'] = response.content
        state['sources'] = []
        state['reasoning_steps'].append("Direct answer generated (no retrieval needed).")
    except Exception as e:
        state['answer'] = f"Error generating response: {str(e)[:100]}"
        state['reasoning_steps'].append(f"Direct answer error: {str(e)[:30]}")
    
    return state


# =============================================================================
# ROUTING FUNCTIONS
# =============================================================================

def route_after_grading(state: AgentState) -> Literal["generate_answer", "rewrite_query", "generate_direct"]:
    """Route based on document grading results."""
    if not state['retrieved_chunks']:
        # No documents found at all
        if state['correction_attempts'] < MAX_CORRECTION_ATTEMPTS:
            return "rewrite_query"
        else:
            return "generate_direct"
    
    if state['documents_relevant']:
        return "generate_answer"
    elif state['correction_attempts'] < MAX_CORRECTION_ATTEMPTS:
        return "rewrite_query"
    else:
        # Give up on correction, try to answer with what we have
        return "generate_answer"


def route_after_answer(state: AgentState) -> Literal["next_subquery", "synthesize", "end"]:
    """Route after generating an answer."""
    if not state['sub_queries'] or len(state['sub_queries']) <= 1:
        return "end"
    
    # Check if there are more sub-queries to process
    if state['sub_query_index'] < len(state['sub_queries']) - 1:
        return "next_subquery"
    else:
        return "synthesize"


def move_to_next_subquery(state: AgentState) -> AgentState:
    """Move to the next sub-query in multi-step processing."""
    state['sub_query_index'] += 1
    state['current_query'] = state['sub_queries'][state['sub_query_index']]
    state['correction_attempts'] = 0  # Reset correction counter for new sub-query
    state['reasoning_steps'].append(f"Moving to sub-query {state['sub_query_index'] + 1}/{len(state['sub_queries'])}")
    return state


# =============================================================================
# BUILD THE GRAPH
# =============================================================================

def build_agent_graph():
    """Build the LangGraph agent workflow."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("analyze_query", analyze_query)
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("grade", grade_documents)
    workflow.add_node("rewrite", rewrite_query)
    workflow.add_node("generate", generate_answer)
    workflow.add_node("generate_direct", generate_direct_answer)
    workflow.add_node("next_subquery", move_to_next_subquery)
    workflow.add_node("synthesize", synthesize_final_answer)
    
    # Define edges
    workflow.add_edge(START, "analyze_query")
    workflow.add_edge("analyze_query", "retrieve")
    workflow.add_edge("retrieve", "grade")
    
    # Conditional edges after grading
    workflow.add_conditional_edges(
        "grade",
        route_after_grading,
        {
            "generate_answer": "generate",
            "rewrite_query": "rewrite",
            "generate_direct": "generate_direct"
        }
    )
    
    # Rewrite loops back to retrieve
    workflow.add_edge("rewrite", "retrieve")
    
    # Conditional edges after generating answer
    workflow.add_conditional_edges(
        "generate",
        route_after_answer,
        {
            "next_subquery": "next_subquery",
            "synthesize": "synthesize",
            "end": END
        }
    )
    
    # Next subquery goes back to retrieve
    workflow.add_edge("next_subquery", "retrieve")
    
    # Synthesize and direct answer go to end
    workflow.add_edge("synthesize", END)
    workflow.add_edge("generate_direct", END)
    
    return workflow.compile()


# =============================================================================
# MAIN QUERY FUNCTION
# =============================================================================

# Build the agent graph once at module load
agent_graph = build_agent_graph()


def query_policy_documents(
    query: str,
    verbose: bool = False,
    document_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Main function to query policy documents using the agentic RAG system.
    
    Args:
        query: The user's question about policies
        verbose: Whether to include reasoning steps in the response
        document_ids: Optional list of document IDs to filter search
        
    Returns:
        Dictionary with answer, sources, and optionally reasoning steps
    """
    # Initialize state
    initial_state: AgentState = {
        "original_query": query,
        "document_ids": document_ids,
        "current_query": query,
        "sub_queries": [],
        "sub_query_index": 0,
        "retrieved_chunks": [],
        "context": "",
        "needs_retrieval": True,
        "documents_relevant": False,
        "correction_attempts": 0,
        "sub_results": [],
        "answer": "",
        "sources": [],
        "reasoning_steps": []
    }
    
    # Run the agent
    try:
        final_state = agent_graph.invoke(initial_state)
        
        response = {
            "query": query,
            "answer": final_state["answer"],
            "sources": final_state["sources"],
            "status": "success"
        }
        
        if verbose:
            response["reasoning_steps"] = final_state["reasoning_steps"]
        
        return response
        
    except Exception as e:
        return {
            "query": query,
            "answer": f"An error occurred while processing your query: {str(e)}",
            "sources": [],
            "status": "error",
            "error": str(e)
        }