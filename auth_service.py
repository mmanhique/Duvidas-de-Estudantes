"""
Serviço de Autenticação, Controlo de Acesso Baseado em Funções (RBAC) e Gestão Académica
Plataforma de Investigação Operacional - FE-UEM
"""

import hashlib
import secrets
import datetime
import re
from typing import Dict, Any, List, Optional
import db_mongo

def hash_password(password: str) -> tuple[str, str]:
    """Gera um salt criptográfico e a hash PBKDF2-HMAC-SHA256 (100.000 iterações)."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return salt, pw_hash

def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    """Verifica com comparação em tempo constante contra ataques de temporização."""
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return secrets.compare_digest(pw_hash, stored_hash)

def sanitize_user(user_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Remove campos sensíveis (hashes, salts e tokens de recuperação)."""
    clean = dict(user_doc)
    clean.pop("password_hash", None)
    clean.pop("salt", None)
    clean.pop("reset_token", None)
    clean.pop("reset_token_expires", None)
    clean.pop("_id", None)
    return clean

# ==============================================================================
# FALLBACK EM MEMÓRIA PARA AMBIENTES SERVERLESS (VERCEL) OU OFFLINE SEM MONGODB
# ==============================================================================

class _FallbackCollection:
    def __init__(self):
        self._docs: List[Dict[str, Any]] = []

    def create_index(self, *args, **kwargs):
        return None

    def _matches(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for k, v in query.items():
            val = doc.get(k)
            if isinstance(v, dict) and "$in" in v:
                if val not in v["$in"]:
                    return False
            elif val != v:
                return False
        return True

    def count_documents(self, query: Dict[str, Any]) -> int:
        return sum(1 for d in self._docs if self._matches(d, query))

    def insert_one(self, doc: Dict[str, Any]):
        self._docs.append(dict(doc))

    def insert_many(self, docs: List[Dict[str, Any]]):
        for d in docs:
            self._docs.append(dict(d))

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for d in self._docs:
            if self._matches(d, query):
                return dict(d)
        return None

    def find(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        results = []
        for d in self._docs:
            if self._matches(d, query):
                copy_d = dict(d)
                if projection:
                    for pk, pv in projection.items():
                        if pv == 0:
                            copy_d.pop(pk, None)
                results.append(copy_d)
        return results

    def _apply_set(self, target: Dict[str, Any], fields: Dict[str, Any]):
        for fk, fv in fields.items():
            if "." in fk:
                parts = fk.split(".")
                curr = target
                for p in parts[:-1]:
                    if p not in curr or not isinstance(curr[p], dict):
                        curr[p] = {}
                    curr = curr[p]
                curr[parts[-1]] = fv
            else:
                target[fk] = fv

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        for d in self._docs:
            if self._matches(d, query):
                if "$set" in update:
                    self._apply_set(d, update["$set"])
                return
        if upsert:
            new_doc = dict(query)
            if "$setOnInsert" in update:
                self._apply_set(new_doc, update["$setOnInsert"])
            if "$set" in update:
                self._apply_set(new_doc, update["$set"])
            self._docs.append(new_doc)

    def update_many(self, query: Dict[str, Any], update: Dict[str, Any]):
        for d in self._docs:
            if self._matches(d, query) and "$set" in update:
                self._apply_set(d, update["$set"])

    def delete_one(self, query: Dict[str, Any]):
        for i, d in enumerate(self._docs):
            if self._matches(d, query):
                self._docs.pop(i)
                return

    def delete_many(self, query: Dict[str, Any]):
        self._docs = [d for d in self._docs if not self._matches(d, query)]

    def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self._docs:
            return []
        scores = [d.get("quiz_score", 0) for d in self._docs if isinstance(d.get("quiz_score"), (int, float))]
        avg = (sum(scores) / len(scores)) if scores else 0
        return [{"_id": None, "avg_score": avg}]


class _FallbackDB:
    def __init__(self):
        self.Users = _FallbackCollection()
        self.sessions = _FallbackCollection()
        self.student_progress = _FallbackCollection()
        self.threads = _FallbackCollection()
        self.replies = _FallbackCollection()


_fallback_db = _FallbackDB()


def _get_auth_db():
    if db_mongo.is_connected():
        db = _get_auth_db()
        if db is not None:
            return db
    return _fallback_db


# ==============================================================================
# INICIALIZAÇÃO E CONTAS INSTITUCIONAIS PRÉ-CONFIGURADAS (FE-UEM)
# ==============================================================================

def init_users_and_roles():
    """Garante a existência de índices e das contas institucionais padrão."""
    db = _get_auth_db()
    if db is None:
        print("[AUTH SERVICE] Erro: Base de dados indisponível para inicializar utilizadores.")
        return False

    # 1. Criar índices únicos
    try:
        db.Users.create_index("email", unique=True)
        db.sessions.create_index("session_token", unique=True)
        db.sessions.create_index("created_at")
        db.student_progress.create_index([("email", 1), ("module_id", 1)], unique=True)
    except Exception as ie:
        print(f"[AUTH SERVICE INDEX] Aviso sobre índices: {ie}")

    # 2. Verificar se já existem utilizadores
    count = db.Users.count_documents({})
    if count == 0:
        print("[AUTH SERVICE] A inicializar contas institucionais padrão da FE-UEM...")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # A. Docente Regente da Disciplina
        s_reg, h_reg = hash_password("Regente@2026")
        regente = {
            "name": "Prof. Doutor Manuel Sitoe",
            "email": "regente@fe.uem.mz",
            "password_hash": h_reg,
            "salt": s_reg,
            "role": "teacher_regent",
            "role_title": "Docente Regente",
            "status": "active",
            "department": "Departamento de Engenharia Mecânica / Produção",
            "institution": "Faculdade de Engenharia - UEM",
            "disciplines": {
                "Investigação Operacional": {
                    "role": "regent",
                    "permissions": [
                        "manage_modules",
                        "publish_lessons",
                        "manage_assessments",
                        "moderate_forum",
                        "validate_answers",
                        "view_analytics",
                        "manage_instructors",
                        "supervise_ai"
                    ]
                }
            },
            "created_at": now,
            "last_login": now
        }

        # B. Docente Assistente da Disciplina
        s_ast, h_ast = hash_password("Assistente@2026")
        assistente = {
            "name": "Prof. Doutora Anabela Cossa",
            "email": "assistente@fe.uem.mz",
            "password_hash": h_ast,
            "salt": s_ast,
            "role": "teacher_assistant",
            "role_title": "Docente Assistente",
            "status": "active",
            "department": "Departamento de Engenharia Electrotécnica",
            "institution": "Faculdade de Engenharia - UEM",
            "disciplines": {
                "Investigação Operacional": {
                    "role": "assistant",
                    "permissions": [
                        "edit_exercises",
                        "moderate_forum",
                        "view_analytics",
                        "answer_queries"
                    ]
                }
            },
            "created_at": now,
            "last_login": now
        }

        # C. Estudante de Demonstração
        s_est, h_est = hash_password("Estudante@2026")
        estudante = {
            "name": "Edilson Macamo",
            "email": "estudante@fe.uem.mz",
            "password_hash": h_est,
            "salt": s_est,
            "role": "student",
            "role_title": "Estudante",
            "status": "active",
            "student_number": "2024-ENG-089",
            "course": "Licenciatura em Engenharia Mecânica",
            "institution": "Faculdade de Engenharia - UEM",
            "disciplines": {
                "Investigação Operacional": {
                    "role": "student",
                    "enrolled_at": now
                }
            },
            "created_at": now,
            "last_login": now
        }

        db.Users.insert_many([regente, assistente, estudante])
        print("[AUTH SERVICE] Contas institucionais criadas com sucesso (Regente, Assistente e Estudante).")

    return True

# ==============================================================================
# REGISTO, AUTENTICAÇÃO E SESSÕES
# ==============================================================================

def register_user(
    name: str,
    email: str,
    password: str,
    requested_role: str = "student",
    student_number: Optional[str] = None,
    course_department: Optional[str] = None
) -> Dict[str, Any]:
    db = _get_auth_db()
    if db is None:
        raise RuntimeError("Base de dados MongoDB Atlas inacessível.")

    name = name.strip()
    email = email.strip().lower()
    password = password.strip()

    if not name or len(name) < 3:
        raise ValueError("O nome completo deve ter pelo menos 3 caracteres.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("Por favor, introduza um endereço de correio electrónico válido.")
    if len(password) < 6:
        raise ValueError("A palavra-passe deve conter pelo menos 6 caracteres.")

    # Verificar duplicação de email
    existing = db.Users.find_one({"email": email})
    if existing:
        raise ValueError("Já existe um utilizador registado com este endereço de correio electrónico.")

    salt, pw_hash = hash_password(password)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Regra estrita de atribuição de privilégios:
    # Auto-registo de docente cria conta pendente de autorização do Regente
    if requested_role in ["teacher", "docente", "teacher_assistant", "teacher_regent"]:
        assigned_role = "teacher_applicant"
        assigned_title = "Candidato a Docente (Pendente)"
        status = "pending_approval"
        msg = "Conta de docente registada com sucesso! Por motivos de segurança académica, a activação das permissões depende da aprovação administrativa do Docente Regente."
    else:
        assigned_role = "student"
        assigned_title = "Estudante"
        status = "active"
        msg = "Conta de estudante criada com sucesso!"

    user_doc = {
        "name": name,
        "email": email,
        "password_hash": pw_hash,
        "salt": salt,
        "role": assigned_role,
        "role_title": assigned_title,
        "status": status,
        "student_number": student_number or f"ENG-{datetime.datetime.now().year}-{secrets.randbelow(9000)+1000}",
        "course": course_department or "Engenharia (FE-UEM)",
        "institution": "Faculdade de Engenharia - UEM",
        "disciplines": {
            "Investigação Operacional": {
                "role": assigned_role,
                "status": status,
                "registered_at": now
            }
        },
        "created_at": now,
        "last_login": now
    }

    db.Users.insert_one(user_doc)
    return {
        "success": True,
        "message": msg,
        "status": status,
        "user": sanitize_user(user_doc)
    }

def login_user(email: str, password: str) -> Dict[str, Any]:
    db = _get_auth_db()
    if db is None:
        raise RuntimeError("Base de dados MongoDB Atlas inacessível.")

    email = email.strip().lower()
    user = db.Users.find_one({"email": email})
    if not user:
        raise ValueError("Credenciais inválidas. Verifique o correio electrónico e a palavra-passe.")

    if not verify_password(password, user["salt"], user["password_hash"]):
        raise ValueError("Credenciais inválidas. Verifique o correio electrónico e a palavra-passe.")

    if user.get("status") == "pending_approval":
        raise ValueError("A sua conta de docente encontra-se a aguardar autorização administrativa do Docente Regente.")
    if user.get("status") == "suspended":
        raise ValueError("Esta conta académica encontra-se temporariamente suspensa pela regência.")

    # Gerar token de sessão criptográfico
    token = secrets.token_hex(32)
    now = datetime.datetime.now()
    expires_at = (now + datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    session_doc = {
        "session_token": token,
        "email": email,
        "name": user["name"],
        "role": user["role"],
        "created_at": now_str,
        "expires_at": expires_at
    }

    db.sessions.insert_one(session_doc)
    db.Users.update_one({"email": email}, {"$set": {"last_login": now_str}})

    return {
        "success": True,
        "token": token,
        "user": sanitize_user(user)
    }

def get_user_from_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    db = _get_auth_db()
    if db is None:
        return None

    session = db.sessions.find_one({"session_token": token})
    if not session:
        return None

    # Verificar expiração
    expires_at = session.get("expires_at", "")
    if expires_at and expires_at < datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
        db.sessions.delete_one({"session_token": token})
        return None

    user = db.Users.find_one({"email": session["email"]})
    if not user:
        return None

    return sanitize_user(user)

def logout_user(token: str) -> bool:
    db = _get_auth_db()
    if db is None:
        return False
    db.sessions.delete_one({"session_token": token})
    return True

# ==============================================================================
# RECUPERAÇÃO DE PALAVRA-PASSE
# ==============================================================================

def request_password_reset(email: str) -> Dict[str, Any]:
    db = _get_auth_db()
    if db is None:
        raise RuntimeError("Base de dados inacessível.")

    email = email.strip().lower()
    user = db.Users.find_one({"email": email})
    if not user:
        raise ValueError("Não foi encontrada nenhuma conta associada a este endereço de e-mail.")

    # Código numérico de 6 dígitos para verificação rápida e segura
    reset_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

    db.Users.update_one(
        {"email": email},
        {"$set": {"reset_token": reset_code, "reset_token_expires": expires_at}}
    )

    return {
        "success": True,
        "email": email,
        "reset_code": reset_code, # Disponibilizado imediatamente na interface para validação
        "expires_in_minutes": 30,
        "message": f"Código de segurança gerado: {reset_code}. Válido por 30 minutos."
    }

def complete_password_reset(email: str, reset_code: str, new_password: str) -> Dict[str, Any]:
    db = _get_auth_db()
    if db is None:
        raise RuntimeError("Base de dados inacessível.")

    email = email.strip().lower()
    reset_code = reset_code.strip()
    new_password = new_password.strip()

    if len(new_password) < 6:
        raise ValueError("A nova palavra-passe deve conter pelo menos 6 caracteres.")

    user = db.Users.find_one({"email": email})
    if not user:
        raise ValueError("Utilizador não encontrado.")

    stored_token = user.get("reset_token")
    expires = user.get("reset_token_expires", "")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not stored_token or stored_token != reset_code:
        raise ValueError("Código de recuperação inválido ou incorrecto.")
    if expires and expires < now_str:
        raise ValueError("O código de recuperação expirou. Por favor solicite um novo código.")

    salt, pw_hash = hash_password(new_password)
    db.Users.update_one(
        {"email": email},
        {
            "$set": {
                "password_hash": pw_hash,
                "salt": salt,
                "reset_token": None,
                "reset_token_expires": None
            }
        }
    )

    # Encerrar sessões antigas
    db.sessions.delete_many({"email": email})

    return {
        "success": True,
        "message": "Palavra-passe actualizada com sucesso! Pode agora iniciar sessão com a nova credencial."
    }

# ==============================================================================
# GESTÃO PEDAGÓGICA E RBAC (EXCLUSIVO DOCENTE REGENTE E ASSISTENTE)
# ==============================================================================

def list_academic_users(requester_role: str) -> List[Dict[str, Any]]:
    """Permite aos docentes consultar a lista de estudantes e equipa docente."""
    if requester_role not in ["teacher_regent", "teacher_assistant"]:
        raise PermissionError("Acesso reservado aos docentes da disciplina.")

    db = _get_auth_db()
    if db is None:
        return []

    users = list(db.Users.find({}, {"_id": 0, "password_hash": 0, "salt": 0, "reset_token": 0}))
    return users

def update_user_status_and_role(
    requester_user: Dict[str, Any],
    target_email: str,
    new_role: str,
    new_status: str = "active",
    custom_permissions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Apenas o Docente Regente tem autoridade para aprovar ou alterar papéis de docentes."""
    if requester_user.get("role") != "teacher_regent":
        raise PermissionError("Apenas o Docente Regente possui competência para gerir permissões e autorizar docentes.")

    db = _get_auth_db()
    if db is None:
        raise RuntimeError("Base de dados inacessível.")

    target_email = target_email.strip().lower()
    target = db.Users.find_one({"email": target_email})
    if not target:
        raise ValueError("Utilizador-alvo não encontrado.")

    role_titles = {
        "teacher_regent": "Docente Regente",
        "teacher_assistant": "Docente Assistente",
        "student": "Estudante",
        "teacher_applicant": "Candidato a Docente"
    }

    title = role_titles.get(new_role, "Utilizador")

    update_fields = {
        "role": new_role,
        "role_title": title,
        "status": new_status,
        "disciplines.Investigação Operacional.role": new_role,
        "disciplines.Investigação Operacional.status": new_status,
        "updated_by": requester_user.get("email"),
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if custom_permissions is not None:
        update_fields["disciplines.Investigação Operacional.permissions"] = custom_permissions

    db.Users.update_one({"email": target_email}, {"$set": update_fields})
    
    # Actualizar também sessões activas desse utilizador
    db.sessions.update_many({"email": target_email}, {"$set": {"role": new_role}})

    return {
        "success": True,
        "message": f"Utilizador {target_email} actualizado com sucesso para o papel de {title}.",
        "user": sanitize_user(db.Users.find_one({"email": target_email}))
    }

# ==============================================================================
# PROGRESSO DO ESTUDANTE E ANALYTICS DA TURMA
# ==============================================================================

def get_student_progress(email: str) -> List[Dict[str, Any]]:
    db = _get_auth_db()
    if db is None:
        return []
    records = list(db.student_progress.find({"email": email}, {"_id": 0}))
    return records

def record_student_activity(email: str, module_id: str, section_completed: Optional[str] = None, quiz_score: Optional[int] = None) -> Dict[str, Any]:
    db = _get_auth_db()
    if db is None:
        return {}

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = db.student_progress.find_one({"email": email, "module_id": module_id})
    
    if not doc:
        doc = {
            "email": email,
            "module_id": module_id,
            "completed_sections": [],
            "quiz_score": 0,
            "total_attempts": 0,
            "first_accessed": now_str,
            "last_accessed": now_str
        }

    sections = doc.get("completed_sections", [])
    if section_completed and section_completed not in sections:
        sections.append(section_completed)

    attempts = doc.get("total_attempts", 0)
    best_score = doc.get("quiz_score", 0)
    if quiz_score is not None:
        attempts += 1
        if quiz_score > best_score:
            best_score = quiz_score

    update_payload = {
        "completed_sections": sections,
        "quiz_score": best_score,
        "total_attempts": attempts,
        "last_accessed": now_str
    }

    db.student_progress.update_one(
        {"email": email, "module_id": module_id},
        {"$set": update_payload, "$setOnInsert": {"first_accessed": now_str}},
        upsert=True
    )

    return update_payload

def get_academic_analytics_summary() -> Dict[str, Any]:
    db = _get_auth_db()
    if db is None:
        return {}

    total_students = db.Users.count_documents({"role": "student"})
    total_teachers = db.Users.count_documents({"role": {"$in": ["teacher_regent", "teacher_assistant"]}})
    pending_teachers = db.Users.count_documents({"status": "pending_approval"})
    total_threads = db.threads.count_documents({})
    total_replies = db.replies.count_documents({})
    validated_threads = db.threads.count_documents({"is_validated": 1})
    
    # Progresso dos estudantes
    progress_count = db.student_progress.count_documents({})
    quiz_avg = 0
    if progress_count > 0:
        pipeline = [{"$group": {"_id": None, "avg_score": {"$avg": "$quiz_score"}}}]
        res = list(db.student_progress.aggregate(pipeline))
        if res:
            quiz_avg = round(res[0].get("avg_score", 0), 1)

    return {
        "total_students": total_students,
        "total_teachers": total_teachers,
        "pending_teachers": pending_teachers,
        "total_threads": total_threads,
        "total_replies": total_replies,
        "validated_threads": validated_threads,
        "average_quiz_score": quiz_avg,
        "progress_records_count": progress_count
    }

if __name__ == "__main__":
    print("A testar módulo auth_service.py...")
    init_users_and_roles()
    print("Utilizadores inicializados com sucesso!")
