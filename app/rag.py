import os
import faiss
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

Data_Dir = "data"
Embed_Model = "text-embedding-3-small"
Chunk_Size = 700
Top_K = 3

documents = []
index = None

def parse_markdown_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        raw_text = f.read()
    
    lines = raw_text.splitlines()
    
    title = None
    url = None
    category = None
    
    content_start_idx = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if stripped.startswith("Title:"):
            title = stripped.replace("Title:", "", 1).strip()
        elif stripped.startswith("URL:"):
            url = stripped.replace("URL:", "", 1).strip()
        elif stripped.startswith("Category:"):
            category = stripped.replace("Category:", "", 1).strip()
        elif stripped == "":
            content_start_idx = i + 1
            break
            
    content = "\n".join(lines[content_start_idx:]).strip()
    
    if not title:
        title = os.path.basename(path)
        
    return {
        "title": title,
        "url": url,
        "category": category,
        "content": content
    }

def load_documents():
    docs = []
    for filename in os.listdir(Data_Dir):
        if filename.endswith(".md"):
            path = os.path.join(Data_Dir, filename)
            parsed = parse_markdown_file(path)
            docs.extend(chunk_text(parsed))
    return docs
    
def chunk_text(doc: dict, chunk_size: int = Chunk_Size):
    chunks = []
    current = ""
    
    paragraphs = doc["content"].split("\n\n")
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(current) + len(paragraph) < chunk_size:
            current += paragraph + "\n\n"
        else:
            if current.strip():
                chunks.append({"title": doc["title"],"url": doc["url"], "category": doc["category"], "content": current.strip()})
            current = paragraph + "\n\n"
            
    if current.strip():
        chunks.append({"title": doc["title"], "url": doc["url"], "category": doc["category"], "content": current.strip()})
    return chunks

def embed_texts(texts):
    response = client.embeddings.create(
        model=Embed_Model,
        input=texts
    )
    return [d.embedding for d in response.data]
    
def build_index():
    global documents, index
    documents = load_documents()
    embeddings = embed_texts([doc["content"] for doc in documents])
    matrix = np.array(embeddings).astype("float32")
    index = faiss.IndexFlatL2(matrix.shape[1])
    index.add(matrix)

def search(query: str, top_k: int = Top_K):
    global index, documents
    if index is None:
        build_index()
        
    query_embedding = embed_texts([query])[0]
    q = np.array([query_embedding]).astype("float32")
    distances, indices = index.search(q, top_k)
    
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        results.append({
            "title": documents[idx]["title"],
            "url": documents[idx]["url"],
            "category": documents[idx]["category"],
            "content": documents[idx]["content"],
            "score": float(dist)
        })
    return results