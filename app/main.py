from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from dotenv import load_dotenv
from openai import OpenAI
import os

from app.models import ChatRequest, ChatResponse, SourceItem
from app.rag import search, build_index
from app.moodle_sync import (
    sanitize_module_key,
    DATA_MODULES_DIR,
    resolve_course_id,
    has_moodle_access,
    has_ingest_access,
    ingest_token_matches,
    LAST_SYNC_STATE,
    debug_sync_module_from_moodle,
    write_module_markdown,
    get_module_access_rows,
    list_module_files,
    save_module_file_access,
    load_module_file_access,
)
from app.safety import is_sensitive_query, classify_query
from app.prompt import System_Prompt
from app.logs import add_log, get_logs

from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import secrets

Temperature = 0.99
Model = "gpt-4.1-mini"
Fallback_Threshold = 1.1
Preview_Length = 220

templates = Jinja2Templates(directory="app/templates")
load_dotenv()

app = FastAPI(title="Module Support Chatbot")

MOODLE_ISSUER = os.getenv("MOODLE_ISSUER")
MOODLE_CLIENT_ID = os.getenv("MOODLE_CLIENT_ID")
MOODLE_AUTH_URL = os.getenv("MOODLE_AUTH_URL")
MOODLE_JWKS_URL = os.getenv("MOODLE_JWKS_URL")
LTI_REDIRECT_URI = os.getenv("LTI_REDIRECT_URI")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "change-this-secret"),
    same_site="none",
    https_only=True,
    )

cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
allow_all_origins = "*" in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
    

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

@app.get("/module-status/{module_key}")
def module_status(module_key: str):
    safe_key = sanitize_module_key(module_key)
    if not safe_key:
        return JSONResponse({"ok": False, "error": "invalid module key"}, status_code=400)

    module_dir = DATA_MODULES_DIR / safe_key
    files = []
    if module_dir.exists():
        for path in sorted(module_dir.glob("*.md")):
            files.append({
                "name": path.name,
                "exists": True,
                "size": path.stat().st_size,
            })

    return {
        "ok": True,
        "module_key": safe_key,
        "course_id": resolve_course_id(safe_key),
        "moodle_access": has_moodle_access(),
        "enabled": True,
        "last_sync": LAST_SYNC_STATE,
        "module_dir": str(module_dir),
        "exists": module_dir.exists(),
        "files": files,
        "file_count": len(files),
    }

@app.post("/module-sync-debug/{module_key}")
def module_sync_debug(module_key: str):
    result = debug_sync_module_from_moodle(module_key)
    return result

@app.post("/ingest/module")
async def ingest_module(
    payload: dict,
    authorization: str | None = Header(default=None),
    x_ingest_token: str | None = Header(default=None),
):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_ingest_token:
        token = x_ingest_token.strip()

    if not has_ingest_access():
        raise HTTPException(status_code=503, detail="Ingest is not configured.")
    if not ingest_token_matches(token):
        raise HTTPException(status_code=401, detail="Invalid ingest token.")

    module_key = sanitize_module_key(payload.get("module_key"))
    if not module_key:
        raise HTTPException(status_code=400, detail="Missing or invalid module_key.")

    markdown = payload.get("markdown") or payload.get("content") or ""
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    if payload.get("title") and not metadata.get("title"):
        metadata["title"] = payload.get("title")
    if payload.get("url") and not metadata.get("url"):
        metadata["url"] = payload.get("url")
    if payload.get("course_id") is not None and metadata.get("course_id") is None:
        metadata["course_id"] = payload.get("course_id")

    result = write_module_markdown(
        module_key,
        markdown,
        source=payload.get("source") or "moodle-push",
        metadata=metadata,
    )
    return {
        "ok": result.get("ok", False),
        "module_key": module_key,
        "status": result,
    }

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, module_key: str | None = None):
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
    safe_module_key = sanitize_module_key(module_key) if module_key else None
    module_files = list_module_files(safe_module_key) if safe_module_key else []
    enabled_files = set(load_module_file_access(safe_module_key).get("enabled_files", [])) if safe_module_key else set()

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "rows": rows,
            "module_key": safe_module_key,
            "module_files": [
                {
                    "name": f["name"],
                    "size": f["size"],
                    "enabled": f["name"] in enabled_files if enabled_files else True,
                }
                for f in module_files
            ],
        }
    )

@app.post("/admin/modules")
async def admin_modules(request: Request):
    form = await request.form()
    module_key = form.get("module_key")
    enabled_files = form.getlist("enabled_files")
    save_module_file_access(module_key, enabled_files)
    redirect_target = f"/admin?module_key={module_key}" if module_key else "/admin"
    return RedirectResponse(redirect_target, status_code=303)
    
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):

    query = req.message.strip()
    module_key = req.module_key
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
        
    retrieved = search(query, module_key=module_key)
    
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
    
@app.api_route("/login", methods=["GET", "POST"])
async def lti_login(request: Request):
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    request.session["lti_state"] = state
    request.session["lti_nonce"] = nonce

    login_hint = request.query_params.get("login_hint")
    lti_message_hint = request.query_params.get("lti_message_hint")

    params = {
        "scope": "openid",
        "response_type": "id_token",
        "client_id": MOODLE_CLIENT_ID,
        "redirect_uri": LTI_REDIRECT_URI,
        "login_hint": login_hint,
        "state": state,
        "response_mode": "form_post",
        "nonce": nonce,
        "prompt": "none",
    }

    if lti_message_hint:
        params["lti_message_hint"] = lti_message_hint

    query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)

    return RedirectResponse(f"{MOODLE_AUTH_URL}?{query}")
    
@app.post("/launch")
async def lti_launch(request: Request):
    form = await request.form()

    id_token = form.get("id_token")
    state = form.get("state")

    if not id_token:
        return HTMLResponse("Missing LTI id_token", status_code=400)

    if state != request.session.get("lti_state"):
        return HTMLResponse("Invalid LTI state", status_code=400)

    # Temporary: store token for now.
    # Next step is validating JWT properly against Moodle JWKS.
    request.session["lti_id_token"] = id_token

    return FileResponse("static/index.html")
    
@app.get("/launch")
async def lti_launch_get():
    return HTMLResponse(
        "This LTI launch URL must be opened from Moodle, not directly. "
        "If you are seeing this from Moodle, check the Tool URL setting.",
        status_code=400
    )
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print("REQUEST:", request.method, request.url)
    return await call_next(request)
