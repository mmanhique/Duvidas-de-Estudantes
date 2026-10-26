document.addEventListener("DOMContentLoaded", () => {
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const loadingBar = document.getElementById("loading-bar");
  const loadingText = document.getElementById("loading-text");
  const clearBtn = document.getElementById("clear-btn");
  const systemStatus = document.getElementById("system-status");
  const sidebar = document.getElementById("sidebar");
  const sidebarToggleBtn = document.getElementById("sidebar-toggle-btn");
  const sidebarCloseBtn = document.getElementById("sidebar-close-btn");
  const sidebarOverlay = document.getElementById("sidebar-overlay");
  const topicItems = document.querySelectorAll(".topic-item");
  const suggestionPills = document.querySelectorAll(".suggestion-pill");

  const conversationHistory = [];

  // Toggle do Painel Lateral (Acesso Progressivo)
  function toggleSidebar() {
    sidebar.classList.toggle("collapsed");
    if (window.innerWidth <= 840) {
      sidebarOverlay.classList.toggle("active", !sidebar.classList.contains("collapsed"));
    }
  }

  function closeSidebar() {
    sidebar.classList.add("collapsed");
    sidebarOverlay.classList.remove("active");
  }

  if (sidebarToggleBtn) sidebarToggleBtn.addEventListener("click", toggleSidebar);
  if (sidebarCloseBtn) sidebarCloseBtn.addEventListener("click", closeSidebar);
  if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);

  // Por omissão em ecrãs menores, iniciar recolhido
  if (window.innerWidth <= 1024) {
    sidebar.classList.add("collapsed");
  }

  const pedagogicalPhrases = [
    "A estruturar formulação matemática formal...",
    "A construir variáveis de decisão e sistema de inequações...",
    "A verificar viabilidade das condições de Kuhn-Tucker / Simplex...",
    "A calcular tableaux e pivoteamentos de Gauss-Jordan...",
    "A determinar preços-sombra e análise de sensibilidade...",
    "A formatar equações em MathJax e citações BibTeX [1], [2]..."
  ];

  let phraseInterval = null;

  function startPedagogicalLoader() {
    loadingBar.style.display = "flex";
    let idx = 0;
    loadingText.textContent = pedagogicalPhrases[idx];
    phraseInterval = setInterval(() => {
      idx = (idx + 1) % pedagogicalPhrases.length;
      loadingText.textContent = pedagogicalPhrases[idx];
    }, 2800);
  }

  function stopPedagogicalLoader() {
    clearInterval(phraseInterval);
    loadingBar.style.display = "none";
  }

  // Verificar status da API backend
  fetch("/api/health")
    .then(r => r.json())
    .then(data => {
      if (data.status === "online") {
        systemStatus.textContent = `${data.model} • Online`;
        const modelSelect = document.getElementById("model-select");
        if (modelSelect && data.model) {
          modelSelect.value = data.model;
        }
      }
    })
    .catch(() => {
      systemStatus.textContent = "Offline";
    });

  // Sincronizar Base de Dados na Nuvem (MongoDB Atlas)
  function checkDatabaseAndSyncModules() {
    const dbStatusPill = document.getElementById("db-status-pill");
    const dbStatusLabel = document.getElementById("db-status-label");
    
    fetch("/api/db/status")
      .then(r => r.json())
      .then(dbData => {
        if (dbData.connected) {
          if (dbStatusLabel) {
            dbStatusLabel.textContent = `🍃 Atlas • ${dbData.database}`;
          }
          if (dbStatusPill) {
            dbStatusPill.title = `MongoDB Atlas Conectado!\nBase de dados: ${dbData.database}\nMódulos: ${dbData.counts?.modules || 0}\nTópicos: ${dbData.counts?.threads || 0}\nRespostas: ${dbData.counts?.replies || 0}`;
          }
        } else {
          if (dbStatusLabel) dbStatusLabel.textContent = "💾 Armazenamento Local";
          if (dbStatusPill) dbStatusPill.title = "MongoDB Atlas offline ou sem credenciais. A utilizar modo local.";
        }
      })
      .catch(err => {
        console.warn("Erro ao contactar estado do MongoDB Atlas:", err);
      });

    // Carregar módulos dinâmicos da base de dados na nuvem
    fetch("/api/modules")
      .then(r => r.json())
      .then(res => {
        if (res && res.modules && res.modules.length > 0) {
          window.COURSE_MODULES = window.COURSE_MODULES || {};
          res.modules.forEach(m => {
            const key = m.topic_key || m.title;
            window.COURSE_MODULES[key] = m;
          });
          console.log(`[MONGODB ATLAS] Sincronizados ${res.modules.length} módulos curriculares com a base de dados na nuvem.`);
        }
      })
      .catch(err => {
        console.warn("A carregar módulos a partir da cache local:", err);
      });
  }

  checkDatabaseAndSyncModules();

  // Templates de dúvidas comuns para os botões temáticos
  const topicPrompts = {
    "Programação Linear": "Como formular matematicamente um problema de programação linear para uma linha de montagem industrial com restrições de matéria-prima e mão-de-obra? Apresente as hipóteses e variáveis.",
    "Método Simplex Primal": "Explique passo a passo a resolução pelo Método Simplex Primal de: Maximizar Z = 3x1 + 5x2 sujeito a x1 <= 4, 2x2 <= 12, 3x1 + 2x2 <= 18 com x1, x2 >= 0. Apresente os tableaux completos.",
    "Duas Fases e Grande M": "Quando e por que razão devemos aplicar o Método das Duas Fases ou o Método do Grande M em vez do Simplex padrão? Dê um exemplo com restrição do tipo '>='.",
    "Dualidade e Sensibilidade": "A partir de uma solução ótima primal em maximização, como lemos e interpretamos economicamente os preços-sombra (variáveis duais) e o Teorema das Folgas Complementares?",
    "Problemas de Transporte": "Como determinar a solução inicial admissível num problema de transportes pelo Método de Aproximação de Vogel (VAM) e verificar a sua otimalidade pelo método MODI?",
    "Optimização em Redes": "Qual a formulação matemática para o problema do Caminho Mais Curto (Shortest Path) e como o algoritmo de Dijkstra garante a otimalidade?",
    "Programação Inteira": "Explique o funcionamento do algoritmo Branch and Bound na resolução de problemas de Programação Linear Inteira (PLI) e a importância do relaxamento contínuo."
  };

  // Controlo dos Espaços: 0. Início | 1. Painel | 2. Sala de Aula | 3. Fórum | 4. Tutor IA
  const btnViewHome = document.getElementById("btn-view-home");
  const btnViewDashboard = document.getElementById("btn-view-dashboard");
  const btnViewLesson = document.getElementById("btn-view-lesson");
  const btnViewForum = document.getElementById("btn-view-forum");
  const btnViewChat = document.getElementById("btn-view-chat");
  const brandHomeLink = document.getElementById("brand-home-link");

  const homeView = document.getElementById("home-view");
  const dashboardView = document.getElementById("dashboard-view");
  const lessonView = document.getElementById("lesson-view");
  const forumView = document.getElementById("forum-view");
  const chatView = document.getElementById("chat-view");

  const lessonAskAiBtn = document.getElementById("lesson-ask-ai-btn");
  const lessonForumBtn = document.getElementById("lesson-forum-btn");
  let currentActiveTopic = "Programação Linear";
  let currentForumThreadId = null;

  function switchToView(mode) {
    // Resetar botões do cabeçalho
    if (btnViewHome) btnViewHome.classList.remove("active");
    if (btnViewDashboard) btnViewDashboard.classList.remove("active");
    if (btnViewLesson) btnViewLesson.classList.remove("active");
    if (btnViewForum) btnViewForum.classList.remove("active");
    if (btnViewChat) btnViewChat.classList.remove("active");

    // Esconder todas as vistas
    if (homeView) homeView.style.display = "none";
    if (dashboardView) dashboardView.style.display = "none";
    if (lessonView) lessonView.style.display = "none";
    if (forumView) forumView.style.display = "none";
    if (chatView) chatView.style.display = "none";

    // Controlo inteligente do painel lateral (Sidebar) conforme o contexto
    if (sidebar) {
      if (mode === "home" || mode === "dashboard") {
        sidebar.classList.add("collapsed");
        if (sidebarToggleBtn) sidebarToggleBtn.style.display = "none";
      } else {
        if (sidebarToggleBtn) sidebarToggleBtn.style.display = "flex";
        if (mode === "lesson" && window.innerWidth > 1024) {
          sidebar.classList.remove("collapsed");
        }
      }
    }

    if (mode === "home") {
      if (homeView) {
        homeView.style.display = "block";
        homeView.scrollTop = 0;
      }
      if (btnViewHome) btnViewHome.classList.add("active");
    } else if (mode === "dashboard") {
      if (dashboardView) {
        dashboardView.style.display = "block";
        dashboardView.scrollTop = 0;
      }
      if (btnViewDashboard) btnViewDashboard.classList.add("active");
      renderAcademicDashboard();
    } else if (mode === "lesson") {
      if (lessonView) {
        lessonView.style.display = "flex";
        lessonView.scrollTop = 0;
      }
      if (btnViewLesson) btnViewLesson.classList.add("active");
    } else if (mode === "forum") {
      if (forumView) {
        forumView.style.display = "flex";
        forumView.scrollTop = 0;
      }
      if (btnViewForum) btnViewForum.classList.add("active");
      loadForumThreads();
    } else {
      if (chatView) chatView.style.display = "flex";
      if (btnViewChat) btnViewChat.classList.add("active");
    }
  }

  if (btnViewHome) {
    btnViewHome.addEventListener("click", () => switchToView("home"));
  }
  if (brandHomeLink) {
    brandHomeLink.addEventListener("click", () => switchToView("home"));
  }
  if (btnViewDashboard) {
    btnViewDashboard.addEventListener("click", () => switchToView("dashboard"));
  }
  if (btnViewLesson) {
    btnViewLesson.addEventListener("click", () => {
      loadLesson(currentActiveTopic);
      switchToView("lesson");
    });
  }

  // Acções dos Botões da Página Inicial
  const homeBtnGoDashboard = document.getElementById("home-btn-go-dashboard");
  const homeBtnGoLesson = document.getElementById("home-btn-go-lesson");
  const homeBtnGoForum = document.getElementById("home-btn-go-forum");
  const homeBtnGoChat = document.getElementById("home-btn-go-chat");

  if (homeBtnGoDashboard) homeBtnGoDashboard.addEventListener("click", () => switchToView("dashboard"));
  if (homeBtnGoLesson) homeBtnGoLesson.addEventListener("click", () => {
    loadLesson(currentActiveTopic);
    switchToView("lesson");
  });
  if (homeBtnGoForum) homeBtnGoForum.addEventListener("click", () => switchToView("forum"));
  if (homeBtnGoChat) homeBtnGoChat.addEventListener("click", () => switchToView("chat"));

  // Clique nos Módulos da Página Inicial
  document.querySelectorAll(".home-module-card").forEach(card => {
    card.addEventListener("click", () => {
      const topic = card.dataset.topic;
      if (topic) {
        loadLesson(topic);
        switchToView("lesson");
      }
    });
  });

  if (btnViewForum) {
    btnViewForum.addEventListener("click", () => switchToView("forum"));
  }

  if (btnViewChat) {
    btnViewChat.addEventListener("click", () => switchToView("chat"));
  }

  if (lessonAskAiBtn) {
    lessonAskAiBtn.addEventListener("click", () => {
      switchToView("chat");
      const promptText = topicPrompts[currentActiveTopic] || `Esclareça as minhas dúvidas sobre ${currentActiveTopic}.`;
      userInput.value = promptText;
      adjustTextareaHeight();
      userInput.focus();
    });
  }

  if (lessonForumBtn) {
    lessonForumBtn.addEventListener("click", () => {
      switchToView("forum");
      const forumModuleSelect = document.getElementById("forum-module-filter");
      if (forumModuleSelect) {
        forumModuleSelect.value = currentActiveTopic;
        loadForumThreads();
      }
    });
  }

  // Navegação por Tabs dentro da Aula Universitária
  const lessonTabBtns = document.querySelectorAll(".lesson-tab-btn");
  lessonTabBtns.forEach(tabBtn => {
    tabBtn.addEventListener("click", () => {
      lessonTabBtns.forEach(b => b.classList.remove("active"));
      tabBtn.classList.add("active");
      const targetPanelId = tabBtn.dataset.tab;
      document.querySelectorAll(".lesson-panel").forEach(p => p.classList.remove("active"));
      const targetPanel = document.getElementById(targetPanelId);
      if (targetPanel) targetPanel.classList.add("active");
    });
  });

  // Carregamento Completo da Aula Universitária (15 Secções Rigorosas)
  function loadLesson(topicName) {
    if (typeof COURSE_MODULES === "undefined" || !COURSE_MODULES[topicName]) {
      console.warn(`Módulo "${topicName}" não encontrado na base de cursos.`);
      return;
    }

    currentActiveTopic = topicName;
    const mod = COURSE_MODULES[topicName];

    // Cabeçalho da Aula
    document.getElementById("lesson-title").textContent = mod.title;
    document.getElementById("lesson-subtitle").textContent = mod.subtitle;
    document.getElementById("lesson-module-code").textContent = mod.identification.code;
    document.getElementById("lesson-module-duration").textContent = mod.duration;
    document.getElementById("lesson-module-level").textContent = mod.level;

    // 1. Identificação
    const idGrid = document.getElementById("lesson-id-grid");
    idGrid.innerHTML = `
      <div class="id-card"><div class="id-card-label">Instituição</div><div class="id-card-val">${mod.identification.institution}</div></div>
      <div class="id-card"><div class="id-card-label">Carga Horária</div><div class="id-card-val">${mod.identification.workload}</div></div>
      <div class="id-card"><div class="id-card-label">Pré-requisitos</div><div class="id-card-val">${mod.prerequisites}</div></div>
      <div class="id-card"><div class="id-card-label">Palavras-chave</div><div class="id-card-val">${mod.identification.keywords.join(", ")}</div></div>
    `;

    // 2. Introdução
    document.getElementById("lesson-introduction").innerHTML = mod.introduction;

    // 3. Objectivos de Bloom
    const bloomList = document.getElementById("lesson-bloom-list");
    bloomList.innerHTML = mod.learningObjectives.map(obj => `
      <div class="bloom-item">
        <span class="bloom-tag">${obj.level}</span>
        <span class="bloom-desc">${obj.desc}</span>
      </div>
    `).join("");

    // 4. Competências
    document.getElementById("lesson-competencies").innerHTML = `
      <ul>${mod.competencies.map(c => `<li>${c}</li>`).join("")}</ul>
    `;

    // 5. Conceitos Fundamentais
    document.getElementById("lesson-concepts").innerHTML = mod.fundamentalConcepts;

    // 6. Fundamentos e Teoremas
    document.getElementById("lesson-theorems").innerHTML = mod.theoreticalFoundations;

    // 7. Formulação Matemática
    document.getElementById("lesson-formulation").innerHTML = mod.mathematicalFormulation;

    // 8. Algoritmos e Procedimentos
    document.getElementById("lesson-algorithm").innerHTML = mod.algorithmProcedure;

    // 9. Fluxograma em SVG
    document.getElementById("lesson-flowchart").innerHTML = mod.flowchartSVG;

    // 10. Exercício Resolvido
    document.getElementById("lesson-solved-exercise").innerHTML = mod.solvedExercise;

    // 11. Aplicações na Engenharia
    document.getElementById("lesson-applications").innerHTML = mod.engineeringApplications;

    // 12. Exercícios Propostos
    document.getElementById("lesson-proposed-exercises").innerHTML = mod.proposedExercises;

    // 13. Auto-Avaliação Interactiva (Quiz com Solução Revelável)
    const quizContainer = document.getElementById("lesson-quiz-container");
    quizContainer.innerHTML = mod.learningAssessment.map((q, qIdx) => `
      <div class="quiz-card" data-qidx="${qIdx}">
        <div class="quiz-q-title">${q.question}</div>
        <div class="quiz-options-list">
          ${q.options.map((opt, optIdx) => `
            <button type="button" class="quiz-opt-btn" data-q="${qIdx}" data-opt="${optIdx}">
              ${opt}
            </button>
          `).join("")}
        </div>
        <div class="quiz-feedback" id="quiz-feedback-${qIdx}">
          <strong>Explicação Científica:</strong> ${q.explanation}
        </div>
      </div>
    `).join("");

    // Eventos do Quiz
    quizContainer.querySelectorAll(".quiz-opt-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const qIdx = parseInt(btn.dataset.q, 10);
        const optIdx = parseInt(btn.dataset.opt, 10);
        const qData = mod.learningAssessment[qIdx];
        const card = btn.closest(".quiz-card");
        
        card.querySelectorAll(".quiz-opt-btn").forEach(b => {
          b.disabled = true;
          const bOpt = parseInt(b.dataset.opt, 10);
          if (bOpt === qData.correct) {
            b.classList.add("correct");
          } else if (b === btn) {
            b.classList.add("wrong");
          }
        });

        const feedback = document.getElementById(`quiz-feedback-${qIdx}`);
        if (feedback) feedback.classList.add("show");
      });
    });

    // 14. Síntese e Conclusões
    document.getElementById("lesson-synthesis").innerHTML = mod.synthesis;

    // 15. Referências Bibliográficas
    const refContainer = document.getElementById("lesson-references");
    refContainer.innerHTML = `
      <ol>${mod.references.map(r => `<li><strong>[${r.num}]</strong> ${r.citation}</li>`).join("")}</ol>
    `;

    // Activar o primeiro tab por omissão
    lessonTabBtns[0].click();

    // Renderizar Fórmulas Matemáticas com LaTeX (MathJax)
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise([lessonView]).catch(err => console.error("Erro MathJax Aula:", err));
    }
  }

  // ==========================================================================
  // Fórum Académico Interactivo (Gestão de Discussões, Docentes e Tutor de IA)
  // ==========================================================================

  const forumThreadsContainer = document.getElementById("forum-threads-container");
  const forumThreadsGrid = document.getElementById("forum-threads-grid");
  const forumThreadsLoading = document.getElementById("forum-threads-loading");
  const forumThreadView = document.getElementById("forum-thread-view");
  const threadCardLead = document.getElementById("thread-card-lead");
  const repliesStream = document.getElementById("replies-stream");
  const repliesCountTitle = document.getElementById("thread-replies-counter");
  const btnBackToList = document.getElementById("btn-back-to-list");
  const btnSummonAi = document.getElementById("btn-summon-ai-tutor");
  const forumReplyForm = document.getElementById("forum-reply-form");
  const replyFormContent = document.getElementById("reply-form-content");
  const replyActiveAuthorPill = document.getElementById("reply-active-author-pill");
  const forumCurrentRole = document.getElementById("forum-current-role");
  
  // Modal de Nova Thread
  const forumModal = document.getElementById("forum-modal-container");
  const btnOpenNewThread = document.getElementById("btn-open-new-thread");
  const btnCloseThreadModal = document.getElementById("btn-close-thread-modal");
  const btnCancelThread = document.getElementById("btn-cancel-thread");
  const forumCreateThreadForm = document.getElementById("forum-create-thread-form");
  const modalThreadModule = document.getElementById("modal-thread-module");
  const modalThreadTitle = document.getElementById("modal-thread-title");
  const modalThreadContent = document.getElementById("modal-thread-content");
  const modalThreadAuthor = document.getElementById("modal-thread-author");

  // Filtros e Pesquisa
  const forumModuleFilter = document.getElementById("forum-module-filter");
  const forumFilterPills = document.querySelectorAll(".forum-filter-pill");
  const forumSearchBox = document.getElementById("forum-search-box");
  const forumDoSearch = document.getElementById("forum-do-search");
  let activeForumFilter = "all";

  // Actualizar indicador de papel (Estudante vs. Docente)
  function updateRoleDisplay() {
    const role = forumCurrentRole ? forumCurrentRole.value : "student";
    if (replyActiveAuthorPill) {
      replyActiveAuthorPill.innerHTML = role === "teacher" 
        ? "Intervindo como: <strong>Docente (FE-UEM)</strong>" 
        : "Intervindo como: <strong>Estudante</strong>";
    }
    if (modalThreadAuthor) {
      modalThreadAuthor.value = role === "teacher" ? "Prof. Docente FE-UEM" : "Estudante FE-UEM";
    }
  }

  if (forumCurrentRole) {
    forumCurrentRole.addEventListener("change", updateRoleDisplay);
    updateRoleDisplay();
  }

  // Carregar lista de tópicos do Fórum
  async function loadForumThreads() {
    if (!forumThreadsGrid) return;
    
    // Assegurar visibilidade da grelha de threads
    forumThreadsContainer.style.display = "block";
    forumThreadView.style.display = "none";
    forumThreadsLoading.style.display = "block";
    forumThreadsGrid.innerHTML = "";

    const selectedModule = forumModuleFilter ? forumModuleFilter.value : "Todos";
    const searchTerm = forumSearchBox ? forumSearchBox.value.trim() : "";

    let url = `/api/forum/threads?module=${encodeURIComponent(selectedModule)}&filter=${encodeURIComponent(activeForumFilter)}`;
    if (searchTerm) {
      url += `&search=${encodeURIComponent(searchTerm)}`;
    }

    try {
      const resp = await fetch(url);
      const data = await resp.json();
      forumThreadsLoading.style.display = "none";

      if (!data.threads || data.threads.length === 0) {
        forumThreadsGrid.innerHTML = `
          <div style="text-align: center; padding: 40px 20px; color: var(--text-muted); font-size: 0.9em;">
            Nenhuma discussão encontrada para os filtros actuais. Seja o primeiro a submeter uma questão ao fórum!
          </div>
        `;
        return;
      }

      forumThreadsGrid.innerHTML = data.threads.map(t => {
        const valBadge = t.is_validated 
          ? `<span class="thread-validation-tag">✓ Validada por Docente</span>` 
          : "";
        
        let roleBadgeClass = "student";
        let roleLabel = "Estudante";
        if (t.author_role === "teacher") {
          roleBadgeClass = "teacher";
          roleLabel = "Docente FE-UEM";
        }

        return `
          <div class="thread-item-card" data-thread-id="${t.id}">
            <div class="thread-item-top">
              <span class="thread-module-tag">${escapeHTML(t.module_id)}</span>
              ${valBadge}
            </div>
            <h4 class="thread-item-title">${escapeHTML(t.title)}</h4>
            <p class="thread-item-preview">${escapeHTML(t.content)}</p>
            <div class="thread-item-meta">
              <span>Por <strong>${escapeHTML(t.author_name)}</strong> &bull; <span class="thread-item-author-role">${roleLabel}</span> &bull; ${t.created_at}</span>
              <span class="thread-replies-pill">💬 ${t.reply_count} ${t.reply_count === 1 ? 'resposta' : 'respostas'}</span>
            </div>
          </div>
        `;
      }).join("");

      // Clique para abrir detalhes
      forumThreadsGrid.querySelectorAll(".thread-item-card").forEach(card => {
        card.addEventListener("click", () => {
          const tid = card.dataset.threadId;
          openThreadDetail(tid);
        });
      });

    } catch (err) {
      forumThreadsLoading.style.display = "none";
      forumThreadsGrid.innerHTML = `<div style="color: red; padding: 20px;">Erro ao carregar discussões do fórum.</div>`;
      console.error(err);
    }
  }

  // Abrir detalhes de uma thread
  async function openThreadDetail(threadId) {
    currentForumThreadId = threadId;
    forumThreadsContainer.style.display = "none";
    forumThreadView.style.display = "flex";
    threadCardLead.innerHTML = "<em>A carregar discussão...</em>";
    repliesStream.innerHTML = "";

    try {
      const resp = await fetch(`/api/forum/thread?id=${threadId}`);
      const data = await resp.json();
      if (!data.thread) return;

      const t = data.thread;
      const isTeacher = (currentUser && (currentUser.role === "teacher_regent" || currentUser.role === "teacher_assistant")) || (forumCurrentRole && forumCurrentRole.value === "teacher");

      // Renderizar o tópico principal
      let leadRoleBadge = `<span class="author-role-badge ${t.author_role}">${t.author_role === 'teacher' ? 'Docente FE-UEM' : 'Estudante'}</span>`;
      let valBtn = "";
      if (isTeacher) {
        valBtn = `
          <button type="button" class="validate-action-btn ${t.is_validated ? 'endorsed' : ''}" id="btn-toggle-thread-val">
            ${t.is_validated ? '✓ Validada pelo Docente' : 'Marcar como Validada Cientificamente'}
          </button>
        `;
      } else if (t.is_validated) {
        valBtn = `<span class="thread-validation-tag">✓ Validada Cientificamente pelo Docente</span>`;
      }

      threadCardLead.innerHTML = `
        <div class="thread-lead-top">
          <div class="thread-author-badge-group">
            <span class="thread-module-tag">${escapeHTML(t.module_id)}</span>
            ${leadRoleBadge}
            <span style="font-size: 0.8em; color: var(--text-muted);">${escapeHTML(t.author_name)} &bull; ${t.created_at}</span>
          </div>
          <div>${valBtn}</div>
        </div>
        <h2 class="thread-lead-title">${escapeHTML(t.title)}</h2>
        <div class="thread-lead-body">${clean_and_format_html(t.content)}</div>
      `;

      if (isTeacher) {
        const toggleBtn = document.getElementById("btn-toggle-thread-val");
        if (toggleBtn) {
          toggleBtn.addEventListener("click", async () => {
            await fetch("/api/forum/validate", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ thread_id: currentForumThreadId })
            });
            openThreadDetail(currentForumThreadId);
          });
        }
      }

      // Renderizar respostas encadeadas
      renderRepliesStream(t.replies);

      // Renderizar fórmulas com MathJax
      if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([forumThreadView]).catch(e => console.error(e));
      }

    } catch (err) {
      console.error("Erro ao carregar detalhes da thread:", err);
    }
  }

  function renderRepliesStream(replies) {
    repliesCountTitle.textContent = `${replies.length} ${replies.length === 1 ? 'Resposta e Contribuição' : 'Respostas e Contribuições Científicas'}`;

    if (replies.length === 0) {
      repliesStream.innerHTML = `
        <div style="padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-muted); border-radius: 6px; font-size: 0.88em;">
          Ainda não foram publicadas respostas a esta questão. Pode ser o primeiro a responder ou solicitar o parecer do Tutor de IA acima!
        </div>
      `;
      return;
    }

    const isTeacher = (currentUser && (currentUser.role === "teacher_regent" || currentUser.role === "teacher_assistant")) || (forumCurrentRole && forumCurrentRole.value === "teacher");

    repliesStream.innerHTML = replies.map(r => {
      let cardClass = "reply-card";
      let roleBadge = `<span class="author-role-badge student">Estudante</span>`;

      if (r.author_role === "ai_tutor") {
        cardClass += " ai-tutor-reply";
        roleBadge = `<span class="author-role-badge ai_tutor">🤖 Resposta do Tutor de IA</span>`;
      } else if (r.author_role === "teacher") {
        cardClass += " teacher-reply";
        roleBadge = `<span class="author-role-badge teacher">👨‍🏫 Docente FE-UEM</span>`;
      }

      let endorsedBadge = "";
      if (r.is_endorsed) {
        endorsedBadge = `<span style="font-size: 0.76em; font-weight: 700; background: #18181b; color: #fff; padding: 2px 8px; border-radius: 10px;">✓ Validação Docente</span>`;
      }

      let teacherValidateAction = "";
      if (isTeacher && r.author_role !== "teacher") {
        teacherValidateAction = `
          <div class="reply-footer-actions">
            <button type="button" class="validate-action-btn ${r.is_endorsed ? 'endorsed' : ''}" data-reply-id="${r.id}">
              ${r.is_endorsed ? '✓ Resposta Validada pelo Docente' : 'Validar Resposta como Docente'}
            </button>
          </div>
        `;
      }

      let referencesHtml = "";
      if (r.references_cited && r.references_cited.length > 0) {
        referencesHtml = `
          <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border-hairline); font-size: 0.82em; color: var(--text-muted);">
            <strong>Fontes Verificadas:</strong> ${r.references_cited.join("; ")}
          </div>
        `;
      }

      return `
        <div class="${cardClass}" id="reply-${r.id}">
          <div class="reply-top-meta">
            <div style="display: flex; align-items: center; gap: 8px;">
              ${roleBadge}
              <strong>${escapeHTML(r.author_name)}</strong>
              <span style="color: var(--text-muted); font-size: 0.9em;">&bull; ${r.created_at}</span>
            </div>
            <div>${endorsedBadge}</div>
          </div>
          <div class="reply-body-content">${clean_and_format_html(r.content)}</div>
          ${referencesHtml}
          ${teacherValidateAction}
        </div>
      `;
    }).join("");

    // Eventos de validação de resposta para docentes
    if (isTeacher) {
      repliesStream.querySelectorAll(".validate-action-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          const rid = btn.dataset.replyId;
          await fetch("/api/forum/validate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ thread_id: currentForumThreadId, reply_id: parseInt(rid, 10) })
          });
          openThreadDetail(currentForumThreadId);
        });
      });
    }
  }

  // Voltar à lista de threads
  if (btnBackToList) {
    btnBackToList.addEventListener("click", () => {
      forumThreadView.style.display = "none";
      forumThreadsContainer.style.display = "block";
      loadForumThreads();
    });
  }

  // Consultar Tutor de IA na Discussão
  if (btnSummonAi) {
    btnSummonAi.addEventListener("click", async () => {
      if (!currentForumThreadId) return;
      btnSummonAi.disabled = true;
      const originalText = btnSummonAi.innerHTML;
      btnSummonAi.innerHTML = '<span>🤖 A processar parecer didáctico com RAG...</span>';

      try {
        const resp = await fetch("/api/forum/summon_ai", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ thread_id: currentForumThreadId })
        });
        const data = await resp.json();
        if (data.thread) {
          renderRepliesStream(data.thread.replies);
          if (window.MathJax && window.MathJax.typesetPromise) {
            window.MathJax.typesetPromise([repliesStream]).catch(e => console.error(e));
          }
        }
      } catch (err) {
        console.error("Erro ao invocar Tutor de IA:", err);
      } finally {
        btnSummonAi.disabled = false;
        btnSummonAi.innerHTML = originalText;
      }
    });
  }

  // Enviar nova resposta na discussão
  if (forumReplyForm) {
    forumReplyForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const content = replyFormContent.value.trim();
      if (!content || !currentForumThreadId) return;

      const isTeach = currentUser && (currentUser.role === "teacher_regent" || currentUser.role === "teacher_assistant");
      const role = isTeach ? "teacher" : "student";
      const author = currentUser ? `${currentUser.name} (${currentUser.role_title || (isTeach ? 'Docente' : 'Estudante')})` : (forumCurrentRole?.value === "teacher" ? "Prof. Docente FE-UEM" : "Estudante FE-UEM");

      try {
        const resp = await fetch("/api/forum/replies", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread_id: currentForumThreadId,
            author_name: author,
            author_role: role,
            content: content
          })
        });
        const data = await resp.json();
        replyFormContent.value = "";
        if (data.thread) {
          renderRepliesStream(data.thread.replies);
          if (window.MathJax && window.MathJax.typesetPromise) {
            window.MathJax.typesetPromise([repliesStream]).catch(e => console.error(e));
          }
        }
      } catch (err) {
        console.error("Erro ao enviar resposta:", err);
      }
    });
  }

  // Modal de Nova Thread
  if (btnOpenNewThread) {
    btnOpenNewThread.addEventListener("click", () => {
      forumModal.style.display = "flex";
      modalThreadTitle.focus();
    });
  }

  function closeThreadModal() {
    forumModal.style.display = "none";
    forumCreateThreadForm.reset();
    updateRoleDisplay();
  }

  if (btnCloseThreadModal) btnCloseThreadModal.addEventListener("click", closeThreadModal);
  if (btnCancelThread) btnCancelThread.addEventListener("click", closeThreadModal);

  // Submeter nova thread
  if (forumCreateThreadForm) {
    forumCreateThreadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const module_id = modalThreadModule.value;
      const title = modalThreadTitle.value.trim();
      const content = modalThreadContent.value.trim();
      const isTeach = currentUser && (currentUser.role === "teacher_regent" || currentUser.role === "teacher_assistant");
      const role = isTeach ? "teacher" : "student";
      const author = currentUser ? `${currentUser.name} (${currentUser.role_title || (isTeach ? 'Docente' : 'Estudante')})` : (modalThreadAuthor.value.trim() || "Estudante FE-UEM");

      try {
        const resp = await fetch("/api/forum/threads", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            module_id: module_id,
            title: title,
            content: content,
            author_name: author,
            author_role: role,
            tags: [module_id]
          })
        });
        const data = await resp.json();
        closeThreadModal();
        if (data.thread) {
          openThreadDetail(data.thread.id);
        }
      } catch (err) {
        console.error("Erro ao criar thread:", err);
      }
    });
  }

  // Filtros de módulo, pesquisa e status pills
  if (forumModuleFilter) {
    forumModuleFilter.addEventListener("change", loadForumThreads);
  }

  forumFilterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      forumFilterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeForumFilter = pill.dataset.filter;
      loadForumThreads();
    });
  });

  if (forumSearchBox) {
    forumSearchBox.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        loadForumThreads();
      }
    });
  }

  if (forumDoSearch) {
    forumDoSearch.addEventListener("click", loadForumThreads);
  }

  // Intercepção ao clicar nos tópicos curriculares: abre a aula universitária completa
  topicItems.forEach(btn => {
    btn.addEventListener("click", () => {
      const topic = btn.dataset.topic;
      loadLesson(topic);
      switchToView("lesson");
      if (window.innerWidth <= 840) closeSidebar();
    });
  });

  // Pílulas de sugestão rápida
  suggestionPills.forEach(pill => {
    pill.addEventListener("click", () => {
      userInput.value = pill.dataset.prompt;
      adjustTextareaHeight();
      userInput.focus();
    });
  });

  // Redimensionamento automático do campo de texto
  function adjustTextareaHeight() {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 160) + "px";
  }

  userInput.addEventListener("input", adjustTextareaHeight);

  // Submissão com Enter (Shift+Enter para quebra de linha)
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // Estado de bloqueio concorrencial (Console Lock do Modelo)
  let isModelProcessing = false;

  // Submissão do chat
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (isModelProcessing) {
      console.warn("🔒 [CONSOLE LOCK ACTIVO] O processamento do modelo ainda está em execução. Aguarde a conclusão da resposta anterior.");
      return;
    }

    const message = userInput.value.trim();
    if (!message) return;

    // Activar o Console Lock na interface
    isModelProcessing = true;
    const submitBtn = document.getElementById("send-btn");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.setAttribute("data-original-html", submitBtn.innerHTML);
      submitBtn.innerHTML = '<span>A processar...</span>';
    }
    userInput.disabled = true;

    // Adicionar mensagem do utilizador ao ecrã
    appendMessage("Estudante", message, "user-message");
    userInput.value = "";
    adjustTextareaHeight();

    // Adicionar ao histórico
    conversationHistory.push({ sender: "user", text: message });

    startPedagogicalLoader();

    const modelSelect = document.getElementById("model-select");
    const chosenModel = modelSelect ? modelSelect.value : "llama3.2:3b";

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: message,
          model: chosenModel,
          history: conversationHistory
        })
      });

      const data = await response.json();
      stopPedagogicalLoader();

      if (!response.ok || data.error) {
        const errorMsg = data.error || `Erro HTTP ${response.status}: Falha ao processar com o modelo.`;
        console.error("🚨 [CONSOLE LOG - FALHA NO PROCESSAMENTO DO MODELO]", {
          timestamp: new Date().toISOString(),
          modelo_solicitado: chosenModel,
          status_http: response.status,
          erro_tecnico: errorMsg,
          questao_enviada: message
        });
        appendAssistantRawHTML(`<div style="color: #18181b; padding: 12px 16px; background: #f4f4f5; border: 1px solid #e4e4e7; border-left: 3px solid #18181b; border-radius: 4px; font-size: 0.9em;"><strong>Aviso:</strong> ${escapeHTML(errorMsg)}</div>`);
      } else {
        if (data.model_failed) {
          console.warn("⚠️ [CONSOLE LOG - AVISO DE CONTINGÊNCIA / FALLBACK ACCIONADO]", {
            timestamp: new Date().toISOString(),
            modelo_solicitado: chosenModel,
            motivo_falha: data.failure_reason,
            provedor_utilizado: data.provider,
            acao: "Fallback automático para o Motor Académico FE-UEM"
          });
        } else {
          console.log("✅ [CONSOLE LOG - SUCESSO NO MODELO]", {
            timestamp: new Date().toISOString(),
            modelo: chosenModel,
            provedor: data.provider
          });
        }

        conversationHistory.push({ sender: "assistant", text: data.reply });
        appendAssistantRawHTML(data.reply);
      }
    } catch (err) {
      stopPedagogicalLoader();
      console.error("🚨 [CONSOLE LOG - ERRO CRÍTICO / EXCEPÇÃO DE REDE NO MODELO]", {
        timestamp: new Date().toISOString(),
        modelo_solicitado: chosenModel,
        mensagem_erro: err.message || err,
        stack_trace: err.stack,
        questao_enviada: message
      });
      appendAssistantRawHTML(`<div style="color: #18181b; padding: 12px 16px; background: #f4f4f5; border: 1px solid #e4e4e7; border-left: 3px solid #18181b; border-radius: 4px; font-size: 0.9em;"><strong>Erro de Comunicação:</strong> Ocorreu uma interrupção de rede. Consulte a consola (F12) para detalhes.</div>`);
    } finally {
      // Libertar o Console Lock da interface
      isModelProcessing = false;
      if (submitBtn) {
        submitBtn.disabled = false;
        const orig = submitBtn.getAttribute("data-original-html");
        if (orig) submitBtn.innerHTML = orig;
      }
      userInput.disabled = false;
      userInput.focus();
    }
  });

  function appendMessage(sender, text, cssClass) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${cssClass}`;

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    msgDiv.innerHTML = `
      <div class="message-meta">
        <span class="sender-name">${sender}</span>
        <span class="message-time">${now}</span>
      </div>
      <div class="message-body">${escapeHTML(text)}</div>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendAssistantRawHTML(htmlContent) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message assistant-message";

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    msgDiv.innerHTML = `
      <div class="message-meta">
        <span class="sender-name">Assistente de Investigação Operacional</span>
        <span class="message-time">${now}</span>
      </div>
      <div class="message-body">${htmlContent}</div>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Renderizar equações LaTeX dinamicamente pelo MathJax
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise([msgDiv]).catch((err) => console.error("Erro MathJax:", err));
    }
  }

  function escapeHTML(str) {
    const p = document.createElement("p");
    p.textContent = str;
    return p.innerHTML;
  }

  // ==============================================================================
  // SISTEMA DE AUTENTICAÇÃO, CONTROLO DE ACESSO (RBAC) E PAINÉIS ACADÉMICOS
  // ==============================================================================

  let authToken = localStorage.getItem("fe_uem_auth_token") || "";
  let currentUser = {
    name: "Edilson Macamo",
    email: "estudante@fe.uem.mz",
    role: "student",
    role_title: "Estudante",
    status: "active",
    student_number: "2024-ENG-089",
    course: "Licenciatura em Engenharia Mecânica"
  };

  // Elementos do Modal de Autenticação
  const authModalContainer = document.getElementById("auth-modal-container");
  const authModalCloseBtn = document.getElementById("auth-modal-close-btn");
  const headerAuthActionBtn = document.getElementById("header-auth-action-btn");
  const headerAuthActionText = document.getElementById("header-auth-action-text");
  const headerUserRole = document.getElementById("header-user-role");
  const headerUserName = document.getElementById("header-user-name");
  const dashSwitchAccountBtn = document.getElementById("dash-switch-account-btn");
  const dashboardBtnLabel = document.getElementById("dashboard-btn-label");

  // Abas do Modal
  const authTabBtns = document.querySelectorAll(".auth-tab-btn");
  const authTabPanes = document.querySelectorAll(".auth-tab-pane");
  const authAlertBox = document.getElementById("auth-alert-box");

  // Formulários
  const formLogin = document.getElementById("form-login");
  const formRegister = document.getElementById("form-register");
  const formForgotRequest = document.getElementById("form-forgot-request");
  const formForgotConfirm = document.getElementById("form-forgot-confirm");

  function showAuthAlert(msg, type = "info") {
    if (!authAlertBox) return;
    authAlertBox.className = `auth-alert-box ${type} show`;
    authAlertBox.textContent = msg;
  }

  function hideAuthAlert() {
    if (!authAlertBox) return;
    authAlertBox.className = "auth-alert-box";
    authAlertBox.textContent = "";
  }

  function openAuthModal(targetTab = "tab-login") {
    hideAuthAlert();
    authTabBtns.forEach(btn => btn.classList.toggle("active", btn.dataset.tab === targetTab));
    authTabPanes.forEach(pane => pane.classList.toggle("active", pane.id === targetTab));
    if (authModalContainer) authModalContainer.style.display = "flex";
  }

  function closeAuthModal() {
    if (authModalContainer) authModalContainer.style.display = "none";
  }

  if (authModalCloseBtn) authModalCloseBtn.addEventListener("click", closeAuthModal);
  if (dashSwitchAccountBtn) dashSwitchAccountBtn.addEventListener("click", () => openAuthModal("tab-login"));

  // Alternar abas do modal
  authTabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      hideAuthAlert();
      authTabBtns.forEach(b => b.classList.remove("active"));
      authTabPanes.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  // Elementos do Menu Dropdown do Utilizador
  const userProfileMenuWrapper = document.getElementById("user-profile-menu-wrapper");
  const userProfileTrigger = document.getElementById("user-profile-trigger");
  const userDropdownCard = document.getElementById("user-dropdown-card");
  const userAvatarInitials = document.getElementById("user-avatar-initials");
  const dropdownUserName = document.getElementById("dropdown-user-name");
  const dropdownUserEmail = document.getElementById("dropdown-user-email");
  const dropdownUserCourse = document.getElementById("dropdown-user-course");
  const dropdownItemDashboard = document.getElementById("dropdown-item-dashboard");
  const dropdownItemSwitch = document.getElementById("dropdown-item-switch");
  const dropdownItemLogout = document.getElementById("dropdown-item-logout");

  function getInitials(name) {
    if (!name) return "FE";
    const cleaned = name.replace(/Prof\.|Doutor|Doutora|Eng\./gi, "").trim();
    const words = cleaned.split(/\s+/).filter(Boolean);
    if (words.length >= 2) {
      return (words[0][0] + words[words.length - 1][0]).toUpperCase();
    }
    return words[0] ? words[0].slice(0, 2).toUpperCase() : "FE";
  }

  // Actualizar cabeçalho e perfil
  function updateHeaderUserUI() {
    if (!currentUser) {
      if (headerUserName) headerUserName.textContent = "Iniciar Sessão";
      if (headerUserRole) {
        headerUserRole.textContent = "Visitante";
        headerUserRole.className = "user-trigger-role-badge";
      }
      if (userAvatarInitials) userAvatarInitials.textContent = "FE";
      if (dashboardBtnLabel) dashboardBtnLabel.textContent = "Painel";
      return;
    }

    const initials = getInitials(currentUser.name);
    if (userAvatarInitials) userAvatarInitials.textContent = initials;
    if (headerUserName) headerUserName.textContent = currentUser.name.split(" ")[0] + " " + (currentUser.name.split(" ")[1] || "");
    if (dropdownUserName) dropdownUserName.textContent = currentUser.name;
    if (dropdownUserEmail) dropdownUserEmail.textContent = currentUser.email;
    if (dropdownUserCourse) dropdownUserCourse.textContent = currentUser.course || currentUser.department || "FE-UEM";

    if (headerUserRole) {
      if (currentUser.role === "teacher_regent") {
        headerUserRole.textContent = "Docente Regente";
        if (dashboardBtnLabel) dashboardBtnLabel.textContent = "Painel Docente";
      } else if (currentUser.role === "teacher_assistant") {
        headerUserRole.textContent = "Docente Assistente";
        if (dashboardBtnLabel) dashboardBtnLabel.textContent = "Painel Assistente";
      } else {
        headerUserRole.textContent = "Estudante";
        if (dashboardBtnLabel) dashboardBtnLabel.textContent = "Meu Painel";
      }
    }

    // Sincronizar selector do fórum
    const forumRoleSelector = document.getElementById("forum-current-role");
    if (forumRoleSelector) {
      forumRoleSelector.value = (currentUser.role === "teacher_regent" || currentUser.role === "teacher_assistant") ? "teacher" : "student";
    }
  }

  // Toggle do Dropdown do Utilizador
  if (userProfileTrigger) {
    userProfileTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      if (!currentUser) {
        openAuthModal("tab-login");
        return;
      }
      const isOpen = userDropdownCard.style.display === "block";
      userDropdownCard.style.display = isOpen ? "none" : "block";
      if (userProfileMenuWrapper) userProfileMenuWrapper.classList.toggle("open", !isOpen);
    });
  }

  // Fechar dropdown ao clicar fora
  document.addEventListener("click", (e) => {
    if (userProfileMenuWrapper && !userProfileMenuWrapper.contains(e.target)) {
      if (userDropdownCard) userDropdownCard.style.display = "none";
      userProfileMenuWrapper.classList.remove("open");
    }
  });

  if (dropdownItemDashboard) {
    dropdownItemDashboard.addEventListener("click", () => {
      if (userDropdownCard) userDropdownCard.style.display = "none";
      if (userProfileMenuWrapper) userProfileMenuWrapper.classList.remove("open");
      switchToView("dashboard");
    });
  }

  if (dropdownItemSwitch) {
    dropdownItemSwitch.addEventListener("click", () => {
      if (userDropdownCard) userDropdownCard.style.display = "none";
      if (userProfileMenuWrapper) userProfileMenuWrapper.classList.remove("open");
      openAuthModal("tab-login");
    });
  }

  // Logout Confiável e Imediato
  async function performLogout() {
    if (userDropdownCard) userDropdownCard.style.display = "none";
    if (userProfileMenuWrapper) userProfileMenuWrapper.classList.remove("open");

    if (confirm("Deseja realmente terminar a sua sessão académica na plataforma?")) {
      if (authToken) {
        try {
          await fetch("/api/auth/logout", {
            method: "POST",
            headers: { "Authorization": `Bearer ${authToken}` }
          });
        } catch (e) { /* ignorar */ }
      }
      localStorage.removeItem("fe_uem_auth_token");
      authToken = "";
      currentUser = null;
      updateHeaderUserUI();
      switchToView("home");
      openAuthModal("tab-login");
      showAuthAlert("Sessão terminada com sucesso. Pode agora iniciar sessão com outra conta.", "info");
    }
  }

  if (dropdownItemLogout) {
    dropdownItemLogout.addEventListener("click", performLogout);
  }

  // Botões de Demonstração Rápida (1-Clique)
  document.querySelectorAll(".demo-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const email = btn.dataset.email;
      const pass = btn.dataset.pass;
      document.getElementById("login-email").value = email;
      document.getElementById("login-password").value = pass;
      await performLogin(email, pass);
    });
  });

  // Função central de Login
  async function performLogin(email, password) {
    hideAuthAlert();
    try {
      const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await resp.json();
      if (!resp.ok) {
        showAuthAlert(data.error || "Erro ao iniciar sessão.", "error");
        return;
      }

      authToken = data.token;
      currentUser = data.user;
      localStorage.setItem("fe_uem_auth_token", authToken);

      updateHeaderUserUI();
      closeAuthModal();

      // Redireccionamento automático baseado em regras de perfil (RBAC)
      switchToView("dashboard");
    } catch (err) {
      showAuthAlert("Falha de rede ao tentar contactar o servidor.", "error");
    }
  }

  if (formLogin) {
    formLogin.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("login-email").value.trim();
      const pass = document.getElementById("login-password").value.trim();
      await performLogin(email, pass);
    });
  }

  // Formulário de Registo
  if (formRegister) {
    formRegister.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideAuthAlert();

      const name = document.getElementById("reg-name").value.trim();
      const email = document.getElementById("reg-email").value.trim();
      const requested_role = document.getElementById("reg-role").value;
      const course_department = document.getElementById("reg-dept").value.trim();
      const password = document.getElementById("reg-password").value.trim();

      try {
        const resp = await fetch("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, email, requested_role, course_department, password })
        });
        const data = await resp.json();
        if (!resp.ok) {
          showAuthAlert(data.error || "Erro no registo.", "error");
          return;
        }

        if (data.status === "pending_approval") {
          showAuthAlert(data.message, "info");
        } else {
          showAuthAlert("Conta criada com sucesso! A iniciar sessão automaticamente...", "success");
          setTimeout(() => performLogin(email, password), 1200);
        }
      } catch (err) {
        showAuthAlert("Falha ao comunicar com o servidor.", "error");
      }
    });
  }

  // Solicitar Código de Recuperação
  if (formForgotRequest) {
    formForgotRequest.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideAuthAlert();
      const email = document.getElementById("recovery-email").value.trim();

      try {
        const resp = await fetch("/api/auth/forgot-password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email })
        });
        const data = await resp.json();
        if (!resp.ok) {
          showAuthAlert(data.error || "Erro ao solicitar recuperação.", "error");
          return;
        }

        showAuthAlert(`Código gerado com sucesso: ${data.reset_code} (válido por 30 minutos).`, "info");
        document.getElementById("recovery-code").value = data.reset_code;
        formForgotRequest.style.display = "none";
        formForgotConfirm.style.display = "block";
      } catch (err) {
        showAuthAlert("Falha ao solicitar código.", "error");
      }
    });
  }

  // Confirmar Recuperação com Código e Nova Palavra-passe
  if (formForgotConfirm) {
    formForgotConfirm.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideAuthAlert();
      const email = document.getElementById("recovery-email").value.trim();
      const reset_code = document.getElementById("recovery-code").value.trim();
      const new_password = document.getElementById("recovery-new-password").value.trim();

      try {
        const resp = await fetch("/api/auth/reset-password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, reset_code, new_password })
        });
        const data = await resp.json();
        if (!resp.ok) {
          showAuthAlert(data.error || "Erro ao redefinir.", "error");
          return;
        }

        showAuthAlert("Palavra-passe actualizada com sucesso! Pode agora aceder.", "success");
        setTimeout(() => {
          formForgotConfirm.style.display = "none";
          formForgotRequest.style.display = "block";
          document.getElementById("btn-tab-login").click();
          document.getElementById("login-email").value = email;
          document.getElementById("login-password").value = new_password;
        }, 1500);
      } catch (err) {
        showAuthAlert("Falha ao redefinir palavra-passe.", "error");
      }
    });
  }

  // ==============================================================================
  // RENDERIZAÇÃO DOS PAINÉIS ACADÉMICOS (ESTUDANTE VS DOCENTE)
  // ==============================================================================

  async function renderAcademicDashboard() {
    if (!currentUser) {
      openAuthModal("tab-login");
      return;
    }

    const dashUserBadge = document.getElementById("dash-user-badge");
    const dashUserGreeting = document.getElementById("dash-user-greeting");
    const dashUserSubinfo = document.getElementById("dash-user-subinfo");
    const studentContent = document.getElementById("student-dashboard-content");
    const teacherContent = document.getElementById("teacher-dashboard-content");

    dashUserGreeting.textContent = `Olá, ${currentUser.name}`;
    dashUserSubinfo.textContent = `${currentUser.course || "Engenharia"} • ${currentUser.student_number ? "Nº " + currentUser.student_number : currentUser.department || "FE-UEM"}`;

    const isTeacher = (currentUser.role === "teacher_regent" || currentUser.role === "teacher_assistant");

    if (isTeacher) {
      dashUserBadge.textContent = currentUser.role === "teacher_regent" ? "👨‍🏫 Docente Regente (Supervisão Científica)" : "👨‍🏫 Docente Assistente (Apoio Pedagógico)";
      dashUserBadge.className = currentUser.role === "teacher_regent" ? "dashboard-role-badge-large regent-role" : "dashboard-role-badge-large assistant-role";
      studentContent.style.display = "none";
      teacherContent.style.display = "block";
      renderTeacherDashboard();
    } else {
      dashUserBadge.textContent = "🎓 Estudante";
      dashUserBadge.className = "dashboard-role-badge-large student-role";
      studentContent.style.display = "block";
      teacherContent.style.display = "none";
      renderStudentDashboard();
    }
  }

  // Renderizar Painel do Estudante
  async function renderStudentDashboard() {
    let studentProgressMap = {};
    if (authToken) {
      try {
        const resp = await fetch("/api/student/progress", {
          headers: { "Authorization": `Bearer ${authToken}` }
        });
        if (resp.ok) {
          const data = await resp.json();
          (data.progress || []).forEach(p => {
            studentProgressMap[p.module_id] = p;
          });
        }
      } catch (e) { /* ignorar */ }
    }

    const modules = [
      { key: "Programação Linear", name: "1. Programação Linear e Modelação", code: "ENG-IO-01" },
      { key: "Método Simplex Primal", name: "2. Método Simplex Primal", code: "ENG-IO-02" },
      { key: "Duas Fases e Grande M", name: "3. Duas Fases & Grande M", code: "ENG-IO-03" },
      { key: "Dualidade e Sensibilidade", name: "4. Dualidade & Sensibilidade", code: "ENG-IO-04" },
      { key: "Problemas de Transporte", name: "5. Transportes & Afectação", code: "ENG-IO-05" },
      { key: "Optimização em Redes", name: "6. Redes, Fluxos & Grafos", code: "ENG-IO-06" },
      { key: "Programação Inteira", name: "7. Programação Linear Inteira", code: "ENG-IO-07" }
    ];

    const container = document.getElementById("student-modules-list-container");
    let completedCount = 0;
    let quizSum = 0;
    let quizCount = 0;

    container.innerHTML = modules.map(m => {
      const rec = studentProgressMap[m.key] || {};
      const secCount = (rec.completed_sections || []).length;
      // 15 secções por módulo
      const pct = Math.min(100, Math.round((secCount / 15) * 100));
      if (pct >= 80) completedCount++;
      if (rec.quiz_score > 0) {
        quizSum += rec.quiz_score;
        quizCount++;
      }

      return `
        <div class="card border shadow-sm rounded-3 p-3 mb-3 d-flex flex-row align-items-center justify-content-between gap-3 flex-wrap module-progress-item bg-white">
          <div class="module-progress-info" style="flex: 1; min-width: 240px;">
            <div class="fw-bold text-dark module-progress-name">${m.name}</div>
            <div class="text-secondary small module-progress-sub">${m.code} &bull; ${secCount} de 15 secções pedagógicas exploradas</div>
          </div>
          <div class="d-flex align-items-center gap-3 flex-grow-1 module-progress-bar-wrapper" style="min-width: 180px;">
            <div class="progress flex-grow-1 module-progress-track" style="height: 8px;">
              <div class="progress-bar bg-success module-progress-fill" style="width: ${pct || 8}%;"></div>
            </div>
            <span class="fw-bold text-dark small module-progress-percent">${pct}%</span>
          </div>
          <button type="button" class="btn btn-outline-dark btn-sm rounded-2 px-3 module-progress-action-btn" data-topic="${m.key}">
            Aceder à Aula
          </button>
        </div>
      `;
    }).join("");

    // Adicionar eventos aos botões
    container.querySelectorAll(".module-progress-action-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const topic = btn.dataset.topic;
        loadLesson(topic);
        switchToView("lesson");
      });
    });

    // Métricas do Estudante
    const overallPct = Math.round((completedCount / 7) * 100);
    document.getElementById("dash-student-modules-count").textContent = `${completedCount} / 7`;
    document.getElementById("dash-student-progress-pct").textContent = `${overallPct}%`;
    document.getElementById("dash-student-quiz-score").textContent = quizCount > 0 ? `${Math.round(quizSum / quizCount)}/100` : "--";
  }

  // Renderizar Painel do Docente
  async function renderTeacherDashboard() {
    // Gestão de Subtabs do Docente
    const subtabBtns = document.querySelectorAll(".docente-subtab-btn");
    const subtabPanes = document.querySelectorAll(".docente-subtab-pane");

    subtabBtns.forEach(btn => {
      btn.onclick = () => {
        subtabBtns.forEach(b => b.classList.remove("active"));
        subtabPanes.forEach(p => { p.classList.remove("active"); p.style.display = "none"; });
        btn.classList.add("active");
        const pane = document.getElementById(btn.dataset.subtab);
        if (pane) { pane.classList.add("active"); pane.style.display = "block"; }
      };
    });

    // RBAC: Se for Assistente, ocultar a aba de permissões e aprovação de docentes
    const teamSubtabBtn = document.getElementById("teacher-subtab-team-btn");
    if (currentUser.role === "teacher_assistant") {
      if (teamSubtabBtn) teamSubtabBtn.style.display = "none";
    } else {
      if (teamSubtabBtn) teamSubtabBtn.style.display = "inline-block";
    }

    // 1. Carregar Analytics
    try {
      const resp = await fetch("/api/admin/analytics", {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (resp.ok) {
        const data = await resp.json();
        const a = data.analytics;
        document.getElementById("dash-teacher-students-count").textContent = a.total_students || 0;
        document.getElementById("dash-teacher-staff-count").textContent = a.total_teachers || 0;
        document.getElementById("dash-teacher-threads-count").textContent = a.total_threads || 0;
        document.getElementById("dash-teacher-validated-count").textContent = a.validated_threads || 0;
      }
    } catch (e) { /* ignorar */ }

    // 2. Carregar Lista de Utilizadores (Estudantes, Equipa e Pendentes)
    try {
      const resp = await fetch("/api/admin/users", {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (resp.ok) {
        const data = await resp.json();
        const users = data.users || [];

        // Preencher Estudantes
        const students = users.filter(u => u.role === "student");
        const studentsTbody = document.getElementById("teacher-students-tbody");
        if (studentsTbody) {
          studentsTbody.innerHTML = students.map(s => `
            <tr>
              <td><strong>${escapeHTML(s.name)}</strong></td>
              <td>${escapeHTML(s.email)}</td>
              <td>${escapeHTML(s.course || "Engenharia")}</td>
              <td>${escapeHTML(s.student_number || "--")}</td>
              <td><span style="color:#16a34a; font-weight:600;">✓ Activo</span></td>
              <td>${s.last_login || s.created_at || "Hoje"}</td>
            </tr>
          `).join("") || `<tr><td colspan="6" style="text-align:center; color:#71717a;">Nenhum estudante registado ainda.</td></tr>`;
        }

        // Preencher Candidatos Pendentes (Apenas Regente pode aprovar)
        const pending = users.filter(u => u.status === "pending_approval" || u.role === "teacher_applicant");
        const pendingTbody = document.getElementById("pending-teachers-tbody");
        if (pendingTbody) {
          pendingTbody.innerHTML = pending.map(p => `
            <tr>
              <td><strong>${escapeHTML(p.name)}</strong></td>
              <td>${escapeHTML(p.email)}</td>
              <td>${escapeHTML(p.course || "Docência FE-UEM")}</td>
              <td>${p.created_at || "Hoje"}</td>
              <td>
                <button type="button" class="teacher-action-pill-btn" onclick="window.approveTeacher('${p.email}', 'teacher_assistant')">
                  Aprovar Assistente
                </button>
                <button type="button" class="teacher-action-pill-btn" onclick="window.approveTeacher('${p.email}', 'teacher_regent')">
                  Aprovar Regente
                </button>
              </td>
            </tr>
          `).join("") || `<tr><td colspan="5" style="text-align:center; color:#71717a;">Nenhum pedido de autorização pendente.</td></tr>`;
        }

        // Preencher Corpo Docente Activo
        const activeTeachers = users.filter(u => u.role === "teacher_regent" || u.role === "teacher_assistant");
        const activeTbody = document.getElementById("active-teachers-tbody");
        if (activeTbody) {
          activeTbody.innerHTML = activeTeachers.map(t => `
            <tr>
              <td><strong>${escapeHTML(t.name)}</strong></td>
              <td>${escapeHTML(t.email)}</td>
              <td><span class="user-badge-role ${t.role === 'teacher_regent' ? 'regent-role' : 'assistant-role'}">${t.role_title}</span></td>
              <td style="font-size:0.8em; color:#52525b;">${t.role === 'teacher_regent' ? 'Total (Gestão Curricular, Permissões, Moderação)' : 'Apoio Pedagógico, Moderação, Resolução de Exercícios'}</td>
              <td>
                ${currentUser.role === 'teacher_regent' && t.email !== currentUser.email ? `
                  <button type="button" class="teacher-action-pill-btn danger" onclick="window.approveTeacher('${t.email}', 'student')">
                    Revogar Acesso
                  </button>
                ` : `<span style="color:#71717a; font-size:0.8em;">(Titular)</span>`}
              </td>
            </tr>
          `).join("");
        }
      }
    } catch (e) { /* ignorar */ }

    // 3. Carregar Módulos no Painel Docente
    renderTeacherModulesTable();
  }

  // Acção global de aprovação/alteração de papéis docentes pelo Regente
  window.approveTeacher = async function(email, newRole) {
    if (!confirm(`Confirma a atribuição do perfil de ${newRole === 'teacher_regent' ? 'Docente Regente' : newRole === 'teacher_assistant' ? 'Docente Assistente' : 'Estudante'} a ${email}?`)) return;

    try {
      const resp = await fetch("/api/admin/users/role", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({ target_email: email, new_role: newRole, new_status: "active" })
      });
      const data = await resp.json();
      if (!resp.ok) {
        alert(data.error || "Erro ao actualizar papel.");
        return;
      }
      alert(data.message);
      renderTeacherDashboard();
    } catch (err) {
      alert("Falha ao comunicar com o servidor.");
    }
  };

  // Renderizar Tabela de Módulos Curriculares
  function renderTeacherModulesTable() {
    const tbody = document.getElementById("teacher-modules-tbody");
    if (!tbody) return;

    const modules = window.COURSE_MODULES || {};
    const keys = Object.keys(modules);

    tbody.innerHTML = keys.map(k => {
      const m = modules[k];
      return `
        <tr>
          <td><span style="font-family:monospace; font-weight:600;">${m.identification?.code || 'ENG-IO'}</span></td>
          <td><strong>${escapeHTML(m.title || k)}</strong></td>
          <td>${m.duration || '4h lectivas'}</td>
          <td>${m.level || 'Licenciatura em Engenharia'}</td>
          <td>MongoDB Atlas (Nuvem)</td>
          <td>
            <button type="button" class="teacher-action-pill-btn" onclick="window.openModuleEditor('${k}')">
              Editar na Nuvem
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  // Modal de Edição de Módulos
  const moduleEditorModal = document.getElementById("module-editor-modal");
  const moduleEditorCloseBtn = document.getElementById("module-editor-close-btn");
  const formModuleEditor = document.getElementById("form-module-editor");
  const btnCreateNewModule = document.getElementById("btn-create-new-module");

  if (moduleEditorCloseBtn) moduleEditorCloseBtn.onclick = () => moduleEditorModal.style.display = "none";
  if (btnCreateNewModule) btnCreateNewModule.onclick = () => window.openModuleEditor(null);

  window.openModuleEditor = function(topicKey) {
    if (moduleEditorModal) moduleEditorModal.style.display = "flex";
    if (topicKey && window.COURSE_MODULES && window.COURSE_MODULES[topicKey]) {
      const m = window.COURSE_MODULES[topicKey];
      document.getElementById("mod-edit-title").value = m.title || "";
      document.getElementById("mod-edit-topic").value = topicKey;
      document.getElementById("mod-edit-code").value = m.identification?.code || "ENG-IO-01";
      document.getElementById("mod-edit-duration").value = m.duration || "4h lectivas";
      document.getElementById("mod-edit-intro").value = (m.introduction || "").replace(/<[^>]+>/g, "").trim();
      document.getElementById("mod-edit-theorems").value = (m.theorems || "").replace(/<[^>]+>/g, "").trim();
      document.getElementById("mod-edit-synthesis").value = (m.synthesis || "").replace(/<[^>]+>/g, "").trim();
    } else {
      formModuleEditor.reset();
    }
  };

  if (formModuleEditor) {
    formModuleEditor.addEventListener("submit", async (e) => {
      e.preventDefault();
      const topic_key = document.getElementById("mod-edit-topic").value.trim();
      const title = document.getElementById("mod-edit-title").value.trim();
      const code = document.getElementById("mod-edit-code").value.trim();
      const duration = document.getElementById("mod-edit-duration").value.trim();
      const intro = document.getElementById("mod-edit-intro").value.trim();
      const theorems = document.getElementById("mod-edit-theorems").value.trim();
      const synthesis = document.getElementById("mod-edit-synthesis").value.trim();

      const payload = {
        topic_key,
        title,
        subtitle: `Tópico Curricular Avançado da FE-UEM`,
        duration,
        level: "Licenciatura em Engenharia (FE-UEM)",
        prerequisites: "Álgebra Linear e Investigação Operacional",
        identification: {
          institution: "Faculdade de Engenharia • UEM",
          discipline: "Investigação Operacional",
          code: code,
          workload: duration,
          keywords: [topic_key, "Engenharia", "Optimização"]
        },
        introduction: `<p>${escapeHTML(intro)}</p>`,
        theorems: `<p>${theorems}</p>`,
        synthesis: `<p>${escapeHTML(synthesis)}</p>`
      };

      try {
        const resp = await fetch("/api/modules", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${authToken}`
          },
          body: JSON.stringify(payload)
        });
        if (resp.ok) {
          alert(`Módulo "${title}" persistido no MongoDB Atlas com sucesso!`);
          moduleEditorModal.style.display = "none";
          checkDatabaseAndSyncModules();
          setTimeout(() => renderTeacherModulesTable(), 1000);
        } else {
          alert("Erro ao persistir módulo no MongoDB Atlas.");
        }
      } catch (err) {
        alert("Falha de rede ao persistir módulo.");
      }
    });
  }

  // Ligação directa para Recuperação de Senha no design exemplar
  const linkForgotPassword = document.getElementById("link-forgot-password");
  if (linkForgotPassword) {
    linkForgotPassword.addEventListener("click", (e) => {
      e.preventDefault();
      openAuthModal("tab-recovery");
    });
  }

  // Atalho do Docente para o Fórum
  const dashGoForumBtn = document.getElementById("dash-go-forum-btn");
  if (dashGoForumBtn) {
    dashGoForumBtn.addEventListener("click", () => switchToView("forum"));
  }

  // Botão Limpar
  clearBtn.addEventListener("click", () => {
    if (confirm("Deseja reiniciar a sessão e limpar o histórico de conversação?")) {
      conversationHistory.length = 0;
      const initial = chatMessages.firstElementChild;
      chatMessages.innerHTML = "";
      if (initial) chatMessages.appendChild(initial);
    }
  });

  // Inicializar por omissão na Página Inicial (Home View)
  switchToView("home");
});
