"""
=============================================================================
LANGGRAPH FOUNDATIONS — The Structure That NEVER Changes
=============================================================================
LangGraph builds AI workflows as GRAPHS:
    Nodes = functions that do work
    Edges = connections between nodes
    State = data that flows through the graph

The CORE PATTERN (same from beginner to production):

    1. DEFINE STATE    → What data flows through the graph
    2. DEFINE NODES    → Functions that read/update state
    3. DEFINE EDGES    → How nodes connect (including conditional branching)
    4. COMPILE & RUN   → graph.compile() → app.invoke(initial_state)

Every LangGraph app — from a simple pipeline to a multi-agent system —
uses this EXACT skeleton.

Run: python learn/03_langgraph_foundations.py
=============================================================================
"""

# pip install langgraph langchain-core langchain-groq

import os
from typing import TypedDict, Annotated, List, Optional
from pydantic import BaseModel, Field

# SET YOUR API KEY (get free at https://console.groq.com)
# os.environ["GROQ_API_KEY"] = "your-key-here"


# =============================================================================
# LEVEL 1: SIMPLEST POSSIBLE GRAPH (No LLM needed)
# =============================================================================
# Understand the skeleton FIRST with pure Python. No AI, no complexity.

def level_1_simplest_graph():
    """
    The absolute minimum LangGraph application.
    3 nodes, linear flow: START → greet → process → format → END
    
    This teaches: State, Nodes, Edges, Compile, Invoke.
    """
    from langgraph.graph import StateGraph, START, END
    
    print("\n" + "=" * 60)
    print("LEVEL 1: SIMPLEST GRAPH (Pure Python, no LLM)")
    print("=" * 60)
    
    # ---- STEP 1: DEFINE STATE ----
    # State = the "shared notebook" passed between ALL nodes.
    # Every node can READ from it and WRITE to it.
    
    class MyState(TypedDict):
        name: str               # Input: user's name
        greeting: str            # Set by greet node
        processed: str           # Set by process node
        final_output: str        # Set by format node
    
    # ---- STEP 2: DEFINE NODES ----
    # A node = a function that takes state and returns a dict of updates.
    # IMPORTANT: You return ONLY the fields you want to UPDATE, not the entire state.
    
    def greet(state: MyState) -> dict:
        """Node 1: Create a greeting."""
        name = state["name"]
        return {"greeting": f"Hello, {name}!"}  # Only updates 'greeting'
    
    def process(state: MyState) -> dict:
        """Node 2: Process the greeting."""
        greeting = state["greeting"]
        return {"processed": greeting.upper()}  # Only updates 'processed'
    
    def format_output(state: MyState) -> dict:
        """Node 3: Create final output."""
        return {"final_output": f"📢 {state['processed']} Welcome to LangGraph!"}
    
    # ---- STEP 3: BUILD GRAPH ----
    graph = StateGraph(MyState)
    
    # Add nodes (name, function)
    graph.add_node("greet", greet)
    graph.add_node("process", process)
    graph.add_node("format", format_output)
    
    # Add edges (from, to) — defines the flow
    graph.add_edge(START, "greet")         # START → greet
    graph.add_edge("greet", "process")     # greet → process
    graph.add_edge("process", "format")    # process → format
    graph.add_edge("format", END)          # format → END
    
    # ---- STEP 4: COMPILE & RUN ----
    app = graph.compile()
    
    # Invoke with initial state
    result = app.invoke({"name": "Rahul"})
    
    print(f"\n  Flow: START → greet → process → format → END")
    print(f"\n  Input:  name = 'Rahul'")
    print(f"  After greet:   greeting = '{result['greeting']}'")
    print(f"  After process: processed = '{result['processed']}'")
    print(f"  After format:  final_output = '{result['final_output']}'")
    
    print("\n💡 KEY INSIGHT: State flows through nodes. Each node updates specific fields.")
    print("   This is the skeleton of EVERY LangGraph app.")


# =============================================================================
# LEVEL 2: CONDITIONAL EDGES (Branching — The Graph's "Brain")
# =============================================================================
# The POWER of LangGraph: nodes can decide WHERE to go next.

def level_2_conditional_edges():
    """
    Conditional edges: a function decides the next node based on state.
    
    Flow:
        START → classify → route?
                             ├── "positive" → handle_positive → END
                             ├── "negative" → handle_negative → END
                             └── "neutral"  → handle_neutral  → END
    """
    from langgraph.graph import StateGraph, START, END
    
    print("\n" + "=" * 60)
    print("LEVEL 2: CONDITIONAL EDGES (Branching)")
    print("=" * 60)
    
    # State
    class ReviewState(TypedDict):
        review_text: str
        sentiment: str
        response: str
    
    # Nodes
    def classify(state: ReviewState) -> dict:
        """Classify review sentiment (simple keyword-based)."""
        text = state["review_text"].lower()
        if any(w in text for w in ["great", "love", "excellent", "amazing", "best"]):
            return {"sentiment": "positive"}
        elif any(w in text for w in ["bad", "terrible", "worst", "hate", "awful"]):
            return {"sentiment": "negative"}
        return {"sentiment": "neutral"}
    
    def handle_positive(state: ReviewState) -> dict:
        return {"response": f"😊 Thank you for the lovely review! We're glad you enjoyed it."}
    
    def handle_negative(state: ReviewState) -> dict:
        return {"response": f"😔 We're sorry to hear that. A manager will contact you within 24 hours."}
    
    def handle_neutral(state: ReviewState) -> dict:
        return {"response": f"🤔 Thank you for your feedback. We'll take it into consideration."}
    
    # Router function — decides which node comes next
    def route_by_sentiment(state: ReviewState) -> str:
        """This function RETURNS THE NAME of the next node."""
        return state["sentiment"]  # Returns "positive", "negative", or "neutral"
    
    # Build graph
    graph = StateGraph(ReviewState)
    
    graph.add_node("classify", classify)
    graph.add_node("positive", handle_positive)
    graph.add_node("negative", handle_negative)
    graph.add_node("neutral", handle_neutral)
    
    graph.add_edge(START, "classify")
    
    # CONDITIONAL EDGE: after 'classify', call route_by_sentiment to decide next node
    graph.add_conditional_edges(
        "classify",            # Source node
        route_by_sentiment,    # Router function
        {                      # Mapping: function return value → node name
            "positive": "positive",
            "negative": "negative",
            "neutral": "neutral",
        }
    )
    
    graph.add_edge("positive", END)
    graph.add_edge("negative", END)
    graph.add_edge("neutral", END)
    
    app = graph.compile()
    
    # Test with different reviews
    test_reviews = [
        "This product is amazing! Best purchase ever!",
        "Terrible quality. Worst experience of my life.",
        "The product arrived on time. It works as expected.",
    ]
    
    print(f"\n  Flow: START → classify → route? → handle_X → END\n")
    
    for review in test_reviews:
        result = app.invoke({"review_text": review})
        print(f"  Review:    '{review[:50]}...'")
        print(f"  Sentiment: {result['sentiment']}")
        print(f"  Response:  {result['response']}")
        print()
    
    print("💡 KEY INSIGHT: add_conditional_edges lets the graph DECIDE the path.")
    print("   The router function reads state and returns the next node's name.")


# =============================================================================
# LEVEL 3: LOOPS (The Graph Can Go Back!)
# =============================================================================
# Unlike simple pipelines, graphs can LOOP — retry, refine, iterate.

def level_3_loops():
    """
    A graph that LOOPS until a condition is met.
    
    Flow:
        START → generate → check_quality?
                              ├── "pass"  → END
                              └── "retry" → generate (LOOP!)
    
    This is the pattern behind AI agents that keep trying until they succeed.
    """
    from langgraph.graph import StateGraph, START, END
    
    print("\n" + "=" * 60)
    print("LEVEL 3: LOOPS (Retry pattern)")
    print("=" * 60)
    
    class PasswordState(TypedDict):
        attempt: int
        password: str
        feedback: str
        is_valid: bool
    
    def generate_password(state: PasswordState) -> dict:
        """Generate a password (simulates LLM generating something)."""
        import random
        import string
        
        attempt = state.get("attempt", 0) + 1
        
        # Simulate getting better each attempt
        if attempt == 1:
            pwd = "abc"  # Too short, will fail
        elif attempt == 2:
            pwd = "abcdefgh"  # No uppercase, will fail
        else:
            pwd = "Secure123!"  # Good password, will pass
        
        print(f"    Attempt {attempt}: Generated '{pwd}'")
        return {"password": pwd, "attempt": attempt}
    
    def check_quality(state: PasswordState) -> dict:
        """Check if password meets requirements."""
        pwd = state["password"]
        issues = []
        
        if len(pwd) < 8:
            issues.append("too short (min 8 chars)")
        if not any(c.isupper() for c in pwd):
            issues.append("needs uppercase letter")
        if not any(c.isdigit() for c in pwd):
            issues.append("needs a number")
        
        if issues:
            return {"feedback": f"Issues: {', '.join(issues)}", "is_valid": False}
        return {"feedback": "Password is strong!", "is_valid": True}
    
    def should_retry(state: PasswordState) -> str:
        """Decide: retry or done?"""
        if state["is_valid"]:
            return "pass"
        if state["attempt"] >= 5:  # Safety: max 5 attempts
            return "pass"
        return "retry"
    
    # Build graph with a loop
    graph = StateGraph(PasswordState)
    
    graph.add_node("generate", generate_password)
    graph.add_node("check", check_quality)
    
    graph.add_edge(START, "generate")
    graph.add_edge("generate", "check")
    
    # LOOP: after check, either retry (go back to generate) or pass (go to END)
    graph.add_conditional_edges(
        "check",
        should_retry,
        {
            "retry": "generate",  # ← THIS IS THE LOOP (goes back!)
            "pass": END,
        }
    )
    
    app = graph.compile()
    
    print(f"\n  Flow: START → generate → check → retry? → generate (LOOP) or END\n")
    
    result = app.invoke({"attempt": 0, "password": "", "feedback": "", "is_valid": False})
    
    print(f"\n  Final: password='{result['password']}', valid={result['is_valid']}")
    print(f"  Took {result['attempt']} attempts")
    
    print("\n💡 KEY INSIGHT: Loops are just conditional edges that point BACKWARDS.")
    print("   This is how AI agents retry/refine until they get it right.")


# =============================================================================
# LEVEL 4: MESSAGE STATE (Chat/LLM patterns)
# =============================================================================
# When building chatbots or LLM apps, you need message history.
# LangGraph has a special pattern for this: the add_messages reducer.

def level_4_message_state():
    """
    Messages in state need special handling:
    - You don't REPLACE messages, you APPEND new ones
    - The 'add_messages' reducer handles this automatically
    
    This is the pattern used in EVERY LangGraph chatbot/agent.
    """
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    print("\n" + "=" * 60)
    print("LEVEL 4: MESSAGE STATE (for LLM/chat applications)")
    print("=" * 60)
    
    # State with messages — Annotated[list, add_messages] means "APPEND, don't replace"
    class ChatState(TypedDict):
        messages: Annotated[list, add_messages]  # ← THE KEY: this APPENDS
        summary: str
    
    def chatbot(state: ChatState) -> dict:
        """Respond to the latest message."""
        messages = state["messages"]
        last_msg = messages[-1].content
        
        # In real app: send messages to LLM
        # response = llm.invoke(messages)
        # return {"messages": [response]}
        
        # Mock response for demo
        mock = AIMessage(content=f"[Bot] You said: '{last_msg}'. That's interesting!")
        return {"messages": [mock]}  # add_messages will APPEND this, not replace!
    
    def summarize(state: ChatState) -> dict:
        """Summarize the conversation."""
        msg_count = len(state["messages"])
        return {"summary": f"Conversation had {msg_count} messages."}
    
    # Build
    graph = StateGraph(ChatState)
    graph.add_node("chatbot", chatbot)
    graph.add_node("summarize", summarize)
    
    graph.add_edge(START, "chatbot")
    graph.add_edge("chatbot", "summarize")
    graph.add_edge("summarize", END)
    
    app = graph.compile()
    
    # Run
    result = app.invoke({
        "messages": [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="What is LangGraph?"),
        ]
    })
    
    print(f"\n  Messages after invoke:")
    for msg in result["messages"]:
        label = msg.__class__.__name__
        print(f"    [{label}] {msg.content[:80]}")
    print(f"  Summary: {result['summary']}")
    
    print(f"\n  Notice: we started with 2 messages, ended with {len(result['messages'])}.")
    print("  The add_messages reducer APPENDED the AI response, not replaced!")
    
    print("\n💡 KEY INSIGHT: Annotated[list, add_messages] = append-only list.")
    print("   This is how LangGraph preserves conversation history.")


# =============================================================================
# LEVEL 5: TOOL-CALLING AGENT (The ReAct Pattern)
# =============================================================================
# The most common LangGraph pattern: LLM decides to call tools in a loop.
#   LLM → "I need to call search()" → execute search → give result to LLM
#   LLM → "Now I have enough info" → generate final answer → END

def level_5_tool_agent():
    """
    The ReAct Agent pattern:
    
        START → agent (LLM) → should_use_tools?
                                ├── YES → tool_node (execute tools) → agent (LOOP)
                                └── NO  → END (final answer ready)
    
    This is the #1 most-used LangGraph pattern in production.
    """
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    from langchain_core.tools import tool
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    
    print("\n" + "=" * 60)
    print("LEVEL 5: TOOL-CALLING AGENT (ReAct pattern)")
    print("=" * 60)
    
    # ---- Define Tools ----
    @tool
    def search_policy(query: str) -> str:
        """Search the company policy database."""
        policies = {
            "leave": "Employees get 21 days annual leave per year.",
            "wfh": "Work from home allowed 2 days per week.",
            "overtime": "Overtime: 1.5x weekday, 2x weekend. Max 20 hrs/month.",
            "sick": "12 days sick leave per year. Medical cert needed after 2 days."
        }
        for key, val in policies.items():
            if key in query.lower():
                return val
        return "No policy found for that query."
    
    @tool
    def calculate(expression: str) -> str:
        """Calculate a math expression."""
        try:
            return str(eval(expression))
        except:
            return "Calculation error"
    
    tools = [search_policy, calculate]
    tool_map = {t.name: t for t in tools}
    
    # ---- State ----
    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]
    
    # ---- Nodes ----
    def agent_node(state: AgentState) -> dict:
        """The 'brain' — LLM decides what to do next."""
        try:
            from langchain_groq import ChatGroq
            llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0)
            llm_with_tools = llm.bind_tools(tools)
            response = llm_with_tools.invoke(state["messages"])
            return {"messages": [response]}
        except Exception:
            # Mock: simulate tool call on first pass, answer on second
            messages = state["messages"]
            has_tool_result = any(
                hasattr(m, '__class__') and m.__class__.__name__ == 'ToolMessage'
                for m in messages
            )
            if not has_tool_result:
                # Simulate LLM deciding to call search_policy
                mock = AIMessage(
                    content="",
                    tool_calls=[{"name": "search_policy", "args": {"query": "leave"}, "id": "call_1"}]
                )
            else:
                # Simulate LLM generating final answer
                mock = AIMessage(content="Based on company policy, employees get 21 days annual leave per year.")
            return {"messages": [mock]}
    
    def tool_node(state: AgentState) -> dict:
        """Execute whatever tools the LLM requested."""
        last_message = state["messages"][-1]
        results = []
        
        for tc in last_message.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            print(f"    🔧 Calling tool: {tool_name}({tool_args})")
            
            result = tool_map[tool_name].invoke(tool_args)
            print(f"    📋 Result: {result}")
            
            results.append(ToolMessage(content=result, tool_call_id=tc["id"]))
        
        return {"messages": results}
    
    # ---- Router ----
    def should_use_tools(state: AgentState) -> str:
        """Check if the LLM wants to call tools or is done."""
        last_message = state["messages"][-1]
        
        # If the LLM made tool calls → execute them
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        
        # Otherwise → LLM is done, go to END
        return "end"
    
    # ---- Build Graph ----
    graph = StateGraph(AgentState)
    
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    
    graph.add_edge(START, "agent")
    
    graph.add_conditional_edges(
        "agent",
        should_use_tools,
        {
            "tools": "tools",   # LLM wants to call tools → execute them
            "end": END,         # LLM is done → finish
        }
    )
    
    graph.add_edge("tools", "agent")  # After tools execute → go back to LLM
    # ↑ THIS IS THE LOOP: agent → tools → agent → tools → ... → END
    
    app = graph.compile()
    
    print(f"\n  Flow: START → agent → tools? → agent → ... → END\n")
    
    result = app.invoke({
        "messages": [HumanMessage(content="How many days of annual leave do employees get?")]
    })
    
    print(f"\n  Conversation trace:")
    for msg in result["messages"]:
        label = msg.__class__.__name__
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"    [{label}] → Tool calls: {[tc['name'] for tc in msg.tool_calls]}")
        else:
            content = msg.content[:100] if msg.content else "(empty)"
            print(f"    [{label}] {content}")
    
    print("\n💡 KEY INSIGHT: The ReAct loop is just:")
    print("   agent → conditional_edge(has tool calls?) → tools → back to agent")
    print("   The LLM decides WHEN to stop (when it stops requesting tools).")


# =============================================================================
# LEVEL 6: MEMORY & CHECKPOINTING (Multi-turn conversations)
# =============================================================================
# Without memory, each invoke() starts fresh. With checkpointing,
# the graph REMEMBERS previous conversations.

def level_6_memory():
    """
    Checkpointing = saving state between invocations.
    thread_id = unique conversation identifier.
    
    This enables: multi-turn chat, pause/resume, time-travel debugging.
    """
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    from langgraph.checkpoint.memory import MemorySaver
    from langchain_core.messages import HumanMessage, AIMessage
    
    print("\n" + "=" * 60)
    print("LEVEL 6: MEMORY (Checkpointing)")
    print("=" * 60)
    
    class ChatState(TypedDict):
        messages: Annotated[list, add_messages]
    
    def chatbot(state: ChatState) -> dict:
        messages = state["messages"]
        last = messages[-1].content
        
        # Count how many human messages so far (shows memory works)
        human_count = sum(1 for m in messages if isinstance(m, HumanMessage))
        
        reply = AIMessage(content=f"[Turn {human_count}] You said: '{last}'. I remember our entire conversation!")
        return {"messages": [reply]}
    
    # Build graph
    graph = StateGraph(ChatState)
    graph.add_node("chatbot", chatbot)
    graph.add_edge(START, "chatbot")
    graph.add_edge("chatbot", END)
    
    # MEMORY: compile with a checkpointer
    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    
    # thread_id groups messages into a conversation
    config = {"configurable": {"thread_id": "user-123"}}
    
    print(f"\n  Simulating multi-turn conversation (thread_id='user-123'):\n")
    
    # Turn 1
    r1 = app.invoke({"messages": [HumanMessage(content="Hi, I'm Rahul")]}, config)
    print(f"  Human: Hi, I'm Rahul")
    print(f"  AI:    {r1['messages'][-1].content}")
    
    # Turn 2 — the graph REMEMBERS turn 1!
    r2 = app.invoke({"messages": [HumanMessage(content="What's my name?")]}, config)
    print(f"\n  Human: What's my name?")
    print(f"  AI:    {r2['messages'][-1].content}")
    print(f"  Total messages in memory: {len(r2['messages'])}")
    
    # Turn 3
    r3 = app.invoke({"messages": [HumanMessage(content="This is turn 3")]}, config)
    print(f"\n  Human: This is turn 3")
    print(f"  AI:    {r3['messages'][-1].content}")
    print(f"  Total messages in memory: {len(r3['messages'])}")
    
    # DIFFERENT thread = DIFFERENT conversation (no shared memory)
    config_other = {"configurable": {"thread_id": "user-456"}}
    r_other = app.invoke({"messages": [HumanMessage(content="Hello!")]}, config_other)
    print(f"\n  [Different thread 'user-456']")
    print(f"  Human: Hello!")
    print(f"  AI:    {r_other['messages'][-1].content}")
    print(f"  Messages: {len(r_other['messages'])} (fresh start!)")
    
    print("\n💡 KEY INSIGHT: MemorySaver + thread_id = conversation memory.")
    print("   Same thread_id = continue conversation. Different = fresh start.")


# =============================================================================
# LEVEL 7: PREBUILT REACT AGENT (Production shortcut)
# =============================================================================
# LangGraph provides create_react_agent() — builds the ENTIRE Level 5 graph
# in ONE line. This is what most production apps start with.

def level_7_prebuilt_agent():
    """
    create_react_agent = Level 5 (tool agent) in ONE function call.
    It creates: agent node + tool node + conditional loop + memory.
    
    Use this when you KNOW the pattern and just want it working fast.
    Use Level 5 (custom graph) when you need custom routing or extra nodes.
    """
    print("\n" + "=" * 60)
    print("LEVEL 7: PREBUILT create_react_agent()")
    print("=" * 60)
    
    try:
        from langgraph.prebuilt import create_react_agent
        from langchain_core.tools import tool
        from langchain_core.messages import HumanMessage
        from langchain_groq import ChatGroq
        
        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0)
        
        @tool
        def get_weather(city: str) -> str:
            """Get current weather for a city."""
            weather = {"delhi": "32°C, Sunny", "mumbai": "28°C, Humid", "bangalore": "24°C, Cloudy"}
            return weather.get(city.lower(), f"Weather data not available for {city}")
        
        @tool
        def get_time(timezone: str) -> str:
            """Get current time in a timezone."""
            return f"Current time in {timezone}: 14:30 IST"
        
        # ONE LINE to create the entire agent!
        agent = create_react_agent(
            model=llm,
            tools=[get_weather, get_time],
        )
        
        result = agent.invoke({
            "messages": [HumanMessage(content="What's the weather in Delhi?")]
        })
        
        print(f"\n  Agent created with create_react_agent(llm, tools)")
        print(f"\n  Conversation:")
        for msg in result["messages"]:
            label = msg.__class__.__name__
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                print(f"    [{label}] Tool calls: {[tc['name'] for tc in msg.tool_calls]}")
            elif msg.content:
                print(f"    [{label}] {msg.content[:100]}")
        
    except Exception as e:
        print(f"\n  Need GROQ_API_KEY for this demo. Pattern:")
        print(f"""
    from langgraph.prebuilt import create_react_agent
    
    agent = create_react_agent(
        model=llm,                      # Any LangChain LLM
        tools=[tool1, tool2, tool3],    # List of @tool functions
    )
    
    result = agent.invoke({{
        "messages": [HumanMessage(content="your question")]
    }})
    
    # That's it! The agent will:
    # 1. See the question
    # 2. Decide which tool(s) to call
    # 3. Execute tools
    # 4. Loop back if needed
    # 5. Generate final answer
        """)
    
    print("💡 KEY INSIGHT: create_react_agent is a SHORTCUT for the Level 5 pattern.")
    print("   Start here, then build custom graphs when you need more control.")


# =============================================================================
# SUMMARY: THE LANGGRAPH SKELETON
# =============================================================================

def summary():
    print("\n" + "=" * 60)
    print("📋 LANGGRAPH SKELETON — Copy-paste this for ANY project")
    print("=" * 60)
    print("""
    from typing import TypedDict, Annotated
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    
    # 1. STATE — what data flows through the graph
    class MyState(TypedDict):
        messages: Annotated[list, add_messages]  # For chat/LLM
        data: str                                 # Your custom fields
        result: str
    
    # 2. NODES — functions that do work
    def step_1(state: MyState) -> dict:
        return {"data": "processed " + state["data"]}
    
    def step_2(state: MyState) -> dict:
        return {"result": state["data"].upper()}
    
    # 3. ROUTER — for conditional edges (optional)
    def decide_next(state: MyState) -> str:
        if state["data"]:
            return "step_2"
        return "step_1"  # retry
    
    # 4. BUILD
    graph = StateGraph(MyState)
    graph.add_node("step_1", step_1)
    graph.add_node("step_2", step_2)
    
    graph.add_edge(START, "step_1")
    graph.add_conditional_edges("step_1", decide_next,
        {"step_1": "step_1", "step_2": "step_2"})
    graph.add_edge("step_2", END)
    
    # 5. COMPILE & RUN
    app = graph.compile()  # Add checkpointer=MemorySaver() for memory
    result = app.invoke({"data": "hello", "messages": []})
    
    # THAT'S IT. Every LangGraph app is this structure.
    # Complexity comes from WHAT your nodes do, not the graph itself.
    """)
    
    print("  PROGRESSION:")
    print("  Level 1: Linear (A → B → C → END)")
    print("  Level 2: Branching (A → B? → C1 or C2)")
    print("  Level 3: Loops (A → B → check → A again or END)")
    print("  Level 4: Messages (add_messages for chat history)")
    print("  Level 5: Tool Agent (LLM → tools → LLM → ... → END)")
    print("  Level 6: Memory (checkpointer + thread_id)")
    print("  Level 7: Prebuilt (create_react_agent)")


# =============================================================================
# RUN ALL LEVELS
# =============================================================================
if __name__ == "__main__":
    print("🚀 " * 20)
    print("LANGGRAPH FOUNDATIONS — 7 levels, same skeleton\n")
    
    level_1_simplest_graph()
    level_2_conditional_edges()
    level_3_loops()
    level_4_message_state()
    level_5_tool_agent()
    level_6_memory()
    level_7_prebuilt_agent()
    summary()
    
    print("\n" + "=" * 60)
    print("✅ DONE! You've built 7 LangGraph applications.")
    print("   From simple pipelines to tool-calling agents.")
    print("   The SKELETON is always the same: State → Nodes → Edges → Compile → Run")
    print("=" * 60)
    
    # EXPERIMENTS:
    # 1. In Level 2: add a 4th sentiment ("angry") with its own handler
    # 2. In Level 3: change the password rules and see the retry count change
    # 3. In Level 5: add a new tool (e.g., get_employee_info) and test it
    # 4. In Level 6: try getting state history with app.get_state_history(config)
    # 5. Build YOUR OWN: a graph that takes a topic → researches → writes a summary
