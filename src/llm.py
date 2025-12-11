"""
LLM Provider Manager for Enterprise RAG
Supports multiple providers with automatic fallback
Primary: Groq (free, fast, 14,400 req/day)
Fallback: Gemini (1,500 req/day free tier)
"""
import os
import time
from typing import Optional, Type
from langchain_core.language_models.chat_models import BaseChatModel

from src.config import LLM_TEMPERATURE


# =============================================================================
# PROVIDER CONFIGURATION
# =============================================================================

# Groq models (free tier: 14,400 req/day, 30 req/min)
GROQ_MODELS = {
    "default": "llama-3.1-8b-instant",  # Fast, good quality
    "large": "llama-3.3-70b-versatile",  # Better quality, slower
    "small": "llama-3.1-8b-instant",     # Fastest
}

# Gemini models (free tier: 1,500 req/day, 15 req/min)
GEMINI_MODELS = {
    "default": "gemini-2.0-flash",
    "large": "gemini-1.5-pro",
    "small": "gemini-2.0-flash",
}


def _get_groq_llm(temperature: float = LLM_TEMPERATURE) -> Optional[BaseChatModel]:
    """Get Groq LLM if API key is available."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return None
    
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=GROQ_MODELS["default"],
            temperature=temperature,
            api_key=api_key,
        )
    except ImportError:
        print("Warning: langchain-groq not installed. Run: pip install langchain-groq")
        return None
    except Exception as e:
        print(f"Groq initialization failed: {e}")
        return None


def _get_gemini_llm(temperature: float = LLM_TEMPERATURE) -> Optional[BaseChatModel]:
    """Get Gemini LLM if API key is available."""
    api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return None
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=GEMINI_MODELS["default"],
            temperature=temperature,
        )
    except Exception as e:
        print(f"Gemini initialization failed: {e}")
        return None


# =============================================================================
# MAIN LLM GETTER WITH FALLBACK
# =============================================================================

def get_llm(temperature: float = LLM_TEMPERATURE) -> BaseChatModel:
    """
    Get LLM with automatic provider selection.
    
    Priority:
    1. Groq (if GROQ_API_KEY set) - 14,400 req/day free
    2. Gemini (if GEMINI_API_KEY set) - 1,500 req/day free
    
    Returns:
        LLM instance ready to use
    
    Raises:
        ValueError if no provider is available
    """
    # Try Groq first (better free tier limits)
    llm = _get_groq_llm(temperature)
    if llm:
        return llm
    
    # Fallback to Gemini
    llm = _get_gemini_llm(temperature)
    if llm:
        return llm
    
    raise ValueError(
        "No LLM provider available. Please set either:\n"
        "- GROQ_API_KEY (get free at https://console.groq.com/)\n"
        "- GEMINI_API_KEY (get free at https://aistudio.google.com/)"
    )


def get_provider_name() -> str:
    """Get the name of the active provider."""
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    return "none"


# =============================================================================
# INVOKE WITH RETRY AND FALLBACK
# =============================================================================

def invoke_with_retry(
    messages,
    temperature: float = LLM_TEMPERATURE,
    max_retries: int = 3,
    structured_output: Optional[Type] = None
) -> str:
    """
    Invoke LLM with retry logic and automatic fallback.
    
    Args:
        messages: List of messages to send
        temperature: LLM temperature
        max_retries: Max retries per provider
        structured_output: Optional Pydantic class for structured output
    
    Returns:
        Response content string or structured object
    """
    providers = []
    
    # Build provider list in priority order
    if os.getenv("GROQ_API_KEY"):
        providers.append(("groq", _get_groq_llm))
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        providers.append(("gemini", _get_gemini_llm))
    
    if not providers:
        raise ValueError("No LLM provider configured")
    
    last_error = None
    
    for provider_name, get_provider in providers:
        llm = get_provider(temperature)
        if not llm:
            continue
            
        for attempt in range(max_retries):
            try:
                if structured_output:
                    return llm.with_structured_output(structured_output).invoke(messages)
                else:
                    return llm.invoke(messages).content
                    
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = (
                    "429" in str(e) or 
                    "quota" in error_str or 
                    "resource" in error_str or
                    "rate" in error_str
                )
                
                if is_rate_limit:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        print(f"{provider_name}: Rate limit, waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"{provider_name}: Rate limit exceeded, trying next provider...")
                        last_error = e
                        break  # Try next provider
                else:
                    # Non-rate-limit error, raise immediately
                    raise
    
    # All providers failed
    if last_error:
        raise last_error
    raise ValueError("All LLM providers failed")


# =============================================================================
# SIMPLE INVOKE (For backward compatibility)
# =============================================================================

def simple_invoke(prompt: str, temperature: float = LLM_TEMPERATURE) -> str:
    """
    Simple text-in, text-out invoke.
    
    Args:
        prompt: Simple string prompt
        temperature: LLM temperature
    
    Returns:
        Response string
    """
    from langchain_core.messages import HumanMessage
    return invoke_with_retry([HumanMessage(content=prompt)], temperature)
