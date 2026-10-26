"""
Módulo de Gestão de Base de Dados MongoDB Atlas
Plataforma Académica de Investigação Operacional - FE-UEM
"""

import os
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import pymongo
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

ENV_PATH = Path(__file__).resolve().parent / ".env"

def load_env_vars():
    env = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env

_env = load_env_vars()
MONGODB_URI = os.environ.get("MONGODB_URI") or _env.get("MONGODB_URI", "")
DB_NAME = os.environ.get("MONGODB_DB_NAME") or _env.get("MONGODB_DB_NAME", "investigacaooperacionaldb")

_client: Optional[pymongo.MongoClient] = None
_db = None

def get_client() -> Optional[pymongo.MongoClient]:
    global _client
    if _client is None and MONGODB_URI:
        try:
            _client = pymongo.MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
                maxPoolSize=20
            )
        except Exception as e:
            print(f"[MONGODB ATLAS ERROR] Erro ao instanciar cliente: {e}")
            _client = None
    return _client

def get_db():
    global _db
    client = get_client()
    if client is not None:
        try:
            _db = client[DB_NAME]
            return _db
        except Exception as e:
            print(f"[MONGODB ATLAS ERROR] Erro ao obter base de dados '{DB_NAME}': {e}")
            return None
    return None

def is_connected() -> bool:
    try:
        client = get_client()
        if client is None:
            return False
        # Ping
        client.admin.command("ping")
        return True
    except Exception:
        return False

def get_db_status() -> Dict[str, Any]:
    connected = is_connected()
    if not connected:
        return {
            "connected": False,
            "engine": "MongoDB Atlas",
            "database": DB_NAME,
            "status": "Desconectado (ou URI em falta)"
        }
    
    db = get_db()
    collections = db.list_collection_names() if db is not None else []
    counts = {}
    if db is not None:
        for c in ["modules", "threads", "replies", "chat_history", "Users"]:
            if c in collections:
                counts[c] = db[c].count_documents({})
            else:
                counts[c] = 0

    return {
        "connected": True,
        "engine": "MongoDB Atlas (Cloud Cluster)",
        "database": DB_NAME,
        "collections": collections,
        "counts": counts,
        "status": "Online e Activo"
    }

# ==============================================================================
# GESTÃO DINÂMICA DE MÓDULOS CURRICULARES (AULAS UNIVERSITÁRIAS)
# ==============================================================================

def get_all_modules() -> List[Dict[str, Any]]:
    db = get_db()
    if db is None:
        return []
    
    modules = list(db.modules.find({}, {"_id": 0}))
    return modules

def get_module_by_key_or_id(identifier: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    if db is None:
        return None
    
    # Procura por topic_key ou id
    mod = db.modules.find_one({"topic_key": identifier}, {"_id": 0})
    if not mod:
        mod = db.modules.find_one({"id": identifier}, {"_id": 0})
    return mod

def save_or_update_module(topic_key: str, module_data: Dict[str, Any]) -> bool:
    db = get_db()
    if db is None:
        return False
    
    doc = dict(module_data)
    doc["topic_key"] = topic_key
    doc["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    db.modules.update_one(
        {"topic_key": topic_key},
        {"$set": doc},
        upsert=True
    )
    return True

# ==============================================================================
# GESTÃO DINÂMICA DE DISCUSSÕES E RESPOSTAS DO FÓRUM (MONGODB ATLAS)
# ==============================================================================

def get_next_sequence(sequence_name: str) -> int:
    db = get_db()
    if db is None:
        return int(datetime.datetime.now().timestamp())
    
    counter = db.counters.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=pymongo.ReturnDocument.AFTER
    )
    return counter["seq"]

def list_threads(module: Optional[str] = None, search: Optional[str] = None, filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    if db is None:
        return []
    
    query: Dict[str, Any] = {}
    if module and module != "Todos":
        query["module_id"] = module
        
    if search:
        s_regex = {"$regex": search, "$options": "i"}
        query["$or"] = [
            {"title": s_regex},
            {"content": s_regex},
            {"author_name": s_regex}
        ]
        
    if filter_type == "validated":
        query["is_validated"] = 1
    elif filter_type == "pending":
        query["is_validated"] = 0
        
    cursor = db.threads.find(query, {"_id": 0}).sort("created_at", pymongo.DESCENDING)
    threads = list(cursor)
    
    # Enriquecer com a contagem de respostas
    for t in threads:
        t_id = t.get("id")
        count = db.replies.count_documents({"thread_id": t_id})
        t["replies_count"] = count
        t["reply_count"] = count
        t["has_ai_reply"] = bool(db.replies.count_documents({"thread_id": t_id, "author_role": "ai_tutor"}))
        t["has_teacher_reply"] = bool(db.replies.count_documents({"thread_id": t_id, "author_role": "teacher"}))
        if isinstance(t.get("tags"), str):
            try:
                t["tags"] = json.loads(t["tags"])
            except Exception:
                t["tags"] = []
                
    return threads

def get_thread_details(thread_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    if db is None:
        return None
    
    thread = db.threads.find_one({"id": thread_id}, {"_id": 0})
    if not thread:
        return None
    
    if isinstance(thread.get("tags"), str):
        try:
            thread["tags"] = json.loads(thread["tags"])
        except Exception:
            thread["tags"] = []

    replies_cursor = db.replies.find({"thread_id": thread_id}, {"_id": 0}).sort("created_at", pymongo.ASCENDING)
    replies = list(replies_cursor)
    for r in replies:
        if isinstance(r.get("references_cited"), str):
            try:
                r["references_cited"] = json.loads(r["references_cited"])
            except Exception:
                r["references_cited"] = []

    thread["replies"] = replies
    thread["replies_count"] = len(replies)
    return thread

def create_thread(module_id: str, title: str, content: str, author_name: str, author_role: str = "student", tags: Optional[List[str]] = None) -> Dict[str, Any]:
    db = get_db()
    if db is None:
        raise RuntimeError("Ligação ao MongoDB Atlas indisponível.")
    
    new_id = get_next_sequence("threads")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    thread_doc = {
        "id": new_id,
        "module_id": module_id,
        "title": title,
        "content": content,
        "author_name": author_name,
        "author_role": author_role,
        "is_validated": 0,
        "is_closed": 0,
        "tags": tags or [module_id],
        "created_at": now_str
    }
    
    db.threads.insert_one(thread_doc)
    return get_thread_details(new_id)

def add_reply(thread_id: int, author_name: str, author_role: str, content: str, references_cited: Optional[List[str]] = None) -> Dict[str, Any]:
    db = get_db()
    if db is None:
        raise RuntimeError("Ligação ao MongoDB Atlas indisponível.")
    
    new_id = get_next_sequence("replies")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    is_endorsed = 1 if author_role == "teacher" else 0
    
    reply_doc = {
        "id": new_id,
        "thread_id": thread_id,
        "author_name": author_name,
        "author_role": author_role,
        "content": content,
        "is_endorsed": is_endorsed,
        "references_cited": references_cited or [],
        "created_at": now_str
    }
    
    db.replies.insert_one(reply_doc)
    
    # Se docente responder, valida automaticamente o tópico
    if author_role == "teacher":
        db.threads.update_one({"id": thread_id}, {"$set": {"is_validated": 1}})
        
    return get_thread_details(thread_id)

def toggle_validation(thread_id: int, reply_id: Optional[int] = None) -> Dict[str, Any]:
    db = get_db()
    if db is None:
        raise RuntimeError("Ligação ao MongoDB Atlas indisponível.")
    
    if reply_id is not None:
        rep = db.replies.find_one({"id": int(reply_id)})
        if rep:
            new_val = 0 if rep.get("is_endorsed", 0) else 1
            db.replies.update_one({"id": int(reply_id)}, {"$set": {"is_endorsed": new_val}})
    else:
        t = db.threads.find_one({"id": int(thread_id)})
        if t:
            new_val = 0 if t.get("is_validated", 0) else 1
            db.threads.update_one({"id": int(thread_id)}, {"$set": {"is_validated": new_val}})
            
    return get_thread_details(int(thread_id))

# ==============================================================================
# PARECER DO TUTOR DE IA COM RAG DINÂMICO CARREGADO DO MONGODB ATLAS
# ==============================================================================

def generate_ai_tutor_reply(thread_id: int, query_ollama_fn, default_model: str) -> Dict[str, Any]:
    db = get_db()
    thread = get_thread_details(thread_id)
    if not thread:
        raise ValueError("Discussão não encontrada.")
        
    module_name = thread.get("module_id", "")
    
    # 1. Recuperar contexto da aula do MongoDB Atlas (RAG)
    module_data = get_module_by_key_or_id(module_name)
    context_chunks = []
    
    if module_data:
        title = module_data.get("title", module_name)
        theorems = module_data.get("theorems", "")
        formulation = module_data.get("formulation", "")
        solved = module_data.get("solvedExercise", {})
        
        context_chunks.append(f"Módulo Curricular: {title}")
        if theorems:
            context_chunks.append(f"Teoremas Fundamentais: {theorems[:700]}")
        if formulation:
            context_chunks.append(f"Formulação Formal: {formulation[:700]}")
        if solved and isinstance(solved, dict):
            context_chunks.append(f"Exemplo Resolvido de Referência: {solved.get('title', '')} - {solved.get('problem', '')[:400]}")
            
    rag_context = "\n\n".join(context_chunks)
    
    # 2. Resumo da discussão existente
    history_summary = []
    for r in thread.get("replies", []):
        history_summary.append(f"[{r['author_role'].upper()} - {r['author_name']}]: {r['content']}")
    discussion_text = "\n".join(history_summary)

    system_prompt = f"""Actue como o Tutor Académico Virtual de Inteligência Artificial em Investigação Operacional da Faculdade de Engenharia da Universidade Eduardo Mondlane (FE-UEM).
O seu papel no Fórum de Dúvidas é emitir um parecer pedagógico claro, rigoroso, respeitoso e matematicamente exacto para esclarecer a dúvida do estudante ou contribuir para a discussão em curso.

Directrizes de Resposta:
1. Comece saudando cordialmente o estudante e os intervenientes.
2. Seja cirúrgico: fundamente a explicação nos teoremas e axiomas de Investigação Operacional.
3. Se envolver formulações ou cálculos, utilize LaTeX (MathJax) com \\( ... \\) para variáveis e \\[ ... \\] para equações em bloco.
4. Faça citações directas à literatura científica clássica (Hillier & Lieberman, Taha, Bazaraa) entre parênteses rectos (ex: [1], [2]).
5. Apresente no fim uma lista com as referências citadas.
6. Não utilize asteriscos markdown (** ou *). Em vez disso, use formatação semântica com tags HTML <strong>, <em>, <ul>, <li>.

Contexto da Aula Extraído do Repositório Académico FE-UEM (RAG):
{rag_context}
"""

    user_query = f"""Dúvida colocada no Fórum pelo estudante {thread['author_name']}:
Título: {thread['title']}
Descrição da Dúvida:
{thread['content']}

Histórico de Intervenções Prévias:
{discussion_text if discussion_text else '(Nenhuma resposta prévia)'}

Por favor, elabore o Parecer do Tutor de IA sobre esta discussão."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    ai_reply_text = ""
    try:
        ai_reply_text = query_ollama_fn(default_model, messages)
    except Exception as e:
        print(f"[AI TUTOR MONGODB] Erro ao invocar modelo IA: {e}")
        
    if not ai_reply_text or "não posso responder" in ai_reply_text.lower():
        # Fallback científico de alta precisão FE-UEM
        ai_reply_text = f"""<p>Saudações académicas, <strong>{thread['author_name']}</strong> e prezados colegas.</p>
<p>Analisando a questão colocada sob o prisma metodológico de <strong>{module_name}</strong> leccionado na FE-UEM:</p>
<div style="background-color:#f8fafc; border-left:4px solid #0284c7; padding:12px 16px; margin:14px 0; border-radius:4px;">
  <strong>Parecer Metodológico do Tutor de IA:</strong><br>
  A resolução de problemas nesta área requer a estrita observância das condições canónicas de viabilidade e de optimalidade.
  Recomenda-se a estruturação formal das variáveis de decisão, a verificação da convexidade da região admissível e a aplicação criteriosa das regras de transição algorítmica.
</div>
<p>Para aprofundamento rigoroso, consulte a secção de Teoremas e Formulações do Módulo na Sala de Aula Digital.</p>
<hr style="border:none; border-top:1px solid #e2e8f0; margin:14px 0;">
<p><strong>Referências Verificáveis:</strong></p>
<ul>
  <li>[1] Hillier, F. S., & Lieberman, G. J. (2021). <em>Introduction to Operations Research</em> (11th ed.). McGraw-Hill Education.</li>
  <li>[2] Taha, H. A. (2017). <em>Operations Research: An Introduction</em> (10th ed.). Pearson.</li>
</ul>"""

    return add_reply(
        thread_id=thread_id,
        author_name="Tutor Académico de IA (RAG - MongoDB Atlas)",
        author_role="ai_tutor",
        content=ai_reply_text,
        references_cited=["Hillier & Lieberman (2021)", "Taha (2017)", "Base Curricular FE-UEM"]
    )

# ==============================================================================
# POVOAMENTO / AUTO-SEED DO MONGODB ATLAS
# ==============================================================================

def seed_atlas_if_empty():
    """
    Semeia o MongoDB Atlas com os 7 módulos curriculares completos e as
    discussões académicas do fórum se as colecções estiverem vazias.
    """
    db = get_db()
    if db is None:
        print("[MONGODB ATLAS] Não foi possível ligar ao cluster para efectuar o seed.")
        return False

    # 1. Povoar Módulos Curriculares
    modules_count = db.modules.count_documents({})
    if modules_count == 0:
        json_path = Path(__file__).resolve().parent / "modules_extracted.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    modules_dict = json.load(f)
                
                docs_to_insert = []
                for topic_name, data in modules_dict.items():
                    data["topic_key"] = topic_name
                    data["created_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    docs_to_insert.append(data)
                
                if docs_to_insert:
                    db.modules.insert_many(docs_to_insert)
                    print(f"[MONGODB ATLAS SEED] Inseridos {len(docs_to_insert)} módulos curriculares com sucesso na colecção 'modules'!")
            except Exception as e:
                print(f"[MONGODB ATLAS SEED ERROR] Erro ao inserir módulos: {e}")
        else:
            print("[MONGODB ATLAS SEED] Ficheiro 'modules_extracted.json' não encontrado para auto-seed.")

    # 2. Povoar Tópicos do Fórum
    threads_count = db.threads.count_documents({})
    if threads_count == 0:
        print("[MONGODB ATLAS SEED] A semear discussões académicas no Fórum...")
        now = datetime.datetime.now()
        
        # Tópico 1
        t1 = create_thread(
            module_id="Programação Linear",
            title="Como modelar restrições de misturas (Blending Problem) quando as percentagens dependem do volume total?",
            content="Colegas e Docentes, estou com uma dúvida no exercício da refinaria de combustíveis da Matola. Quando a percentagem de enxofre deve ser inferior a 1.5% do volume total da mistura $V_{total} = x_1 + x_2 + x_3$, a inequação original surge como $\\frac{0.02x_1 + 0.01x_2 + 0.005x_3}{x_1 + x_2 + x_3} \\le 0.015$. Como converter isto numa inequação linear canónica sem violar a linearidade?",
            author_name="Edilson Macamo (Estudante)",
            author_role="student",
            tags=["Programação Linear", "Misturas", "Modelagem", "Refinaria"]
        )
        
        # Resposta do Professor ao Tópico 1
        add_reply(
            thread_id=t1["id"],
            author_name="Prof. Doutor Manuel Sitoe (Docente)",
            author_role="teacher",
            content="""Excelente questão, Edilson! O princípio da linearização baseia-se na propriedade da multiplicação cruzada sob a premissa de que o volume total é estritamente positivo ($x_1 + x_2 + x_3 > 0$). Multiplicando ambos os membros por $(x_1 + x_2 + x_3)$, obtém-se: 
\\[ 0.02x_1 + 0.01x_2 + 0.005x_3 \\le 0.015(x_1 + x_2 + x_3) \\]
Agrupando os termos por variável:
\\[ (0.02 - 0.015)x_1 + (0.01 - 0.015)x_2 + (0.005 - 0.015)x_3 \\le 0 \\]
\\[ 0.005x_1 - 0.005x_2 - 0.01x_3 \\le 0 \\]
Esta forma é perfeitamente linear e canónica, respeitando os axiomas da PL.""",
            references_cited=["Hillier & Lieberman (2021), cap. 3 - Blending Models"]
        )
        
        # Tópico 2
        t2 = create_thread(
            module_id="Método Simplex Primal",
            title="Empate no teste da razão mínima de Dantzig: como proceder para evitar ciclagem?",
            content="Quando efectuamos o teste da razão $\\min \\{b_i / a_{ik} : a_{ik} > 0\\}$ e encontramos duas linhas com o mesmo valor mínimo exacto, qual é o protocolo rigoroso para desempate? Existe risco real de ciclo infinito nos exercícios da FE-UEM?",
            author_name="Sheila Machel (Estudante)",
            author_role="student",
            tags=["Simplex", "Degenerescência", "Ciclagem", "Razão Mínima"]
        )
        
        add_reply(
            thread_id=t2["id"],
            author_name="Prof. Doutor Manuel Sitoe (Docente)",
            author_role="teacher",
            content="""Olá Sheila. Esse fenómeno traduz a ocorrência de <strong>degenerescência primal</strong> (uma ou mais variáveis básicas tomam o valor zero na iteração seguinte). 
Para evitar o fenómeno teórico de ciclagem infinita, a literatura consagra a <em>Regra de Bland</em> (escolha da variável de menor índice entre as candidatas a sair da base) ou a técnica da perturbação lexicográfica. 
Nos exercícios práticos da faculdade, a regra de menor índice é a convenção padrão adoptada nas aulas laboratoriais.""",
            references_cited=["Bazaraa, Jarvis & Sherali (2010), Linear Programming and Network Flows"]
        )
        
        # Tópico 3
        t3 = create_thread(
            module_id="Dualidade e Sensibilidade",
            title="Por que razão o preço-sombra de uma restrição com folga positiva é obrigatoriamente zero?",
            content="Na análise económica de sensibilidade, se numa fábrica ainda sobrarem 50 horas de torno mecânico ($s_1 = 50 > 0$), por que razão o dual $y_1$ associado tem de ser nulo?",
            author_name="Cremildo Langa (Estudante)",
            author_role="student",
            tags=["Dualidade", "Preço-Sombra", "Folgas Complementares"]
        )

        print("[MONGODB ATLAS SEED] Discussões semeadas com sucesso no MongoDB Atlas!")

    return True

if __name__ == "__main__":
    print("A testar módulo db_mongo.py...")
    status = get_db_status()
    print("Status:", json.dumps(status, indent=2, ensure_ascii=False))
    if status["connected"]:
        seed_atlas_if_empty()
        print("Módulos no Atlas:", len(get_all_modules()))
        print("Tópicos no Atlas:", len(list_threads()))
