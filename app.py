import os
import sys
import re
import json
import html
import datetime
import unicodedata
import urllib.request
import urllib.error
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
import forum_service
import db_mongo
import auth_service

ENV_PATH = Path(__file__).resolve().parent / ".env"
def load_env():
    env_vars = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()
    return env_vars

env = load_env()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL") or env.get("DEFAULT_MODEL", "llama3.2:3b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST") or env.get("OLLAMA_HOST", "http://localhost:11434")
PORT = int(os.environ.get("PORT") or env.get("PORT", "8000"))

SYSTEM_PROMPT = """Actue como um Assistente Académico Virtual especializado em Investigação Operacional para os estudantes dos cursos de Engenharia da Faculdade de Engenharia da Universidade Eduardo Mondlane (FE-UEM).

Directrizes estritas de apresentação, escopo e conteúdo:
1. Delimitação estrita de escopo (Não alucine): O modelo foi concebido exclusivamente para responder a questões no âmbito de Investigação Operacional, Modelação Matemática e Optimização em Engenharia (Programação Linear, Simplex, Duas Fases, Grande M, Teoria da Dualidade, Análise de Sensibilidade, Problemas de Transporte e Afectação, Teoria de Grafos e Redes, Programação Inteira e Dinâmica).
Sempre que uma pergunta estiver fora do seu âmbito de especialização (por exemplo, culinária, desporto, política, cultura geral, entretenimento, conselhos pessoais ou quaisquer outras matérias alheias à especialização), NÃO desenvolva respostas sobre assuntos não relacionados nem tente especular. Apresente EXCLUSIVAMENTE a seguinte mensagem padronizada, sem explicações adicionais:
<article>
  <header>
    <h3>Questão Fora de Âmbito</h3>
  </header>
  <section>
    <p>Esta questão encontra-se fora do âmbito científico e académico para o qual este agente foi concebido. Por favor, formule uma pergunta relacionada com a sua área de especialização.</p>
  </section>
</article>

2. Sem asteriscos e com HTML limpo: Não utilize asteriscos (ex: **, *, ***). Toda a formatação deve ser feita exclusivamente através de tags HTML semânticas (use <strong> para negrito, <em> para ênfase, e <ul><li>...</li></ul> ou <ol><li>...</li></ol> para listas).
3. Pergunta em destaque no topo: Inicie SEMPRE a resposta reproduzindo a pergunta colocada pelo estudante num bloco de destaque no topo (<div class="question-header-card" style="background-color:#f4f4f5; border:1px solid #e4e4e7; border-left:3px solid #18181b; padding:10px 14px; margin-bottom:16px; border-radius:4px; font-size:0.92em; color:#18181b;"><strong>Questão Submetida:</strong> [pergunta do estudante]</div>), e logo abaixo apresente a resposta directa.
4. Linguagem informal ou imprecisa: Responda normalmente e com rigor técnico às questões pertinentes de Investigação Operacional, mesmo quando formuladas pelo estudante em linguagem informal ou com terminologia imprecisa.
5. Foco cirúrgico e sem elementos desnecessários: Vá estritamente directo ao ponto da pergunta. Elimine introduções longas, frases de cortesia redundantes ou conclusões genéricas.
6. Citação numérica do tipo BibTeX: Em respostas teóricas e práticas da especialidade, fundamente as explicações com citações numéricas no formato BibTeX entre parênteses rectos (ex.: [1], [2]).
7. Formulação matemática e LaTeX: Use equações em LaTeX compatíveis com MathJax (\\( ... \\) para equações inline e \\[ ... \\] para equações em bloco), com notação matricial e passos dedutivos claros quando solicitado.
8. Secção final de referências numéricas: Finalize respostas técnicas com a lista de referências bibliográficas correspondente às citações feitas ([1], [2]...).
"""

def query_ollama(model_name, messages):
    if os.environ.get("VERCEL") and ("localhost" in OLLAMA_HOST or "127.0.0.1" in OLLAMA_HOST):
        raise ConnectionError("Ollama local indisponível em ambiente Serverless (Vercel).")
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.5,
            "repeat_penalty": 1.25,
            "top_p": 0.9,
            "num_predict": 450
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("message", {}).get("content", "")

def is_degenerate(text):
    if not text:
        return True
    lower = text.lower()
    if "não posso responder" in lower or "nao posso responder" in lower or "atividades ilegais" in lower or "anti-sociais" in lower:
        return True
    words = text.split()
    if len(words) > 10:
        for i in range(len(words) - 5):
            window = [w.lower() for w in words[i:i+6]]
            if len(set(window)) <= 2:
                return True
    return False

def log_model_failure(model_name, user_query, reason, exc=None):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[CONSOLE LOG - FALHA NO PROCESSAMENTO DO MODELO] [{ts}]", flush=True)
    print(f"  -> Modelo Solicitado : {model_name}", flush=True)
    print(f"  -> Motivo da Falha   : {reason}", flush=True)
    if exc:
        print(f"  -> Detalhes do Erro  : {repr(exc)}", flush=True)
    print(f"  -> Pergunta          : {user_query[:100]}...", flush=True)
    print(f"  -> Acção de Recurso  : Encaminhado para o Motor Académico FE-UEM\n", flush=True)

def get_installed_ollama_models():
    if os.environ.get("VERCEL") and ("localhost" in OLLAMA_HOST or "127.0.0.1" in OLLAMA_HOST):
        return []
    try:
        url = f"{OLLAMA_HOST}/api/tags"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

def clean_and_format_html(text):
    """
    Remove asteriscos e converte padrões markdown em HTML limpo e semântico,
    preservando equações matemáticas LaTeX / MathJax.
    """
    if not text:
        return ""
    
    # 1. Proteger blocos matemáticos do MathJax para preservar notações (ex: x^* ou índices)
    math_blocks = []
    def save_math(match):
        idx = len(math_blocks)
        math_blocks.append(match.group(0))
        return f"___MATH_BLOCK_{idx}___"
    
    # Proteger \[ ... \], \( ... \), $$ ... $$
    text = re.sub(r'\\\[[\s\S]*?\\\]', save_math, text)
    text = re.sub(r'\\\(.*?\\\)', save_math, text)
    text = re.sub(r'\$\$[\s\S]*?\$\$', save_math, text)
    
    # 2. Converter Markdown headers para HTML semântico
    text = re.sub(r'(?m)^###\s+(.*?)$', r'<h4>\1</h4>', text)
    text = re.sub(r'(?m)^##\s+(.*?)$', r'<h3>\1</h3>', text)
    text = re.sub(r'(?m)^#\s+(.*?)$', r'<h3>\1</h3>', text)
    
    # 3. Converter negrito markdown com asteriscos: **texto** -> <strong>texto</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    
    # 4. Converter itálico markdown com asteriscos: *texto* -> <em>texto</em>
    text = re.sub(r'\*([^\*\n]+?)\*', r'<em>\1</em>', text)
    
    # 5. Converter marcadores de lista (* item ou - item) em listas HTML
    lines = text.split('\n')
    new_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        bullet_match = re.match(r'^[\*\-]\s+(.+)$', stripped)
        if bullet_match:
            if not in_list:
                new_lines.append('<ul style="margin: 10px 0; padding-left: 20px;">')
                in_list = True
            new_lines.append(f'  <li>{bullet_match.group(1)}</li>')
        else:
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append('</ul>')
    text = '\n'.join(new_lines)
    
    # 6. Remover quaisquer asteriscos residuais soltos fora de equações
    text = text.replace('***', '')
    text = text.replace('**', '')
    text = text.replace('*', '')
    
    # 7. Restaurar blocos matemáticos intactos
    for idx, mb in enumerate(math_blocks):
        text = text.replace(f"___MATH_BLOCK_{idx}___", mb)
        
    return text

def format_response_with_question_header(reply_html, user_query):
    """
    Garante que a resposta tem sempre no topo a pergunta do estudante em destaque,
    seguida imediatamente pela resposta focada, sem asteriscos e em HTML limpo.
    """
    cleaned_reply = clean_and_format_html(reply_html)
    escaped_query = html.escape(user_query.strip())
    header_html = (
        f'<div class="question-header-card" style="background-color:#f4f4f5; border:1px solid #e4e4e7; '
        f'border-left:3px solid #18181b; padding:10px 14px; margin-bottom:16px; border-radius:4px; '
        f'font-size:0.92em; color:#18181b;">'
        f'<strong>Questão Submetida:</strong> {escaped_query}'
        f'</div>\n'
    )
    prefix_lower = cleaned_reply[:350].lower()
    if "questão submetida" in prefix_lower or "pergunta submetida" in prefix_lower:
        return cleaned_reply
    return header_html + cleaned_reply

def normalize_text(text):
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def is_in_domain(query):
    """
    Verifica previamente se a questão se enquadra no âmbito científico, académico e técnico
    de Investigação Operacional e Modelação Matemática em Engenharia.
    Aceita termos técnicos e formulações informais sobre optimização.
    """
    norm = normalize_text(query)
    
    # 1. Termos específicos e inequívocos de Investigação Operacional
    specific_terms = [
        "investigacao operacional", "pesquisa operacional", "operational research",
        "programacao linear", "programacao inteira", "programacao dinamica",
        "programacao nao linear", "programacao quadratica", "linear programming",
        "optimizacao", "otimizacao", "optimizador", "otimizador", "optimizar", "otimizar",
        
        # Algoritmos e Métodos
        "simplex", "tableau", "tableaux", "pivo", "pivoteamento", "dantzig",
        "duas fases", "grande m", "big m", "variavel artificial", "variaveis artificiais",
        "branch and bound", "branch & bound", "plano de corte", "planos de corte", "gomory",
        "relaxamento linear", "relaxamento continuo",
        
        # Dualidade e Pós-Otimalidade
        "dualidade", "pos-otima", "pos-optima", "pos otima", "pos optima",
        "preco-sombra", "preco sombra", "precos-sombra", "precos sombra",
        "custo reduzido", "custos reduzidos",
        "folgas complementares", "kuhn-tucker", "kkt",
        
        # Transportes e Afectação
        "transporte", "afectacao", "atribuicao",
        "vogel", "vam", "metodo modi", "canto noroeste", "stepping stone",
        
        # Grafos e Redes
        "teoria dos grafos", "redes de transporte", "fluxo em rede", "fluxos em rede",
        "caminho mais curto", "caminho mais rapido", "shortest path", "dijkstra", "bellman-ford", "floyd",
        "fluxo maximo", "max flow", "ford-fulkerson", "corte minimo", "capacidade residual",
        "arvore geradora", "spanning tree", "kruskal", "prim",
        "cpm", "pert", "caminho critico", "folga total", "folga livre", "diagrama de rede",
        
        # Modelação Matemática em IO
        "variavel de decisao", "variaveis de decisao", "variavel decisoria",
        "funcao objectivo", "funcao objetivo", "f.o.",
        "solucao basica viavel", "solucao basica", "solucao viavel", "solucao optima", "solucao otima",
        "espaco de solucoes", "regiao de viabilidade", "regiao viavel",
        "matriz tecnologica", "coeficiente tecnico", "coeficientes tecnicos",
        
        # Tópicos complementares de IO
        "teoria das filas", "fila de espera", "filas de espera", "taxa de chegada", "taxa de servico",
        "teoria dos jogos", "equilibrio de nash", "ponto de sela",
        "gestao de estoques", "gestao de inventario", "lote economico", "eoq",
        "caixeiro viajante", "tsp", "problema da mochila", "knapsack"
    ]
    
    if any(t in norm for t in specific_terms):
        return True
        
    # 2. Termos compostos e formulações informais de optimização e engenharia
    informal_patterns = [
        "melhor rota", "rota mais rapida", "rota mais curta", "menor percurso",
        "maximizar lucro", "maximizar os lucros", "lucro maximo",
        "minimizar custo", "minimizar os custos", "custo minimo",
        "alocar recursos", "alocacao de recursos", "distribuir tarefas", "alocar tarefas",
        "gargalo de producao", "capacidade produtiva", "capacidade de producao",
        "plano de producao", "linha de producao", "linha de montagem",
        "sujeito a", "restricao de capacidade", "restricoes de capacidade",
        "sistema de inequacoes", "ponto extremo", "pontos extremos"
    ]
    
    if any(p in norm for p in informal_patterns):
        return True
        
    # 3. Combinação de verbos/metas de optimização com restrições
    has_opt_verb = any(v in norm for v in ["maximizar", "minimizar", "optimizar", "otimizar", "lucro", "custo", "tempo", "distancia"])
    has_constraint = any(c in norm for c in ["restricao", "restricoes", "limite", "capacidade", "recurso", "recursos", "origem", "destino"])
    if has_opt_verb and has_constraint:
        return True
        
    return False

def generate_out_of_domain_response(user_query):
    """
    Retorna exclusivamente a mensagem padronizada para questões fora do âmbito científico,
    sem explicações adicionais, cumprindo estritamente as directrizes institucionais.
    """
    content = (
        '<article>\n'
        '  <header>\n'
        '    <h3>Questão Fora de Âmbito</h3>\n'
        '  </header>\n'
        '  <section>\n'
        '    <p>Esta questão encontra-se fora do âmbito científico e académico para o qual este agente foi concebido. Por favor, formule uma pergunta relacionada com a sua área de especialização.</p>\n'
        '  </section>\n'
        '</article>'
    )
    return format_response_with_question_header(content, user_query)

def generate_academic_fallback_response(user_query, model_tried=""):
    query = user_query.lower()
    
    # Saudações simples
    greetings = ["olá", "ola", "oi", "bom dia", "boa tarde", "boa noite", "saudações", "saudacoes", "alo", "alô"]
    words = [w.strip("!.,? ") for w in query.split()]
    if any(w in greetings for w in words) and len(words) <= 4:
        content = """
        <article>
          <header>
            <h3>Saudações Académicas &bull; Assistente de Investigação Operacional</h3>
            <p>Olá! Sou o Assistente Académico Virtual de <strong>Investigação Operacional</strong> da Faculdade de Engenharia da Universidade Eduardo Mondlane (FE-UEM) [1].</p>
          </header>
          <section>
            <h4>Como posso ajudar nos teus estudos de Engenharia?</h4>
            <p>Podes colocar questões teóricas, submeter exercícios práticos ou pedir demonstrações matemáticas sobre:</p>
            <ul>
              <li><strong>Programação Linear:</strong> Formulação canónica, variáveis de decisão e espaço de soluções [1].</li>
              <li><strong>Método Simplex:</strong> Construção de tableaux, variáveis de folga/excesso e critérios de optimilidade [1], [2].</li>
              <li><strong>Duas Fases e Grande M:</strong> Resolução de problemas com restrições \\(\\ge\\) ou \\(=\\) [2], [3].</li>
              <li><strong>Dualidade e Sensibilidade:</strong> Interpretação económica de preços-sombra e Teorema das Folgas Complementares [1], [2].</li>
              <li><strong>Problemas de Transporte e Redes:</strong> Algoritmos de Vogel, MODI, Dijkstra e fluxo máximo [1], [3].</li>
            </ul>
            <p><em>Podes escrever a tua dúvida específica ou clicar num dos tópicos no menu lateral para começar.</em></p>
          </section>
          <footer>
            <h4>Referências Bibliográficas</h4>
            <ol>
              <li>[1] Hillier, F. S., &amp; Lieberman, G. J. (2021). <em>Introduction to Operations Research</em> (11.ª ed.). McGraw-Hill Education.</li>
              <li>[2] Taha, H. A. (2017). <em>Operations Research: An Introduction</em> (10.ª ed.). Pearson.</li>
              <li>[3] Bazaraa, M. S., Jarvis, J. J., &amp; Sherali, H. D. (2010). <em>Linear Programming and Network Flows</em> (4.ª ed.). John Wiley &amp; Sons.</li>
            </ol>
          </footer>
        </article>
        """
        return format_response_with_question_header(content, user_query)

    if "duas fases" in query or "grande m" in query or "artificial" in query:
        content = """
        <article>
          <header>
            <h3>Tratamento de Variáveis Artificiais: Duas Fases vs. Grande M</h3>
            <p>Quando a origem não constitui uma solução básica viável inicial (restrições do tipo \\(\\ge\\) ou \\(=\\)), introduzem-se variáveis artificiais \\(R_i \\ge 0\\) [1].</p>
          </header>

          <section>
            <h4>1. Comparação dos Métodos</h4>
            <table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse:collapse;">
              <thead style="background-color:#18181b; color:#ffffff;">
                <tr><th>Critério</th><th>Método das Duas Fases</th><th>Método do Grande M</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Objectivo Inicial</strong></td>
                  <td>Fase I: Minimizar a soma das artificiais \\(\\min W = \\sum R_i\\) [1].</td>
                  <td>Penalizar as artificiais na F.O. com parâmetro \\(M \\gg 0\\) [2].</td>
                </tr>
                <tr>
                  <td><strong>Estabilidade Numérica</strong></td>
                  <td>Alta (elimina erros de arredondamento causados por \\(M\\)).</td>
                  <td>Baixa (sujeito a erros de precisão computacional) [1].</td>
                </tr>
                <tr>
                  <td><strong>Critério de Inviabilidade</strong></td>
                  <td>Se \\(W^* > 0\\), o problema primal é inviável [1].</td>
                  <td>Se alguma artificial permanecer na base com valor positivo, é inviável [2].</td>
                </tr>
              </tbody>
            </table>
          </section>

          <footer>
            <h4>Referências Bibliográficas</h4>
            <ol>
              <li>[1] Bazaraa, M. S., Jarvis, J. J., &amp; Sherali, H. D. (2010). <em>Linear Programming and Network Flows</em> (4.ª ed.). John Wiley &amp; Sons.</li>
              <li>[2] Winston, W. L. (2004). <em>Operations Research: Applications and Algorithms</em> (4.ª ed.). Brooks/Cole.</li>
            </ol>
          </footer>
        </article>
        """
    elif "dual" in query or "sensibilidade" in query or "sombra" in query:
        content = """
        <article>
          <header>
            <h3>Teoria da Dualidade e Teorema das Folgas Complementares</h3>
            <p>A cada problema primal de Programação Linear corresponde um problema dual associado que traduz a valoração marginal dos recursos escassos [1].</p>
          </header>

          <section>
            <h4>1. Relações Canónicas Primal-Dual</h4>
            \\[
            \\begin{aligned}
            \\text{Primal: } & \\max \\ \\mathbf{c}^T \\mathbf{x} \\quad \\text{sujeito a:} \\quad \\mathbf{A}\\mathbf{x} \\le \\mathbf{b}, \\quad \\mathbf{x} \\ge \\mathbf{0} \\\\
            \\text{Dual: } & \\min \\ \\mathbf{b}^T \\mathbf{y} \\quad \\text{sujeito a:} \\quad \\mathbf{A}^T\\mathbf{y} \\ge \\mathbf{c}, \\quad \\mathbf{y} \\ge \\mathbf{0}
            \\end{aligned}
            \\]
          </section>

          <section>
            <h4>2. Teorema das Folgas Complementares</h4>
            <p>Seja \\(\\mathbf{x}^*\\) viável primal e \\(\\mathbf{y}^*\\) viável dual. Elas são óptimas se e só se [1], [2]:</p>
            \\[
            y_i^* \\cdot (b_i - \\mathbf{a}_i^T \\mathbf{x}^*) = 0, \\quad \\forall i
            \\]
            \\[
            x_j^* \\cdot (\\mathbf{A}_j^T \\mathbf{y}^* - c_j) = 0, \\quad \\forall j
            \\]
            <ul>
              <li>Se uma restrição do recurso \\(i\\) tiver folga positiva (\\(s_i^* > 0\\)), o seu preço-sombra é nulo (\\(y_i^* = 0\\)) [1].</li>
              <li>Se um recurso tiver preço-sombra positivo (\\(y_i^* > 0\\)), o recurso esgota-se integralmente (\\(s_i^* = 0\\)) [2].</li>
            </ul>
          </section>

          <footer>
            <h4>Referências Bibliográficas</h4>
            <ol>
              <li>[1] Hillier, F. S., &amp; Lieberman, G. J. (2021). <em>Introduction to Operations Research</em> (11.ª ed.). McGraw-Hill Education.</li>
              <li>[2] Taha, H. A. (2017). <em>Operations Research: An Introduction</em> (10.ª ed.). Pearson.</li>
            </ol>
          </footer>
        </article>
        """
    elif "simplex" in query or "tableau" in query:
        content = """
        <article>
          <header>
            <h3>Resolução pelo Método Simplex Primal (Dantzig)</h3>
            <p>O Método Simplex determina a solução óptima de um problema de Programação Linear movendo-se iterativamente ao longo dos pontos extremos (soluções básicas viáveis) do poliedro de restrições [1].</p>
          </header>
          
          <section>
            <h4>1. Formulação do Problema</h4>
            \\[
            \\begin{aligned}
            \\max Z &= 3x_1 + 5x_2 \\\\
            \\text{sujeito a:} \\quad x_1 &\\le 4 \\\\
            2x_2 &\\le 12 \\\\
            3x_1 + 2x_2 &\\le 18 \\\\
            x_1, x_2 &\\ge 0
            \\end{aligned}
            \\]
          </section>

          <section>
            <h4>2. Forma Padrão</h4>
            <p>Com as variáveis de folga \\(s_1, s_2, s_3 \\ge 0\\) [2]:</p>
            \\[
            \\begin{alignedat}{6}
            Z & {}-{} 3x_1 & {}-{} 5x_2 & {}+{} 0s_1 & {}+{} 0s_2 & {}+{} 0s_3 = 0 \\\\
              & \\phantom{{}-{}} x_1 & & {}+{} s_1 & & = 4 \\\\
              & & \\phantom{{}+{}} 2x_2 & & {}+{} s_2 & = 12 \\\\
              & \\phantom{{}-{}} 3x_1 & {}+{} 2x_2 & & & {}+{} s_3 = 18
            \\end{alignedat}
            \\]
          </section>

          <section>
            <h4>3. Tableau Óptimo</h4>
            <div style="overflow-x: auto;">
              <table border="1" cellpadding="6" cellspacing="0" style="width:100%; text-align:center; border-collapse:collapse;">
                <thead style="background-color:#18181b; color:#ffffff;">
                  <tr><th>Base</th><th>\\(Z\\)</th><th>\\(x_1\\)</th><th>\\(x_2\\)</th><th>\\(s_1\\)</th><th>\\(s_2\\)</th><th>\\(s_3\\)</th><th>RHS</th></tr>
                </thead>
                <tbody>
                  <tr style="background-color:#f4f4f5; font-weight:600;"><td>\\(Z\\)</td><td>1</td><td>0</td><td>0</td><td>0</td><td>1.5</td><td>1.0</td><td>36</td></tr>
                  <tr><td>\\(s_1\\)</td><td>0</td><td>0</td><td>0</td><td>1</td><td>0.33</td><td>-0.33</td><td>2</td></tr>
                  <tr><td>\\(x_2\\)</td><td>0</td><td>0</td><td>1</td><td>0</td><td>0.5</td><td>0</td><td>6</td></tr>
                  <tr><td>\\(x_1\\)</td><td>0</td><td>1</td><td>0</td><td>0</td><td>-0.33</td><td>0.33</td><td>2</td></tr>
                </tbody>
              </table>
            </div>
            <p style="margin-top:10px;">
              <strong>Solução Óptima:</strong> \\(x_1^* = 2\\), \\(x_2^* = 6\\), \\(s_1^* = 2\\), \\(Z^* = 36\\times 10^3\\text{ MZN}\\). Preços-sombra: \\(y_2^* = 1.5\\), \\(y_3^* = 1.0\\), \\(y_1^* = 0\\) [1], [2].
            </p>
          </section>

          <footer>
            <h4>Referências Bibliográficas</h4>
            <ol>
              <li>[1] Hillier, F. S., &amp; Lieberman, G. J. (2021). <em>Introduction to Operations Research</em> (11.ª ed.). McGraw-Hill Education.</li>
              <li>[2] Taha, H. A. (2017). <em>Operations Research: An Introduction</em> (10.ª ed.). Pearson.</li>
            </ol>
          </footer>
        </article>
        """
    elif "dual" in query or "sensibilidade" in query or "sombra" in query:
        content = """
        <article>
          <header>
            <h3>Teoria da Dualidade e Teorema das Folgas Complementares</h3>
            <p>A cada problema primal de Programação Linear corresponde um problema dual associado que traduz a valoração marginal dos recursos escassos [1].</p>
          </header>

          <section>
            <h4>1. Relações Canónicas Primal-Dual</h4>
            \\[
            \\begin{aligned}
            \\text{Primal: } & \\max \\ \\mathbf{c}^T \\mathbf{x} \\quad \\text{sujeito a:} \\quad \\mathbf{A}\\mathbf{x} \\le \\mathbf{b}, \\quad \\mathbf{x} \\ge \\mathbf{0} \\\\
            \\text{Dual: } & \\min \\ \\mathbf{b}^T \\mathbf{y} \\quad \\text{sujeito a:} \\quad \\mathbf{A}^T\\mathbf{y} \\ge \\mathbf{c}, \\quad \\mathbf{y} \\ge \\mathbf{0}
            \\end{aligned}
            \\]
          </section>

          <section>
            <h4>2. Teorema das Folgas Complementares</h4>
            <p>Seja \\(\\mathbf{x}^*\\) viável primal e \\(\\mathbf{y}^*\\) viável dual. Elas são óptimas se e só se [1], [2]:</p>
            \\[
            y_i^* \\cdot (b_i - \\mathbf{a}_i^T \\mathbf{x}^*) = 0, \\quad \\forall i
            \\]
            \\[
            x_j^* \\cdot (\\mathbf{A}_j^T \\mathbf{y}^* - c_j) = 0, \\quad \\forall j
            \\]
            <ul>
              <li>Se uma restrição do recurso \\(i\\) tiver folga positiva (\\(s_i^* > 0\\)), o seu preço-sombra é nulo (\\(y_i^* = 0\\)) [1].</li>
              <li>Se um recurso tiver preço-sombra positivo (\\(y_i^* > 0\\)), o recurso esgota-se integralmente (\\(s_i^* = 0\\)) [2].</li>
            </ul>
          </section>

          <footer>
            <h4>Referências Bibliográficas</h4>
            <ol>
              <li>[1] Hillier, F. S., &amp; Lieberman, G. J. (2021). <em>Introduction to Operations Research</em> (11.ª ed.). McGraw-Hill Education.</li>
              <li>[2] Taha, H. A. (2017). <em>Operations Research: An Introduction</em> (10.ª ed.). Pearson.</li>
            </ol>
          </footer>
        </article>
        """
    elif is_in_domain(query):
        content = """
        <article>
          <header>
            <h3>Análise Académica e Metodologia de Resolução</h3>
          </header>

          <section>
            <h4>1. Modelação Conceptual de Sistemas de Engenharia</h4>
            <p>
              Em Investigação Operacional aplicada aos cursos de Engenharia da <strong>FE-UEM</strong>, o processo de tomada de decisão quantitativa obedece à estruturação em cinco fases axiomáticas [1]:
            </p>
            <ol>
              <li><strong>Definição do Sistema e Fronteiras:</strong> Identificação das variáveis de decisão \\(x_j\\), grandezas mensuráveis com unidades no Sistema Internacional (SI) ou unidades monetárias (Meticais).</li>
              <li><strong>Construção da Função de Eficiência (Função Objectivo):</strong> Formalização de \\(\\max Z\\) (lucro, rendimento, caudal) ou \\(\\min Z\\) (custos, perdas energéticas, atrasos) [1], [2].</li>
              <li><strong>Mapeamento das Inequações de Restrição:</strong> Limitações de capacidade produtiva, conservação de massa/fluxo, requisitos normativos e limites contratuais [2].</li>
              <li><strong>Determinação da Solução Óptima:</strong> Execução do algoritmo apropriado (Simplex, Branch &amp; Bound, Dijkstra, Ford-Fulkerson) [1], [3].</li>
              <li><strong>Análise Pós-Óptima e Sensibilidade:</strong> Validação da robustez da solução face a flutuações e incertezas no ambiente operacional moçambicano [1], [2].</li>
            </ol>
          </section>

          <section>
            <h4>2. Formulação Padrão em Notação Matricial</h4>
            \\[
            \\begin{aligned}
            \\text{Opt } & Z = \\mathbf{c}^T \\mathbf{x} \\\\
            \\text{sujeito a:} \\quad & \\mathbf{A}\\mathbf{x} \\le \\mathbf{b} \\\\
            & \\mathbf{x} \\ge \\mathbf{0}
            \\end{aligned}
            \\]
            <p>
              Onde \\(\\mathbf{A} \\in \\mathbb{R}^{m \\times n}\\) representa a matriz tecnológica de coeficientes técnicos, \\(\\mathbf{b} \\in \\mathbb{R}^m\\) o vector de disponibilidades de recursos e \\(\\mathbf{c} \\in \\mathbb{R}^n\\) o vector de margens marginais [1], [3].
            </p>
          </section>

          <footer>
            <h4>Referências Bibliográficas</h4>
            <ol>
              <li>[1] Taha, H. A. (2017). <em>Operations Research: An Introduction</em> (10.ª ed.). Pearson.</li>
              <li>[2] Hillier, F. S., &amp; Lieberman, G. J. (2021). <em>Introduction to Operations Research</em> (11.ª ed.). McGraw-Hill Education.</li>
              <li>[3] Bazaraa, M. S., Jarvis, J. J., &amp; Sherali, H. D. (2010). <em>Linear Programming and Network Flows</em> (4.ª ed.). John Wiley &amp; Sons.</li>
            </ol>
          </footer>
        </article>
        """
    else:
        return generate_out_of_domain_response(user_query)

    notice = f"""
    <div style="background-color: #fafafa; border: 1px solid #e4e4e7; border-left: 3px solid #71717a; padding: 8px 12px; margin-bottom: 16px; border-radius: 4px; font-size: 0.82em; color: #52525b;">
      <strong>FE-UEM &bull; Investigação Operacional:</strong> Resposta estruturada com rigor científico, formulação matemática e citações numéricas BibTeX [1], [2].
    </div>
    """
    return format_response_with_question_header(notice + content, user_query)

STATIC_DIR = Path(__file__).resolve().parent / "static"
_server_initialized = False

def ensure_initialized():
    global _server_initialized
    if not _server_initialized:
        try:
            forum_service.init_db()
            auth_service.init_users_and_roles()
        except Exception as e:
            print(f"[INIT WARNING] {e}")
        _server_initialized = True

class handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def get_auth_token(self):
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            if "auth_token=" in part:
                return part.split("auth_token=")[1].strip()
        return None

    def get_current_user(self):
        token = self.get_auth_token()
        return auth_service.get_user_from_token(token)

    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        ensure_initialized()
        # 1. Autenticação e Perfil
        if self.path == "/api/auth/me":
            user = self.get_current_user()
            if not user:
                self.send_json_error(401, "Sessão não autenticada ou expirada.")
                return
            self.send_json({"user": user})
            return

        # 2. Utilizadores e Gestão Docente (Apenas Regente e Assistente)
        if self.path == "/api/admin/users":
            user = self.get_current_user()
            if not user or user.get("role") not in ["teacher_regent", "teacher_assistant"]:
                self.send_json_error(403, "Acesso restrito ao corpo docente.")
                return
            users = auth_service.list_academic_users(user.get("role"))
            self.send_json({"users": users})
            return

        # 3. Estatísticas e Desempenho da Turma
        if self.path == "/api/admin/analytics":
            user = self.get_current_user()
            if not user or user.get("role") not in ["teacher_regent", "teacher_assistant"]:
                self.send_json_error(403, "Acesso restrito ao corpo docente.")
                return
            analytics = auth_service.get_academic_analytics_summary()
            self.send_json({"analytics": analytics})
            return

        # 4. Progresso do Estudante Autenticado
        if self.path == "/api/student/progress":
            user = self.get_current_user()
            if not user:
                self.send_json_error(401, "Não autenticado.")
                return
            progress = auth_service.get_student_progress(user["email"])
            self.send_json({"progress": progress})
            return
        if self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            ollama_models = get_installed_ollama_models()
            status = {
                "status": "online",
                "institution": "Faculdade de Engenharia - UEM",
                "discipline": "Investigação Operacional",
                "model": DEFAULT_MODEL,
                "default_model": DEFAULT_MODEL,
                "ollama_available": len(ollama_models) > 0,
                "ollama_models": ollama_models,
                "has_api_key": bool(OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"))
            }
            self.wfile.write(json.dumps(status).encode("utf-8"))
            return
        
        if self.path == "/api/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            ollama_models = get_installed_ollama_models()
            models = [
                {"id": "llama3.2:3b", "name": "Llama 3.2 (Meta Open Source - 3B Recomendado)", "type": "open-source"},
                {"id": "llama3.2:1b", "name": "Llama 3.2 (Meta Open Source - 1B Rápido)", "type": "open-source"},
                {"id": "academic-engine", "name": "Motor Académico Integrado FE-UEM", "type": "built-in"},
                {"id": "deepseek-r1:1.5b", "name": "DeepSeek-R1 (Open Source Reasoning)", "type": "open-source"},
                {"id": "qwen2.5:3b", "name": "Qwen 2.5 (Alibaba Open Source - 3B)", "type": "open-source"},
                {"id": "gpt-4o-mini", "name": "OpenAI GPT-4o-mini", "type": "cloud"}
            ]
            self.wfile.write(json.dumps({"models": models, "installed_ollama": ollama_models}).encode("utf-8"))
            return

        if self.path == "/api/db/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            status = db_mongo.get_db_status()
            self.wfile.write(json.dumps(status).encode("utf-8"))
            return

        if self.path.startswith("/api/modules"):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            topic = qs.get("topic", [None])[0] or qs.get("id", [None])[0]
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            if topic:
                mod = db_mongo.get_module_by_key_or_id(topic)
                self.wfile.write(json.dumps({"module": mod}).encode("utf-8"))
            else:
                modules = db_mongo.get_all_modules()
                self.wfile.write(json.dumps({"modules": modules, "count": len(modules)}).encode("utf-8"))
            return

        if self.path.startswith("/api/forum/threads"):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            module = qs.get("module", [None])[0]
            search = qs.get("search", [None])[0]
            filter_type = qs.get("filter", [None])[0]
            threads = forum_service.list_threads(module, search, filter_type)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"threads": threads}).encode("utf-8"))
            return

        if self.path.startswith("/api/forum/thread"):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            thread_id = qs.get("id", [None])[0]
            if not thread_id:
                self.send_json_error(400, "ID da discussão em falta.")
                return
            thread = forum_service.get_thread_details(int(thread_id))
            if not thread:
                self.send_json_error(404, "Discussão não encontrada.")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"thread": thread}).encode("utf-8"))
            return

        if self.path == "/" or self.path == "":
            self.path = "/index.html"
            
        return super().do_GET()

    def do_POST(self):
        ensure_initialized()
        # 1. Registo de Novo Utilizador
        if self.path == "/api/auth/register":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                res = auth_service.register_user(
                    name=data.get("name", ""),
                    email=data.get("email", ""),
                    password=data.get("password", ""),
                    requested_role=data.get("requested_role", "student"),
                    student_number=data.get("student_number"),
                    course_department=data.get("course_department")
                )
                self.send_json(res, code=201)
                return
            except ValueError as ve:
                self.send_json_error(400, str(ve))
                return
            except Exception as e:
                self.send_json_error(500, f"Erro interno ao registar utilizador: {str(e)}")
                return

        # 2. Início de Sessão (Login)
        if self.path == "/api/auth/login":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                res = auth_service.login_user(
                    email=data.get("email", ""),
                    password=data.get("password", "")
                )
                self.send_json(res, code=200)
                return
            except ValueError as ve:
                self.send_json_error(401, str(ve))
                return
            except Exception as e:
                self.send_json_error(500, f"Erro interno ao autenticar: {str(e)}")
                return

        # 3. Encerramento de Sessão (Logout)
        if self.path == "/api/auth/logout":
            token = self.get_auth_token()
            if token:
                auth_service.logout_user(token)
            self.send_json({"success": True, "message": "Sessão terminada com sucesso."})
            return

        # 4. Solicitação de Recuperação de Palavra-Passe
        if self.path == "/api/auth/forgot-password":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                res = auth_service.request_password_reset(data.get("email", ""))
                self.send_json(res, code=200)
                return
            except ValueError as ve:
                self.send_json_error(400, str(ve))
                return
            except Exception as e:
                self.send_json_error(500, f"Erro ao solicitar recuperação: {str(e)}")
                return

        # 5. Conclusão da Recuperação com Nova Palavra-Passe
        if self.path == "/api/auth/reset-password":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                res = auth_service.complete_password_reset(
                    email=data.get("email", ""),
                    reset_code=data.get("reset_code", ""),
                    new_password=data.get("new_password", "")
                )
                self.send_json(res, code=200)
                return
            except ValueError as ve:
                self.send_json_error(400, str(ve))
                return
            except Exception as e:
                self.send_json_error(500, f"Erro ao actualizar palavra-passe: {str(e)}")
                return

        # 6. Gestão e Promoção de Docentes (Exclusivo Docente Regente)
        if self.path == "/api/admin/users/role":
            user = self.get_current_user()
            if not user or user.get("role") != "teacher_regent":
                self.send_json_error(403, "Apenas o Docente Regente pode autorizar e gerir permissões da equipa docente.")
                return
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                res = auth_service.update_user_status_and_role(
                    requester_user=user,
                    target_email=data.get("target_email", ""),
                    new_role=data.get("new_role", "teacher_assistant"),
                    new_status=data.get("new_status", "active"),
                    custom_permissions=data.get("custom_permissions")
                )
                self.send_json(res, code=200)
                return
            except Exception as e:
                self.send_json_error(400, str(e))
                return

        # 7. Registo de Actividade e Progresso do Estudante
        if self.path == "/api/student/progress":
            user = self.get_current_user()
            if not user:
                self.send_json_error(401, "Não autenticado.")
                return
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                res = auth_service.record_student_activity(
                    email=user["email"],
                    module_id=data.get("module_id", ""),
                    section_completed=data.get("section_id"),
                    quiz_score=data.get("quiz_score")
                )
                self.send_json({"success": True, "progress": res})
                return
            except Exception as e:
                self.send_json_error(400, str(e))
                return
        if self.path == "/api/modules":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
            except Exception as e:
                self.send_json_error(400, f"JSON inválido: {str(e)}")
                return
            topic_key = data.get("topic_key") or data.get("title", "Novo Módulo")
            success = db_mongo.save_or_update_module(topic_key, data)
            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))
            return

        if self.path == "/api/forum/threads":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
            except Exception as e:
                self.send_json_error(400, f"JSON inválido: {str(e)}")
                return
            thread = forum_service.create_thread(
                module_id=data.get("module_id", "Geral"),
                title=data.get("title", "").strip(),
                content=data.get("content", "").strip(),
                author_name=data.get("author_name", "Estudante FE-UEM"),
                author_role=data.get("author_role", "student"),
                tags=data.get("tags", [])
            )
            self.send_response(201)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"thread": thread}).encode("utf-8"))
            return

        if self.path == "/api/forum/replies":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
            except Exception as e:
                self.send_json_error(400, f"JSON inválido: {str(e)}")
                return
            thread = forum_service.add_reply(
                thread_id=int(data.get("thread_id")),
                author_name=data.get("author_name", "Estudante FE-UEM"),
                author_role=data.get("author_role", "student"),
                content=data.get("content", "").strip()
            )
            self.send_response(201)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"thread": thread}).encode("utf-8"))
            return

        if self.path == "/api/forum/summon_ai":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
            except Exception as e:
                self.send_json_error(400, f"JSON inválido: {str(e)}")
                return
            thread_id = int(data.get("thread_id"))
            thread = forum_service.generate_ai_tutor_reply(
                thread_id=thread_id,
                query_ollama_fn=query_ollama,
                default_model=DEFAULT_MODEL
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"thread": thread}).encode("utf-8"))
            return

        if self.path == "/api/forum/validate":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
            except Exception as e:
                self.send_json_error(400, f"JSON inválido: {str(e)}")
                return
            thread_id = int(data.get("thread_id"))
            reply_id = data.get("reply_id")
            thread = forum_service.toggle_validation(thread_id, reply_id)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"thread": thread}).encode("utf-8"))
            return

        if self.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode("utf-8"))
            except Exception as e:
                self.send_json_error(400, f"JSON inválido: {str(e)}")
                return

            user_message = data.get("message", "").strip()
            history = data.get("history", [])
            chosen_model = data.get("model", DEFAULT_MODEL)

            if not user_message:
                self.send_json_error(400, "Mensagem vazia.")
                return

            # Tratamento de saudações conversacionais
            greetings = ["olá", "ola", "oi", "bom dia", "boa tarde", "boa noite", "saudações", "saudacoes", "alo", "alô"]
            words = [w.strip("!.,? ") for w in user_message.lower().split()]
            if any(w in greetings for w in words) and len(words) <= 4:
                welcome_reply = generate_academic_fallback_response(user_message, chosen_model)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": welcome_reply, "provider": "academic-engine"}).encode("utf-8"))
                return

            # Verificação prévia de âmbito científico/académico (Guardrail anti-alucinação)
            if not is_in_domain(user_message):
                out_of_domain_reply = generate_out_of_domain_response(user_message)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "reply": out_of_domain_reply,
                    "provider": "academic-engine",
                    "out_of_domain": True
                }).encode("utf-8"))
                return

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for msg in history[-6:]:
                messages.append({
                    "role": "user" if msg.get("sender") == "user" else "assistant",
                    "content": msg.get("text", "")
                })
            messages.append({"role": "user", "content": user_message})

            failure_reason = None

            # 1. Tentar Ollama se o modelo for open-source
            if "llama" in chosen_model or "deepseek" in chosen_model or "qwen" in chosen_model or "mistral" in chosen_model:
                try:
                    ollama_models = get_installed_ollama_models()
                    target_model = chosen_model
                    # Se o modelo solicitado não estiver instalado no Ollama, usar o modelo instalado (ex: llama3.2:1b)
                    if ollama_models and chosen_model not in ollama_models:
                        target_model = ollama_models[0]
                        print(f"[CONSOLE LOG] Modelo '{chosen_model}' nao instalado localmente. A recorrer ao modelo instalado '{target_model}'.")
                    
                    ollama_res = query_ollama(target_model, messages)
                    if ollama_res and not is_degenerate(ollama_res):
                        formatted_reply = format_response_with_question_header(ollama_res, user_message)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "reply": formatted_reply,
                            "provider": f"ollama ({target_model})",
                            "model_failed": False
                        }).encode("utf-8"))
                        return
                    else:
                        failure_reason = "Resposta do modelo Ollama vazia ou degenerada (repetição ou falso-positivo de recusa)."
                        log_model_failure(target_model, user_message, failure_reason)
                except Exception as oe:
                    failure_reason = f"Falha de ligação/execução com Ollama: {str(oe)}"
                    log_model_failure(chosen_model, user_message, failure_reason, oe)

            # 2. Se for cloud (OpenAI) e houver chave
            if "gpt" in chosen_model and OPENAI_API_KEY:
                try:
                    api_payload = {
                        "model": chosen_model,
                        "messages": messages,
                        "temperature": 0.2
                    }
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {OPENAI_API_KEY}"
                    }
                    req = urllib.request.Request(
                        "https://api.openai.com/v1/chat/completions",
                        data=json.dumps(api_payload).encode("utf-8"),
                        headers=headers,
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=60) as response:
                        res_body = response.read().decode("utf-8")
                        res_json = json.loads(res_body)
                        assistant_reply = res_json["choices"][0]["message"]["content"]
                        formatted_reply = format_response_with_question_header(assistant_reply, user_message)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "reply": formatted_reply,
                            "provider": "openai",
                            "model_failed": False
                        }).encode("utf-8"))
                        return
                except Exception as ce:
                    failure_reason = f"Falha na API OpenAI: {str(ce)}"
                    log_model_failure(chosen_model, user_message, failure_reason, ce)

            # 3. Fallback científico e pedagógico da FE-UEM
            academic_reply = generate_academic_fallback_response(user_message, chosen_model)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "reply": academic_reply,
                "provider": "academic-engine",
                "model_failed": bool(failure_reason),
                "failure_reason": failure_reason or "Motor Académico FE-UEM seleccionado directamente"
            }).encode("utf-8"))
            return

        self.send_json_error(404, "Endpoint não encontrado")

    def send_json_error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# Alias de compatibilidade local e Vercel Serverless (@vercel/python)
IOAssistantHandler = handler

def run_server():
    ensure_initialized()
    db_stat = db_mongo.get_db_status()
    server_address = ("", PORT)
    httpd = ThreadedHTTPServer(server_address, IOAssistantHandler)
    print(f"================================================================")
    print(f" Servidor Academico de Investigacao Operacional (FE-UEM)")
    print(f" Acessivel localmente em: http://localhost:{PORT}")
    print(f" Base de Dados: {db_stat.get('engine')} [{db_stat.get('database')}] - {db_stat.get('status')}")
    print(f" Colecções: {', '.join(db_stat.get('collections', []))}")
    print(f" Suporte a Modelos Open-Source (Llama, DeepSeek, Qwen) e FE-UEM")
    print(f"================================================================")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
