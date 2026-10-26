import sqlite3
import json
import datetime
from pathlib import Path
import db_mongo

DB_PATH = Path(__file__).resolve().parent / "forum.db"

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if db_mongo.is_connected():
        print("[DATABASE] A inicializar MongoDB Atlas como motor de dados principal...")
        db_mongo.seed_atlas_if_empty()
        return

    # Fallback SQLite
    print("[DATABASE] MongoDB Atlas offline. A inicializar SQLite local de contingência...")
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forum_threads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        author_name TEXT NOT NULL,
        author_role TEXT NOT NULL,
        is_validated INTEGER DEFAULT 0,
        is_closed INTEGER DEFAULT 0,
        tags TEXT DEFAULT '[]',
        created_at TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forum_replies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id INTEGER NOT NULL,
        author_name TEXT NOT NULL,
        author_role TEXT NOT NULL,
        content TEXT NOT NULL,
        is_endorsed INTEGER DEFAULT 0,
        references_cited TEXT DEFAULT '[]',
        created_at TEXT NOT NULL,
        FOREIGN KEY (thread_id) REFERENCES forum_threads(id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    cursor.execute("SELECT COUNT(*) as count FROM forum_threads")
    count = cursor.fetchone()["count"]
    if count == 0:
        seed_forum_data(conn)
    conn.close()

def seed_forum_data(conn):
    cursor = conn.cursor()
    now = datetime.datetime.now()
    
    t1_time = (now - datetime.timedelta(days=2, hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO forum_threads (module_id, title, content, author_name, author_role, is_validated, is_closed, tags, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "Programação Linear",
        "Como modelar restrições de misturas (Blending Problem) quando as percentagens dependem do volume total?",
        "Colegas e Docentes, estou com uma dúvida no exercício da refinaria de combustíveis da Matola. Quando a percentagem de enxofre deve ser inferior a 1.5% do volume total da mistura $V_{total} = x_1 + x_2 + x_3$, a inequação original surge como $\\frac{0.02x_1 + 0.01x_2 + 0.005x_3}{x_1 + x_2 + x_3} \\le 0.015$. Como converter isto numa inequação linear canónica sem violar a linearidade?",
        "Edilson Macamo (Estudante)",
        "student",
        1,
        0,
        json.dumps(["Programação Linear", "Misturas", "Modelagem", "Refinaria"]),
        t1_time
    ))
    t1_id = cursor.lastrowid
    
    r1_prof_time = (now - datetime.timedelta(days=2, hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO forum_replies (thread_id, author_name, author_role, content, is_endorsed, references_cited, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        t1_id,
        "Prof. Doutor Manuel Sitoe (Docente)",
        "teacher",
        "Excelente questão, Edilson! O princípio da linearização baseia-se na propriedade da multiplicação cruzada sob a premissa de que o volume total é estritamente positivo ($x_1 + x_2 + x_3 > 0$). Multiplicando ambos os membros por $(x_1 + x_2 + x_3)$, obtém-se: \n\\[ 0.02x_1 + 0.01x_2 + 0.005x_3 \\le 0.015(x_1 + x_2 + x_3) \\]\nAgrupando os termos por variável:\n\\[ (0.02 - 0.015)x_1 + (0.01 - 0.015)x_2 + (0.005 - 0.015)x_3 \\le 0 \\]\n\\[ 0.005x_1 - 0.005x_2 - 0.01x_3 \\le 0 \\]\nEsta forma é perfeitamente linear e canónica, respeitando os axiomas da PL.",
        1,
        json.dumps(["Hillier & Lieberman (2021), cap. 3 - Blending Models"]),
        r1_prof_time
    ))
    
    conn.commit()

def list_threads(module=None, search=None, filter_type=None):
    if db_mongo.is_connected():
        return db_mongo.list_threads(module=module, search=search, filter_type=filter_type)

    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT t.id, t.module_id, t.title, t.content, t.author_name, t.author_role,
               t.is_validated, t.is_closed, t.tags, t.created_at,
               COUNT(r.id) as reply_count,
               MAX(r.created_at) as last_reply_at
        FROM forum_threads t
        LEFT JOIN forum_replies r ON t.id = r.thread_id
        WHERE 1=1
    """
    params = []
    
    if module and module != "Todos":
        query += " AND t.module_id = ?"
        params.append(module)
        
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query += " AND (LOWER(t.title) LIKE ? OR LOWER(t.content) LIKE ? OR LOWER(t.tags) LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern])
        
    if filter_type == "validated":
        query += " AND t.is_validated = 1"
    elif filter_type == "unanswered":
        query += " GROUP BY t.id HAVING reply_count = 0"
    elif filter_type == "frequent":
        query += " GROUP BY t.id HAVING reply_count >= 2"
        
    if "GROUP BY" not in query:
        query += " GROUP BY t.id"
        
    query += " ORDER BY t.is_validated DESC, t.id DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    threads = []
    for r in rows:
        threads.append({
            "id": r["id"],
            "module_id": r["module_id"],
            "title": r["title"],
            "content": r["content"],
            "author_name": r["author_name"],
            "author_role": r["author_role"],
            "is_validated": bool(r["is_validated"]),
            "is_closed": bool(r["is_closed"]),
            "tags": json.loads(r["tags"] or "[]"),
            "created_at": r["created_at"],
            "reply_count": r["reply_count"],
            "last_reply_at": r["last_reply_at"] or r["created_at"]
        })
    conn.close()
    return threads

def get_thread_details(thread_id):
    if db_mongo.is_connected():
        return db_mongo.get_thread_details(int(thread_id))

    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM forum_threads WHERE id = ?", (thread_id,))
    thread_row = cursor.fetchone()
    if not thread_row:
        conn.close()
        return None
        
    cursor.execute("""
        SELECT * FROM forum_replies 
        WHERE thread_id = ? 
        ORDER BY id ASC
    """, (thread_id,))
    reply_rows = cursor.fetchall()
    
    replies = []
    for rr in reply_rows:
        replies.append({
            "id": rr["id"],
            "thread_id": rr["thread_id"],
            "author_name": rr["author_name"],
            "author_role": rr["author_role"],
            "content": rr["content"],
            "is_endorsed": bool(rr["is_endorsed"]),
            "references_cited": json.loads(rr["references_cited"] or "[]"),
            "created_at": rr["created_at"]
        })
        
    thread = {
        "id": thread_row["id"],
        "module_id": thread_row["module_id"],
        "title": thread_row["title"],
        "content": thread_row["content"],
        "author_name": thread_row["author_name"],
        "author_role": thread_row["author_role"],
        "is_validated": bool(thread_row["is_validated"]),
        "is_closed": bool(thread_row["is_closed"]),
        "tags": json.loads(thread_row["tags"] or "[]"),
        "created_at": thread_row["created_at"],
        "replies": replies,
        "reply_count": len(replies)
    }
    conn.close()
    return thread

def create_thread(module_id, title, content, author_name="Estudante FE-UEM", author_role="student", tags=None):
    if db_mongo.is_connected():
        return db_mongo.create_thread(module_id, title, content, author_name, author_role, tags)

    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tags_json = json.dumps(tags if tags else [module_id])
    
    cursor.execute("""
        INSERT INTO forum_threads (module_id, title, content, author_name, author_role, is_validated, is_closed, tags, created_at)
        VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?)
    """, (module_id, title, content, author_name, author_role, tags_json, now_str))
    
    thread_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_thread_details(thread_id)

def add_reply(thread_id, author_name, author_role, content, references_cited=None, is_endorsed=0):
    if db_mongo.is_connected():
        return db_mongo.add_reply(thread_id, author_name, author_role, content, references_cited)

    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    refs_json = json.dumps(references_cited if references_cited else [])
    
    cursor.execute("""
        INSERT INTO forum_replies (thread_id, author_name, author_role, content, is_endorsed, references_cited, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (thread_id, author_name, author_role, content, is_endorsed, refs_json, now_str))
    
    if author_role == "teacher":
        cursor.execute("UPDATE forum_threads SET is_validated = 1 WHERE id = ?", (thread_id,))
        
    conn.commit()
    conn.close()
    return get_thread_details(thread_id)

def toggle_validation(thread_id, reply_id=None):
    if db_mongo.is_connected():
        return db_mongo.toggle_validation(thread_id, reply_id)

    conn = get_connection()
    cursor = conn.cursor()
    if reply_id:
        cursor.execute("UPDATE forum_replies SET is_endorsed = 1 - is_endorsed WHERE id = ?", (reply_id,))
    else:
        cursor.execute("UPDATE forum_threads SET is_validated = 1 - is_validated WHERE id = ?", (thread_id,))
    conn.commit()
    conn.close()
    return get_thread_details(thread_id)

def generate_ai_tutor_reply(thread_id, query_ollama_fn=None, default_model="llama3.2:3b"):
    if db_mongo.is_connected():
        return db_mongo.generate_ai_tutor_reply(thread_id, query_ollama_fn, default_model)

    thread = get_thread_details(thread_id)
    if not thread:
        return None
        
    module_name = thread["module_id"]
    title = thread["title"]
    question = thread["content"]
    
    ai_content = f"""<article><header><h4>Parecer Didáctico do Tutor de IA (FE-UEM)</h4></header><p>Em análise à dúvida colocada sobre <strong>{title}</strong> no módulo <em>{module_name}</em>: a correcta formulação requer o cumprimento rigoroso das propriedades canónicas de viabilidade e optimalidade.</p></article>"""
    return add_reply(thread_id, "Tutor Académico de IA (RAG)", "ai_tutor", ai_content, ["Hillier & Lieberman (2021)"])
