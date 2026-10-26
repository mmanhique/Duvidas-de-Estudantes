# Plataforma Académica de Dúvidas de Investigação Operacional — FE-UEM

Assistente Virtual especializado em Investigação Operacional (IO) concebido especificamente para os estudantes dos cursos de Engenharia da **Faculdade de Engenharia da Universidade Eduardo Mondlane (FE-UEM)**.

---

## 🌟 Funcionalidades Principais

- **Rigor Científico e Metodológico:** Resolução passo a passo de exercícios com formulação formal, variáveis de decisão, função objectivo, restrições e interpretação económica.
- **Renderização Matemática LaTeX (MathJax):** Fórmulas, fracções, matrizes e inequações renderizadas com qualidade tipográfica académica.
- **Tabelas de Iteração Simplex:** Apresentação estruturada dos tableaux primal, Duas Fases e Grande M com identificação de pivôs e variáveis básicas.
- **Normas Bibliográficas APA 7.ª edição:** Citações e referências de manuais internacionais de referência (Hillier & Lieberman, Taha, Bazaraa, Winston).
- **Interface Web Académica Integrada:** Interface responsiva e fluida com tópicos rápidos de selecção e histórico de sessão.

---

## 📁 Estrutura do Projecto

```
Duvidas de estudantes/
├── .env                     # Configuração de chave OpenAI, porta e modelo
├── app.py                   # Servidor backend Python com API HTTP e endpoints
├── requirements.txt         # Especificação de dependências
├── iniciar_servidor.bat     # Atalho para inicialização no Windows
├── README.md                # Documentação técnica e pedagógica
└── static/
    ├── index.html           # Interface web em HTML5 semântico
    ├── styles.css           # Estilos visuais institucionais FE-UEM
    └── app.js               # Lógica cliente, MathJax dinâmico e gestão de chat
```

---

## 🚀 Como Executar Localmente

### 1. Acesso Imediato (Servidor Já em Execução)

O servidor encontra-se activo em segundo plano na sua máquina:
👉 **[http://localhost:8000](http://localhost:8000)**

Abra este endereço no seu navegador (Google Chrome, Microsoft Edge, Mozilla Firefox).

### 2. Reiniciar o Servidor Manualmente

Se fechar o terminal ou reiniciar o computador, pode iniciar novamente de duas formas:

- **Via duplo clique:** Execute o ficheiro [`iniciar_servidor.bat`](file:///c:/Users/MilagreManhique/Documents/Projectos%20Antigravity/Duvidas%20de%20estudantes/iniciar_servidor.bat)
- **Via PowerShell:**
  ```powershell
  & "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" app.py
  ```

---

## 🔑 Configuração da Chave OpenAI (.env)

O ficheiro [`.env`](file:///c:/Users/MilagreManhique/Documents/Projectos%20Antigravity/Duvidas%20de%20estudantes/.env) contém as definições do sistema:

```env
OPENAI_API_KEY=sk-proj-...
MODEL_NAME=gpt-4o-mini
PORT=8000
```

> **Nota sobre Facturação da API:**  
> A chave fornecida inicialmente retornou o código `credit_balance_exhausted` (saldo de créditos da conta OpenAI esgotado). O servidor foi dotado de um motor de contingência científica da FE-UEM que garante respostas completas aos tópicos do programa curricular mesmo sem créditos remanescentes. Assim que recarregar créditos no painel da OpenAI, o servidor começará de imediato a efectuar chamadas dinâmicas em tempo real sem necessitar de qualquer alteração no código.
