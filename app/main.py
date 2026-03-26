from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from dotenv import load_dotenv
from openai import OpenAI
import os

from app.models import ChatRequest, ChatResponse, SourceItem
from app.rag import search, build_index
from app.safety import is_sensitive_query, classify_query
from app.prompt import System_Prompt
from app.logs import add_log, get_logs

Temperature = 0.99
Model = "gpt-4.1-mini-fake"
Fallback_Threshold = 1.1
Preview_Length = 220

templates = Jinja2Templates(directory="app/templates")
load_dotenv()

app = FastAPI(title="Student Support Chatbot")
app.mount("/static", StaticFiles(directory="static"), name="static")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def wellbeing_response():
    
    return ChatResponse(
        answer=(
            "I'm sorry you're feeling this way. The university offers wellbeing and support services that may be able to help.\n\n"
            "You can explore support options here:\n"
            "https://student.kent.ac.uk/support/wellbeing\n\n"
            "If you feel you may be at immediate risk, please contact emergency services or urgent support."
        ),
        sources=[
            SourceItem(
                title="Wellbeing Support",
                url="https://student.kent.ac.uk/support/wellbeing",
                category="wellbeing",
                content="",
                score=0.0
            )
        ],
        fallback=True,
        category="wellbeing"
    )

@app.on_event("startup")
def startup_event():
    build_index()
    
@app.get("/")
def serve_ui():
    return FileResponse("static/index.html")
    
@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    logs=get_logs()
    
    rows = ""
    for i, log in enumerate(logs):
        sources = ", ".join(log["sources"]) if log["sources"] else "None"
        snippet = log.get("snippet", "None").replace("<", "&lt;").replace(">", "&gt;")
        
        rows += f"""
        <tr>
            <td>{log['timestamp']}</td>
            <td>{log['query']}</td>
            <td>{log['category']}</td>
            <td>{'Yes' if log['fallback'] else 'No'}</td>
            <td>{'Yes' if log['sensitive'] else 'No'}</td>
            <td>{sources}</td>
            <td>
                <button class="preview-toggle" type="button" onclick="togglePreview('snippet-{i}')">
                    Preview
                </button>
                <div id="snippet-{i}" class="snippet-preview">
                    {snippet}
                </div>
            </td>
        </tr>
        """
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "rows": rows
        }
    )
    
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    query = req.message.strip()
    category = classify_query(query)
    sensitive = is_sensitive_query(query)
    
    if sensitive:
        add_log({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "query": query,
            "category": category,
            "fallback":True,
            "sensitive": sensitive,
            "sources": []
        })
        return wellbeing_response()
        
    retrieved = search(query)
    
    if not retrieved:
        add_log({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "query": query,
            "category": category,
            "fallback":True,
            "sensitive": sensitive,
            "sources": [],
            "snippet": "No sufficiently relevant source passed the similarity threshold."
        })
        return ChatResponse(
            answer=(
                "I couldn't find relevant information in the approved knowledge base. "
                "Please check the official university guidance or contact the relevant support service."
                ),
                sources=[],
                fallback=True,
                category=category
            )
            
    best_score = retrieved[0]["score"]
    if best_score > Fallback_Threshold:
        add_log({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "query": query,
            "category": category,
            "fallback":True,
            "sensitive": sensitive,
            "sources": []
        })        
        return ChatResponse(
            answer=(
                "I couldn't confirm that confidently from the approved content I have access to. "
                "Please check the official university guidance or contact the relevant support services."
                ),
                sources=[SourceItem(**r) for r in retrieved],
                fallback=True,
                category=category
            )
    context = "\n\n---\n\n".join(
        [f"Source: {r['title']}\n{r['content']}" for r in retrieved]
    )
    
    user_prompt = f"""
        Student question: 
        {query}
    
        Retrieved context:
        {context}
    """
    try:
        response = client.chat.completions.create(
            model=Model,
            temperature=Temperature,
            messages=[
                {"role": "system", "content": System_Prompt},
                {"role": "user", "content": user_prompt},
            ],
        )   
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM API error: {e}")
        
        add_log({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "query": query,
            "category": category,
            "fallback":False,
            "sensitive": sensitive,
            "sources": [s.title for s in sources] if 'sources' in locals() else [],
            "snippet": "LLM API failure handled."
        })
        
        return ChatResponse(
            answer=(
                "The assistant is temporarily unavailable. "
                "Please check the official university support pages or try again shortly."
            ),
            sources=sources if 'sources' in locals() else [],
            fallback=True,
            category=category
        )
        
    sorted_retrieved = sorted(retrieved, key=lambda r: r["score"])
    
    unique_sources = {}
    for r in sorted_retrieved:
        key = r.get("url") or r.get("title")
        if key not in unique_sources:
            unique_sources[key] = r
    
    top_sources = list(unique_sources.values())[:3]
    if top_sources:
        best_snippet = top_sources[0].get("content", "")[:Preview_Length].strip()
        if len(top_sources[0].get("content", "")) > Preview_Length:
            best_snippet += "..."
    sources = [SourceItem(**s) for s in top_sources]
    
    add_log({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": query,
        "category": category,
        "fallback":False,
        "sensitive": sensitive,
        "sources": [s.title for s in sources],
        "snippet": best_snippet
    })
    
    return ChatResponse(
        answer=answer,
        sources=sources,
        fallback=False,
        category=category
    )