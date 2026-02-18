"""
=============================================================================
LANGCHAIN FOUNDATIONS — The Structure That NEVER Changes
=============================================================================
LangChain is a framework for building LLM applications.

The CORE PATTERN (same from beginner to production):

    1. MESSAGES   → How you talk to LLMs (system + human messages)
    2. LLM CALL   → Send messages, get response
    3. PROMPTS    → Templates for reusable instructions
    4. CHAINS     → Connect multiple steps: input → step1 → step2 → output
    5. OUTPUT     → Parse LLM text into structured data (Pydantic)
    6. TOOLS      → Give LLMs the ability to call functions

Every LangChain app — from a chatbot to a complex agent —
uses these SAME building blocks.

Run: python learn/02_langchain_foundations.py
=============================================================================
"""

# pip install langchain-core langchain-groq

import os
from typing import List, Optional
from pydantic import BaseModel, Field

# SET YOUR API KEY (get free at https://console.groq.com)
# os.environ["GROQ_API_KEY"] = "your-key-here"

# For examples that need an LLM, we'll use a helper that falls back to mock
def get_llm():
    """Get LLM or return None if no API key."""
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama-3.1-8b-instant", temperature=0.0)
    except Exception:
        print("⚠️  No GROQ_API_KEY set. Using mock responses. Set it to get real LLM calls.")
        return None


# =============================================================================
# FOUNDATION 1: MESSAGES — How You Talk to LLMs
# =============================================================================
# Every LLM call = a list of messages. ALWAYS.
# This is the SAME whether you use OpenAI, Groq, Gemini, Claude, Llama.

def foundation_1_messages():
    """
    THREE message types you'll use 99% of the time:
    
    SystemMessage  → Instructions FOR the AI (the AI's "role")
    HumanMessage   → What the user says
    AIMessage      → What the AI responded (used for conversation history)
    """
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    print("\n" + "=" * 60)
    print("FOUNDATION 1: MESSAGES")
    print("=" * 60)
    
    # Basic message list
    messages = [
        SystemMessage(content="You are a helpful assistant that answers in 1-2 sentences."),
        HumanMessage(content="What is Python?"),
    ]
    
    print(f"\nMessages to send:")
    for msg in messages:
        print(f"  [{msg.__class__.__name__}] {msg.content}")
    
    # Call LLM
    llm = get_llm()
    if llm:
        response = llm.invoke(messages)
        print(f"\n  [AIMessage] {response.content}")
        
        # CONVERSATION: To continue chatting, add the response + next question
        messages.append(response)  # Add AI's response to history
        messages.append(HumanMessage(content="Who created it?"))
        
        response2 = llm.invoke(messages)
        print(f"  [AIMessage] {response2.content}")
        # The LLM knows "it" = Python because it sees the full conversation
    else:
        print("\n  [Mock] Python is a programming language.")
    
    print("\n💡 KEY INSIGHT: Every LLM call is just invoke(list_of_messages).")
    print("   The SAME pattern works with ANY LLM provider.")


# =============================================================================
# FOUNDATION 2: PROMPT TEMPLATES — Reusable Message Factories
# =============================================================================
# Instead of building message strings manually every time,
# templates let you create REUSABLE prompts with variables.

def foundation_2_prompts():
    """
    PromptTemplate = a string with {variables} that get filled in.
    ChatPromptTemplate = creates a list of messages with {variables}.
    
    This is the SAME pattern used in your project's EXPANSION_PROMPT.
    """
    from langchain_core.prompts import ChatPromptTemplate
    
    print("\n" + "=" * 60)
    print("FOUNDATION 2: PROMPT TEMPLATES")
    print("=" * 60)
    
    # Create a reusable template
    template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert on {topic}. Answer in {style} style."),
        ("human", "{question}")
    ])
    
    # Fill in the variables → get actual messages
    messages_1 = template.invoke({
        "topic": "Python programming",
        "style": "beginner-friendly",
        "question": "What is a decorator?"
    })
    
    messages_2 = template.invoke({
        "topic": "cooking",
        "style": "professional chef",
        "question": "How do I make pasta?"
    })
    
    print(f"\nTemplate: system + human with 3 variables")
    print(f"\nFilled template 1 (Python):")
    for msg in messages_1.messages:
        print(f"  [{msg.__class__.__name__}] {msg.content}")
    
    print(f"\nFilled template 2 (Cooking):")
    for msg in messages_2.messages:
        print(f"  [{msg.__class__.__name__}] {msg.content}")
    
    # Call LLM with template
    llm = get_llm()
    if llm:
        response = llm.invoke(messages_1)
        print(f"\n  Answer: {response.content[:150]}...")
    
    print("\n💡 KEY INSIGHT: Templates are FACTORIES for messages.")
    print("   Define once, reuse with different variables.")


# =============================================================================
# FOUNDATION 3: CHAINS — Connecting Steps Together
# =============================================================================
# A chain = step1 | step2 | step3 (using the pipe | operator)
# Data flows through each step, transformed along the way.

def foundation_3_chains():
    """
    The | (pipe) operator connects steps:
        prompt | llm | output_parser
    
    This is LangChain's CORE pattern. Everything builds on this.
    
    Think of it like a factory assembly line:
        raw input → format into prompt → send to LLM → parse response
    """
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    
    print("\n" + "=" * 60)
    print("FOUNDATION 3: CHAINS (the | pipe operator)")
    print("=" * 60)
    
    llm = get_llm()
    if not llm:
        print("\n  Need GROQ_API_KEY to demo chains. Showing structure only.")
        print("  chain = prompt | llm | StrOutputParser()")
        print("  result = chain.invoke({'topic': 'Python', 'question': '...'})")
        print("\n💡 KEY INSIGHT: | connects steps. Data flows left → right.")
        return
    
    # Build a chain: template → LLM → parse to string
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert on {topic}. Answer in 1 sentence."),
        ("human", "{question}")
    ])
    
    # The chain: prompt → llm → output parser
    chain = prompt | llm | StrOutputParser()
    #        ↑           ↑        ↑
    #    fills template  calls LLM  extracts .content as string
    
    # Now use it — just pass the variables!
    result = chain.invoke({
        "topic": "space",
        "question": "How far is the Moon?"
    })
    
    print(f"\n  Chain: prompt | llm | StrOutputParser()")
    print(f"  Input:  topic='space', question='How far is the Moon?'")
    print(f"  Output: {result}")
    
    # Reuse with different inputs
    result2 = chain.invoke({
        "topic": "history",
        "question": "When was the internet invented?"
    })
    print(f"\n  Reuse:  topic='history', question='When was the internet invented?'")
    print(f"  Output: {result2}")
    
    print("\n💡 KEY INSIGHT: chain = prompt | llm | parser")
    print("   .invoke(dict) feeds data through the entire pipeline.")


# =============================================================================
# FOUNDATION 4: STRUCTURED OUTPUT — LLM Returns Pydantic Objects
# =============================================================================
# Instead of getting raw text, force the LLM to return structured data.
# This is what your project uses in src/evaluation.py

def foundation_4_structured_output():
    """
    with_structured_output(PydanticModel) → LLM returns a Python object,
    not raw text. You get .score, .reasoning, etc. as typed attributes.
    
    This is CRITICAL for production apps where you need to parse LLM output
    reliably (not regex-ing through random text).
    """
    print("\n" + "=" * 60)
    print("FOUNDATION 4: STRUCTURED OUTPUT (Pydantic)")
    print("=" * 60)
    
    # Define the structure you want the LLM to return
    class SentimentAnalysis(BaseModel):
        """LLM will fill in these fields."""
        sentiment: str = Field(description="positive, negative, or neutral")
        confidence: float = Field(description="Confidence score 0.0 to 1.0")
        key_phrases: List[str] = Field(description="Key phrases that indicate sentiment")
        summary: str = Field(description="One sentence summary")
    
    # Another example — document classification
    class DocumentClassification(BaseModel):
        """Classify a document into categories."""
        category: str = Field(description="Main category: policy, report, memo, or guide")
        topics: List[str] = Field(description="List of topics covered")
        urgency: str = Field(description="low, medium, or high")
        summary: str = Field(description="Brief summary in 1-2 sentences")
    
    print(f"\n  SentimentAnalysis fields: sentiment, confidence, key_phrases, summary")
    print(f"  DocumentClassification fields: category, topics, urgency, summary")
    
    llm = get_llm()
    if not llm:
        print("\n  Need GROQ_API_KEY to demo. Showing pattern:")
        print("  structured_llm = llm.with_structured_output(SentimentAnalysis)")
        print("  result = structured_llm.invoke(messages)")
        print("  print(result.sentiment)   # 'positive'")
        print("  print(result.confidence)  # 0.92")
        return
    
    from langchain_core.messages import HumanMessage
    
    # Use it!
    structured_llm = llm.with_structured_output(SentimentAnalysis)
    
    result = structured_llm.invoke([
        HumanMessage(content=(
            "Analyze the sentiment of this review:\n"
            "'The product arrived late and was damaged. Customer service was unhelpful "
            "and rude. Worst experience ever. Would not recommend.'"
        ))
    ])
    
    print(f"\n  Result (SentimentAnalysis object):")
    print(f"    sentiment:   {result.sentiment}")
    print(f"    confidence:  {result.confidence}")
    print(f"    key_phrases: {result.key_phrases}")
    print(f"    summary:     {result.summary}")
    
    print("\n💡 KEY INSIGHT: with_structured_output(MyModel) makes the LLM")
    print("   return a typed Python object. No manual parsing needed.")
    print("   Your project uses this in evaluation.py for FaithfulnessResult.")


# =============================================================================
# FOUNDATION 5: TOOLS — Giving LLMs the Ability to ACT
# =============================================================================
# An LLM can only generate text. But with TOOLS, it can:
#   - Search a database
#   - Call an API
#   - Do math
#   - Read a file
# The LLM DECIDES which tool to use and with what arguments.

def foundation_5_tools():
    """
    Tools = Python functions that an LLM can choose to call.
    
    The pattern:
    1. Define functions with @tool decorator
    2. Bind tools to LLM: llm.bind_tools([tool1, tool2])
    3. LLM will output "I want to call tool1 with args {...}"
    4. You execute the tool and give results back to LLM
    
    This is the foundation of AI AGENTS (LangGraph builds on this).
    """
    from langchain_core.tools import tool
    
    print("\n" + "=" * 60)
    print("FOUNDATION 5: TOOLS")
    print("=" * 60)
    
    # Define tools — these are just Python functions with descriptions
    @tool
    def search_knowledge_base(query: str) -> str:
        """Search the company knowledge base for relevant information."""
        # In real app: this would call your vector DB
        fake_results = {
            "leave": "Employees get 21 days annual leave.",
            "wfh": "WFH allowed 2 days/week with manager approval.",
            "overtime": "Overtime at 1.5x weekday, 2x weekend.",
        }
        for key, val in fake_results.items():
            if key in query.lower():
                return val
        return "No relevant information found."
    
    @tool
    def calculate(expression: str) -> str:
        """Calculate a mathematical expression. Use for any math operations."""
        try:
            return str(eval(expression))
        except Exception as e:
            return f"Error: {e}"
    
    @tool
    def get_current_date() -> str:
        """Get today's date."""
        from datetime import date
        return str(date.today())
    
    print(f"\n  Defined 3 tools:")
    print(f"    1. search_knowledge_base(query) — searches company docs")
    print(f"    2. calculate(expression) — does math")
    print(f"    3. get_current_date() — returns today's date")
    
    # Test tools directly
    print(f"\n  Direct call: search_knowledge_base('leave policy')")
    print(f"    Result: {search_knowledge_base.invoke('leave policy')}")
    print(f"  Direct call: calculate('21 * 8')")
    print(f"    Result: {calculate.invoke('21 * 8')}")
    
    llm = get_llm()
    if not llm:
        print("\n  Need GROQ_API_KEY to demo LLM + tools. Showing pattern:")
        print("  llm_with_tools = llm.bind_tools([search_knowledge_base, calculate])")
        print("  response = llm_with_tools.invoke('How many hours of leave is 21 days?')")
        print("  response.tool_calls → [{'name': 'calculate', 'args': {'expression': '21*8'}}]")
        return
    
    from langchain_core.messages import HumanMessage
    
    # Bind tools to LLM — now the LLM KNOWS these tools exist
    tools = [search_knowledge_base, calculate, get_current_date]
    llm_with_tools = llm.bind_tools(tools)
    
    # Ask a question that needs a tool
    response = llm_with_tools.invoke([
        HumanMessage(content="How many total hours of annual leave do employees get? (assume 8 hour days)")
    ])
    
    print(f"\n  LLM response with tools bound:")
    print(f"    Content: {response.content[:100] if response.content else '(no text - tool call instead)'}")
    print(f"    Tool calls: {response.tool_calls}")
    
    if response.tool_calls:
        # Execute the tool the LLM chose
        for tc in response.tool_calls:
            print(f"\n  LLM wants to call: {tc['name']}({tc['args']})")
            # Find and execute the tool
            tool_map = {t.name: t for t in tools}
            if tc['name'] in tool_map:
                result = tool_map[tc['name']].invoke(tc['args'])
                print(f"  Tool result: {result}")
    
    print("\n💡 KEY INSIGHT: Tools let LLMs TAKE ACTIONS, not just generate text.")
    print("   The LLM DECIDES which tool to use. You just define the tools.")
    print("   LangGraph automates this tool-calling loop (see 03_langgraph).")


# =============================================================================
# FOUNDATION 6: RUNNABLE INTERFACE — The Universal API
# =============================================================================
# Everything in LangChain implements the same interface.
# This is WHY you can chain anything with |

def foundation_6_runnable():
    """
    EVERY LangChain object has these methods:
        .invoke(input)        → single input, single output
        .batch([input1, ...]) → multiple inputs at once
        .stream(input)        → get output token by token
    
    This is called the "Runnable" interface. Prompts, LLMs, parsers,
    chains — they ALL have invoke/batch/stream.
    
    That's WHY the | pipe works: output of one .invoke → input of next .invoke
    """
    print("\n" + "=" * 60)
    print("FOUNDATION 6: RUNNABLE INTERFACE")
    print("=" * 60)
    
    print("""
    Every LangChain object:
    ┌─────────────────────────────────────────┐
    │  .invoke(input)   → single call         │
    │  .batch([inputs]) → parallel calls       │
    │  .stream(input)   → token by token       │
    │                                          │
    │  prompt.invoke({"topic": "AI"})          │
    │  llm.invoke([messages])                  │
    │  parser.invoke(ai_message)               │
    │  chain.invoke({"topic": "AI"})           │
    │                                          │
    │  ALL use .invoke(). That's the pattern.  │
    └─────────────────────────────────────────┘
    
    Chain with |:
    chain = prompt | llm | parser
    
    What happens when you call chain.invoke(input):
    1. prompt.invoke(input) → messages
    2. llm.invoke(messages) → AIMessage
    3. parser.invoke(AIMessage) → string
    
    💡 KEY INSIGHT: Learn .invoke() and you've learned LangChain's API.
       Everything is a Runnable. Everything has .invoke().
    """)


# =============================================================================
# QUICK REFERENCE: ALL PATTERNS ON ONE PAGE
# =============================================================================

def quick_reference():
    print("\n" + "=" * 60)
    print("📋 LANGCHAIN QUICK REFERENCE")
    print("=" * 60)
    print("""
    # 1. MESSAGES (talk to LLM)
    from langchain_core.messages import SystemMessage, HumanMessage
    messages = [SystemMessage(content="..."), HumanMessage(content="...")]
    response = llm.invoke(messages)          # → AIMessage
    answer = response.content                # → str

    # 2. PROMPT TEMPLATES (reusable)
    from langchain_core.prompts import ChatPromptTemplate
    template = ChatPromptTemplate.from_messages([
        ("system", "You are {role}"), ("human", "{question}")
    ])
    messages = template.invoke({"role": "...", "question": "..."})

    # 3. CHAINS (connect steps)
    chain = template | llm | StrOutputParser()
    result = chain.invoke({"role": "...", "question": "..."})

    # 4. STRUCTURED OUTPUT (get Python objects)
    class MyOutput(BaseModel):
        answer: str
        score: float
    result = llm.with_structured_output(MyOutput).invoke(messages)
    print(result.answer, result.score)

    # 5. TOOLS (LLM can call functions)
    @tool
    def my_tool(query: str) -> str:
        \"\"\"Description for the LLM.\"\"\"
        return "result"
    llm_with_tools = llm.bind_tools([my_tool])
    response = llm_with_tools.invoke(messages)
    print(response.tool_calls)  # LLM chose which tool + args

    # 6. TEXT SPLITTER (for RAG)
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(long_text)
    """)


# =============================================================================
# RUN ALL FOUNDATIONS
# =============================================================================
if __name__ == "__main__":
    print("🚀 " * 20)
    print("LANGCHAIN FOUNDATIONS — The patterns that NEVER change\n")
    
    foundation_1_messages()
    foundation_2_prompts()
    foundation_3_chains()
    foundation_4_structured_output()
    foundation_5_tools()
    foundation_6_runnable()
    quick_reference()
    
    print("\n" + "=" * 60)
    print("✅ DONE! You now know the 6 foundations of LangChain.")
    print("   Next: learn/03_langgraph_foundations.py")
    print("=" * 60)
    
    # EXPERIMENTS:
    # 1. Set GROQ_API_KEY and re-run — see real LLM responses
    # 2. Change the system message in foundation_1 — see how behavior changes
    # 3. Create your own Pydantic model in foundation_4
    # 4. Create your own @tool in foundation_5
    # 5. Build a chain that: takes a topic → asks LLM for 3 facts → parses them
