    const chatForm = document.getElementById("chat-form");
    const sessionInput = document.getElementById("session-id");
    const historyPanel = document.getElementById("history-panel");
    const branchFocusPanel = document.getElementById("conversation-branch-header");
    const branchFocusTitle = document.getElementById("branch-focus-title");
    const branchFocusQuestion = document.getElementById("branch-focus-question");
    const branchFocusMeta = document.getElementById("branch-focus-meta");
    const knowledgeOutlinePanel = document.getElementById("knowledge-outline-panel");
    const nodeDetailTitle = document.getElementById("node-detail-title");
    const nodeDetailSummary = document.getElementById("node-detail-summary");
    const nodeDetailBody = document.getElementById("node-detail-body");
    const nodeDetailReferences = document.getElementById("node-detail-references");
    const nodeDetailIncomingReferences = document.getElementById("node-detail-incoming-references");
    const nodeDetailForkAction = document.getElementById("node-detail-fork-action");
    const selectionForkAction = document.getElementById("selection-fork-action");
    const selectionForkHint = document.getElementById("selection-fork-hint");
    const recentSessionsList = document.getElementById("recent-sessions-list");
    const loadSessionButton = document.getElementById("load-session");
    const recentSessions = [];
    let currentSessionId = "";
    let currentReaderNodeId = "";
    let currentBranchContext = null;
    let pendingForkFocusQuestion = "";

    function escapeHtml(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function getNearestPrecedingUserPrompt(messages, messageIndex) {
      const precedingMessages = (messages || []).slice(0, messageIndex).reverse();
      const nearestUserMessage = precedingMessages.find((message) => message.role === "user");
      return nearestUserMessage ? nearestUserMessage.content || "" : "";
    }

    function focusWorkspaceSection(sectionId) {
      document.querySelectorAll("[data-workspace-section]").forEach((section) => {
        section.dataset.active = section.id === sectionId ? "true" : "false";
      });
    }

    function applyWorkspaceHighlight(nodeId) {
      document.querySelectorAll("[data-node-id]").forEach((element) => {
        element.dataset.active = element.dataset.nodeId === nodeId ? "true" : "false";
      });
      document.querySelectorAll("[data-history-session-id]").forEach((element) => {
        element.dataset.active = nodeId && element.dataset.linkedNodeId === nodeId ? "true" : "false";
      });
    }

    function getSelectionText() {
      const activeElement = document.activeElement;
      if (
        activeElement &&
        (activeElement.tagName === "TEXTAREA" || activeElement.tagName === "INPUT")
      ) {
        const start = typeof activeElement.selectionStart === "number" ? activeElement.selectionStart : null;
        const end = typeof activeElement.selectionEnd === "number" ? activeElement.selectionEnd : null;
        if (start !== null && end !== null && end > start) {
          return activeElement.value.slice(start, end).trim();
        }
      }
      return window.getSelection ? window.getSelection().toString().trim() : "";
    }

    function renderSelectionForkState() {
      const selectedText = getSelectionText();
      if (selectionForkHint) {
        selectionForkHint.textContent = selectedText
          ? `Selected text will become the fork focus: ${selectedText}`
          : "Select text in a panel, then fork it as the branch focus.";
      }
      if (selectionForkAction) {
        selectionForkAction.textContent = selectedText ? "Use selected text as fork focus" : "Fork selected text";
      }
    }

    function resolveSelectionForkAnchor() {
      const activeNodeId = nodeDetailForkAction && nodeDetailForkAction.dataset.nodeId
        ? nodeDetailForkAction.dataset.nodeId
        : "";
      if (activeNodeId) {
        return {
          sourceType: "selection",
          nodeId: activeNodeId,
        };
      }
      const answerReference = historyPanel.querySelector("[data-role='assistant'] [data-node-id]");
      if (answerReference && answerReference.dataset.nodeId) {
        return {
          sourceType: "selection",
          nodeId: answerReference.dataset.nodeId,
        };
      }
      const branchActiveNodeId = currentBranchContext && currentBranchContext.active_node_ids
        ? currentBranchContext.active_node_ids[0]
        : "";
      if (branchActiveNodeId) {
        return {
          sourceType: "selection",
          nodeId: branchActiveNodeId,
        };
      }
      return null;
    }

    function loadReaderNode(nodeId) {
      if (!nodeId) {
        return;
      }
      applyWorkspaceHighlight(nodeId);
      currentReaderNodeId = nodeId;
      focusWorkspaceSection("markdown-preview-panel");
      loadNodeDetail(nodeId);
    }

    function resolveForkFocusQuestion(focusQuestionOverride = "") {
      if (focusQuestionOverride) {
        return focusQuestionOverride;
      }
      const sessionFocusQuestion = pendingForkFocusQuestion
        || (currentBranchContext && currentBranchContext.focus_question)
        || "";
      const questionField = document.getElementById("question");
      const typedQuestion = questionField && questionField.value ? questionField.value.trim() : "";
      return sessionFocusQuestion || typedQuestion || "Continue this branch.";
    }

    function renderBranchFocus(branchContext, sessionId = "") {
      const context = branchContext || {};
      currentBranchContext = context;
      if (branchFocusPanel) {
        branchFocusPanel.dataset.sessionId = sessionId || "";
      }
      if (branchFocusTitle) {
        branchFocusTitle.textContent = sessionId ? `Branch ${sessionId}` : "Branch focus";
      }
      if (branchFocusQuestion) {
        branchFocusQuestion.textContent = pendingForkFocusQuestion
          || context.focus_question
          || "No branch focus is set yet.";
      }
      if (branchFocusMeta) {
        const metaParts = [];
        if (context.branch_id) metaParts.push(`branch ${context.branch_id}`);
        if (context.parent_session_id) metaParts.push(`parent ${context.parent_session_id}`);
        if (context.root_session_id) metaParts.push(`root ${context.root_session_id}`);
        if (context.forked_from_node_id) {
          metaParts.push(`node ${context.forked_from_node_id}`);
        } else if (context.forked_from_message_index !== null && context.forked_from_message_index !== undefined) {
          metaParts.push(`message ${context.forked_from_message_index}`);
        }
        if (context.active_node_ids && context.active_node_ids.length) {
          metaParts.push(`active ${context.active_node_ids.length} nodes`);
        }
        if (context.summary_node_ids && context.summary_node_ids.length) {
          metaParts.push(`summary ${context.summary_node_ids.length} nodes`);
        }
        branchFocusMeta.textContent = metaParts.length ? metaParts.join(" · ") : "No branch metadata yet.";
      }
    }

    function renderAnswerCardActions(messageIndex, referencedNodeIds) {
      const canFork = !!(referencedNodeIds && referencedNodeIds.length);
      const actionButtons = [
        `<button type="button" data-history-fork-index="${messageIndex}" ${canFork ? "" : "disabled"}>Fork</button>`,
      ];
      actionButtons.push(`<button type="button" data-copy-answer-index="${messageIndex}">Copy</button>`);
      actionButtons.push(`<button type="button" data-regenerate-answer-index="${messageIndex}">Regenerate</button>`);
      return `<div class="conversation-card-actions">${actionButtons.join("")}</div>`;
    }

    async function forkCurrentSession({
      sourceType,
      nodeId = "",
      messageIndex = null,
      focusQuestionOverride = "",
    }) {
      const session_id = currentSessionId || sessionInput.value.trim();
      if (!session_id) {
        return;
      }
      const focus_question = resolveForkFocusQuestion(focusQuestionOverride);
      const body = { focus_question };
      if (sourceType === "node") {
        if (!nodeId) return;
        body.forked_from_node_id = nodeId;
      } else if (sourceType === "selection") {
        if (!nodeId) return;
        body.forked_from_node_id = nodeId;
      } else if (sourceType === "answer-reference") {
        if (!nodeId) return;
        body.forked_from_node_id = nodeId;
      } else if (sourceType === "history-reference") {
        if (messageIndex === null || messageIndex === undefined) return;
        body.forked_from_message_index = messageIndex;
      } else {
        return;
      }

      const response = await fetch(`/api/sessions/${encodeURIComponent(session_id)}/fork`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        if (branchFocusMeta) {
          branchFocusMeta.textContent = "Unable to fork this branch.";
        }
        focusWorkspaceSection("conversation-branch-header");
        return;
      }

      const payload = await response.json();
      currentSessionId = payload.session_id || "";
      currentBranchContext = payload.branch_context || null;
      if (currentSessionId) {
        sessionInput.value = currentSessionId;
      }
      renderBranchFocus(currentBranchContext, currentSessionId);
      await loadSession();
      focusWorkspaceSection("conversation-branch-header");
    }

    async function copyTextToClipboard(text) {
      const value = text || "";
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(value);
        return;
      }
      const fallback = document.createElement("textarea");
      fallback.value = value;
      fallback.setAttribute("readonly", "readonly");
      fallback.style.position = "absolute";
      fallback.style.left = "-9999px";
      document.body.appendChild(fallback);
      fallback.select();
      document.execCommand("copy");
      document.body.removeChild(fallback);
    }

    async function regenerateMessage(messages, messageIndex) {
      const nearestUserPrompt = getNearestPrecedingUserPrompt(messages, messageIndex);
      if (!nearestUserPrompt) {
        return;
      }
      const questionField = document.getElementById("question");
      if (questionField) {
        questionField.value = nearestUserPrompt;
      }
      await submitQuestion(nearestUserPrompt);
    }

    function renderConversationMessages(messages, sessionId = "") {
      historyPanel.innerHTML = "";
      messages.forEach((message, index) => {
        const referencedNodeIds = (message.assistant_context && message.assistant_context.referenced_node_ids) || [];
        const item = document.createElement("div");
        item.className = "history-item";
        item.dataset.role = message.role || "";
        item.dataset.historySessionId = sessionId;
        item.dataset.historyIndex = String(index);
        if (referencedNodeIds.length) {
          item.dataset.linkedNodeId = referencedNodeIds[0];
        }
        const referenceLinks = referencedNodeIds.length
          ? `<div class="conversation-card-references">${referencedNodeIds.map((nodeId) => `<a href="#" class="reference-link" data-node-id="${escapeHtml(nodeId)}">${escapeHtml(nodeId)}</a>`).join("")}</div>`
          : "";
        const actionMarkup = message.role === "assistant"
          ? renderAnswerCardActions(index, referencedNodeIds)
          : "";
        item.innerHTML = `<div class="history-role">${escapeHtml(message.role)}</div><div class="conversation-card-content">${escapeHtml(message.content)}</div>${referenceLinks}${actionMarkup}`;
        item.addEventListener("click", () => {
          focusWorkspaceSection("history-panel");
        });
        item.querySelectorAll(".reference-link").forEach((link) => {
          link.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            const nodeId = link.dataset.nodeId || "";
            if (!nodeId) {
              return;
            }
            loadReaderNode(nodeId);
          });
        });
        const forkButton = item.querySelector("[data-history-fork-index]");
        if (forkButton) {
          forkButton.addEventListener("click", (event) => {
            event.stopPropagation();
            if (forkButton.disabled || !referencedNodeIds.length) {
              return;
            }
            forkCurrentSession({
              sourceType: "history-reference",
              messageIndex: index,
              focusQuestionOverride: getSelectionText(),
            });
          });
        }
        const copyButton = item.querySelector("[data-copy-answer-index]");
        if (copyButton) {
          copyButton.addEventListener("click", async (event) => {
            event.stopPropagation();
            await copyTextToClipboard(message.content || "");
          });
        }
        const regenerateButton = item.querySelector("[data-regenerate-answer-index]");
        if (regenerateButton) {
          regenerateButton.addEventListener("click", async (event) => {
            event.stopPropagation();
            await regenerateMessage(messages, index);
          });
        }
        historyPanel.appendChild(item);
      });
      const latestAssistantMessage = [...messages].reverse().find((message) => message.role === "assistant");
      const referencedNodeIds = latestAssistantMessage && latestAssistantMessage.assistant_context
        ? latestAssistantMessage.assistant_context.referenced_node_ids || []
        : [];
      applyWorkspaceHighlight(referencedNodeIds[0] || "");
    }

    function rememberSession(sessionId, providerType) {
      if (!sessionId) {
        return;
      }
      const existingIndex = recentSessions.findIndex((entry) => entry.session_id === sessionId);
      const entry = { session_id: sessionId, provider_type: providerType || null };
      if (existingIndex >= 0) {
        recentSessions.splice(existingIndex, 1);
      }
      recentSessions.unshift(entry);
      recentSessions.splice(5);
      renderRecentSessions();
    }

    function buildRecentSessionsTree(sessions) {
      const sessionsById = new Map();
      const childIdsByParent = new Map();
      sessions.forEach((session) => {
        sessionsById.set(session.session_id, { ...session });
      });
      sessions.forEach((session) => {
        const parentId = session.branch_context && session.branch_context.parent_session_id
          ? session.branch_context.parent_session_id
          : "";
        if (!parentId) {
          return;
        }
        if (!childIdsByParent.has(parentId)) {
          childIdsByParent.set(parentId, []);
        }
        childIdsByParent.get(parentId).push(session.session_id);
      });

      const depthCache = new Map();
      const resolveDepth = (sessionId) => {
        if (depthCache.has(sessionId)) {
          return depthCache.get(sessionId);
        }
        const session = sessionsById.get(sessionId);
        if (!session) {
          depthCache.set(sessionId, 0);
          return 0;
        }
        const parentId = session.branch_context && session.branch_context.parent_session_id
          ? session.branch_context.parent_session_id
          : "";
        const depth = parentId && sessionsById.has(parentId) ? resolveDepth(parentId) + 1 : 0;
        depthCache.set(sessionId, depth);
        return depth;
      };

      const normalizedSessions = sessions.map((session) => ({
        ...session,
        branch_depth:
          typeof session.branch_depth === "number" ? session.branch_depth : resolveDepth(session.session_id),
        child_session_ids: Array.isArray(session.child_session_ids)
          ? session.child_session_ids
          : childIdsByParent.get(session.session_id) || [],
      }));
      const normalizedById = new Map(
        normalizedSessions.map((session) => [session.session_id, session])
      );
      const orderedSessions = [];
      const visitedSessionIds = new Set();

      function appendRecentSessionBranch(sessionId) {
        if (visitedSessionIds.has(sessionId)) {
          return;
        }
        const session = normalizedById.get(sessionId);
        if (!session) {
          return;
        }
        visitedSessionIds.add(sessionId);
        orderedSessions.push(session);
        const childIds = session.child_session_ids || [];
        childIds.forEach((childSessionId) => appendRecentSessionBranch(childSessionId));
      }

      normalizedSessions
        .filter((session) => {
          const parentSessionId = session.branch_context && session.branch_context.parent_session_id
            ? session.branch_context.parent_session_id
            : "";
          return !parentSessionId || !normalizedById.has(parentSessionId);
        })
        .forEach((session) => appendRecentSessionBranch(session.session_id));

      normalizedSessions.forEach((session) => appendRecentSessionBranch(session.session_id));
      return orderedSessions;
    }

    function renderRecentSessions() {
      recentSessionsList.innerHTML = "";
      if (!recentSessions.length) {
        recentSessionsList.innerHTML = "<div class='panel-item'>No recent sessions yet.</div>";
        return;
      }
      const tree = document.createElement("div");
      tree.className = "recent-session-tree";
      buildRecentSessionsTree(recentSessions).forEach((session) => {
        const item = document.createElement("div");
        item.className = "recent-session-item";
        item.dataset.depth = String(session.branch_depth || 0);
        item.dataset.childSessionIds = (session.child_session_ids || []).join(",");
        item.style.marginLeft = `${(typeof session.branch_depth === "number" ? session.branch_depth : 0) * 12}px`;
        const providerType = session.provider_profile && session.provider_profile.provider_type
          ? session.provider_profile.provider_type
          : session.provider_type || "saved provider";
        const messageCount = typeof session.message_count === "number" ? session.message_count : 0;
        const lastMessage = session.last_message && session.last_message.content
          ? session.last_message.content
          : "No message preview";
        const branchDepth = typeof session.branch_depth === "number" ? session.branch_depth : 0;
        const childSessionIds = session.child_session_ids || [];
        item.innerHTML = `
          <button type="button" class="recent-session-button" data-session-id="${session.session_id}" data-provider-type="${providerType}">
            <div class="history-role">session</div>
            <div><strong>${session.session_id}</strong></div>
            <div class="recent-session-meta">
              <span class="recent-session-chip">branch depth ${branchDepth}</span>
              <span class="recent-session-chip">${providerType}</span>
              <span class="recent-session-chip">${messageCount} messages</span>
            </div>
            <div class="recent-session-children">children ${childSessionIds.length ? childSessionIds.join(", ") : "none"}</div>
          <div>${lastMessage}</div>
          </button>`;
        item.querySelector("button").addEventListener("click", () => switchRecentSession(session.session_id));
        tree.appendChild(item);
      });
      recentSessionsList.appendChild(tree);
    }

    function switchRecentSession(sessionId) {
      sessionInput.value = sessionId;
      pendingForkFocusQuestion = "";
      renderSelectionForkState();
      loadSession();
    }

    function renderBookOutline(nodes) {
      knowledgeOutlinePanel.innerHTML = "";
      nodes.forEach((node) => {
        const item = document.createElement("div");
        item.className = "panel-item";
        item.dataset.nodeId = node.id;
        item.innerHTML = `<button type="button" class="outline-item" data-node-id="${node.id}"><div class="history-role">${node.type}</div><div><strong>${node.title}</strong></div><div>${node.summary}</div></button>`;
        item.addEventListener("click", () => loadReaderNode(node.id));
        knowledgeOutlinePanel.appendChild(item);
      });
    }

    const renderOutline = renderBookOutline;

    function renderMarkdownFragment(line) {
      const escapedLine = escapeHtml(line);
      const headingMatch = /^(#{1,3})\s+(.*)$/.exec(escapedLine);
      if (headingMatch) {
        const level = Math.min(headingMatch[1].length + 1, 4);
        return `<h${level}>${headingMatch[2]}</h${level}>`;
      }
      const orderedMatch = /^(\d+)\.\s+(.*)$/.exec(escapedLine);
      if (orderedMatch) {
        return `<ol><li>${orderedMatch[2]}</li></ol>`;
      }
      const bulletMatch = /^[-*]\s+(.*)$/.exec(escapedLine);
      if (bulletMatch) {
        return `<ul><li>${bulletMatch[1]}</li></ul>`;
      }
      return `<p>${escapedLine}</p>`;
    }

    function renderMarkdownPreview(node) {
      nodeDetailTitle.textContent = node.title || "Markdown preview";
      nodeDetailSummary.textContent = node.summary || "Select a knowledge node to read its detail here.";
      const bodyLines = String(node.detail || "")
        .split(/\n{2,}/)
        .map((line) => line.trim())
        .filter(Boolean);
      const bodyMarkup = bodyLines.length
        ? bodyLines.map((line) => renderMarkdownFragment(line)).join("")
        : "<p class='reader-empty'>No markdown content available for this node.</p>";
      nodeDetailBody.innerHTML = `
        <article class="markdown-reader-surface">
          <div class="history-role">${escapeHtml(node.type || "node")}</div>
          ${bodyMarkup}
        </article>
      `;
    }

    function renderRelatedChats(relatedSessionIds) {
      nodeDetailReferences.innerHTML = "";
      const entries = relatedSessionIds || [];
      if (!entries.length) {
        nodeDetailReferences.innerHTML = "<div class='panel-item reader-muted'>No related chats yet.</div>";
        return;
      }
      entries.forEach((sessionId) => {
        const item = document.createElement("div");
        item.className = "panel-item";
        item.innerHTML = `
          <button type="button" class="outline-item related-session-link" data-related-session-id="${sessionId}">
            <div class="history-role">related chat</div>
            <div><strong>${sessionId}</strong></div>
          </button>
        `;
        item.querySelector("button").addEventListener("click", () => switchRecentSession(sessionId));
        nodeDetailReferences.appendChild(item);
      });
    }

    function renderReaderContext(node) {
      nodeDetailIncomingReferences.innerHTML = "";
      const referenceCount = Array.isArray(node.references) ? node.references.length : 0;
      const incomingReferenceCount = Array.isArray(node.incoming_references) ? node.incoming_references.length : 0;
      const metadata = document.createElement("div");
      metadata.className = "panel-item reader-muted";
      metadata.innerHTML = `
        <div class="history-role">reader context</div>
        <div>${referenceCount} outgoing references</div>
        <div>${incomingReferenceCount} incoming references</div>
        <div>${node.id || "No node id selected"}</div>
      `;
      nodeDetailIncomingReferences.appendChild(metadata);
    }

    function renderNodeDetail(node) {
      currentReaderNodeId = node.id || currentReaderNodeId;
      cacheNodeSymbolSnapshot(node.id, node.symbols || {}, node.title || node.id || "");
      renderMarkdownPreview(node);
      renderRelatedChats(node.related_session_ids || []);
      renderReaderContext(node);
      if (nodeDetailForkAction) {
        nodeDetailForkAction.disabled = !node.id;
        nodeDetailForkAction.dataset.nodeId = node.id || "";
        nodeDetailForkAction.textContent = node.id ? "Fork current node" : "Fork node";
        nodeDetailForkAction.onclick = () => {
          if (!node.id) {
            return;
          }
          forkCurrentSession({
            sourceType: "node",
            nodeId: node.id,
            focusQuestionOverride: getSelectionText(),
          });
        };
      } else if (node.id) {
        const fallbackForkAction = document.createElement("button");
        fallbackForkAction.type = "button";
        fallbackForkAction.className = "history-role";
        fallbackForkAction.textContent = "Fork current node";
        fallbackForkAction.addEventListener("click", () => {
          forkCurrentSession({
            sourceType: "node",
            nodeId: node.id,
            focusQuestionOverride: getSelectionText(),
          });
        });
        nodeDetailBody.appendChild(fallbackForkAction);
      }
    }

    function renderNodeReferences(references) {
      nodeDetailReferences.innerHTML = "";
      const entries = references || [];
      if (!entries.length) {
        nodeDetailReferences.innerHTML = "<div class='panel-item'>No node references.</div>";
        return;
      }
      entries.forEach((reference) => {
        const item = document.createElement("div");
        item.className = "panel-item";
        item.dataset.nodeId = reference.node_id;
        item.innerHTML = `<button type="button" class="outline-item" data-node-id="${reference.node_id}"><div class="history-role">reference</div><div><strong>${reference.node_id}</strong></div><div>${reference.reason || ""}</div></button>`;
        item.addEventListener("click", () => loadReaderNode(reference.node_id));
        nodeDetailReferences.appendChild(item);
      });
    }

    function renderIncomingNodeReferences(references) {
      nodeDetailIncomingReferences.innerHTML = "";
      const entries = references || [];
      if (!entries.length) {
        nodeDetailIncomingReferences.innerHTML = "<div class='panel-item'>No incoming references.</div>";
        return;
      }
      entries.forEach((reference) => {
        const item = document.createElement("div");
        item.className = "panel-item";
        item.dataset.nodeId = reference.node_id;
        item.innerHTML = `<button type="button" class="outline-item" data-node-id="${reference.node_id}"><div class="history-role">reference</div><div><strong>${reference.node_id}</strong></div><div>${reference.reason || ""}</div></button>`;
        item.addEventListener("click", () => loadReaderNode(reference.node_id));
        nodeDetailIncomingReferences.appendChild(item);
      });
    }

    async function loadRecentSessions() {
      const response = await fetch("/api/sessions");
      if (!response.ok) {
        recentSessions.length = 0;
        renderRecentSessions();
        return;
      }
      const payload = await response.json();
      recentSessions.length = 0;
      recentSessions.push(...(payload.sessions || []));
      renderRecentSessions();
    }

    async function loadOutline() {
      const response = await fetch("/api/outline");
      if (!response.ok) {
        knowledgeOutlinePanel.innerHTML = "<div class='panel-item'>Outline unavailable.</div>";
        return;
      }
      const payload = await response.json();
      renderBookOutline(payload.nodes || []);
    }

    async function loadSession() {
      const sessionId = sessionInput.value.trim();
      if (!sessionId) return;
      const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
      if (!response.ok) {
        historyPanel.innerHTML = "<div class='history-item'>Session not found.</div>";
        return;
      }
      const payload = await response.json();
      currentSessionId = payload.session_id || sessionId;
      currentBranchContext = payload.branch_context || null;
      pendingForkFocusQuestion = "";
      renderBranchFocus(currentBranchContext, currentSessionId);
      renderConversationMessages(payload.messages || [], currentSessionId);
      rememberSession(currentSessionId, payload.provider_profile && payload.provider_profile.provider_type);
      loadRecentSessions();
      focusWorkspaceSection("history-panel");
    }

    async function loadNodeDetail(nodeId) {
      const response = await fetch(`/api/nodes/${encodeURIComponent(nodeId)}`);
      if (currentReaderNodeId !== nodeId) {
        return;
      }
      if (!response.ok) {
        currentReaderNodeId = "";
        nodeDetailTitle.textContent = "Node not found";
        nodeDetailSummary.textContent = "";
        nodeDetailBody.innerHTML = "<div class='panel-item'>Unable to load node detail.</div>";
        nodeDetailReferences.innerHTML = "<div class='panel-item reader-muted'>No related chats yet.</div>";
        nodeDetailIncomingReferences.innerHTML = "";
        if (nodeDetailForkAction) {
          nodeDetailForkAction.disabled = true;
          nodeDetailForkAction.dataset.nodeId = "";
          nodeDetailForkAction.textContent = "Fork current node";
          nodeDetailForkAction.onclick = null;
        }
        return;
      }
      const payload = await response.json();
      if (currentReaderNodeId !== nodeId) {
        return;
      }
      renderNodeDetail(payload.node || {});
    }

    chatForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const session_id = sessionInput.value.trim();
      const question = document.getElementById("question").value.trim();
      const provider_type = document.getElementById("provider-type").value;
      const provider_model = document.getElementById("provider-model").value.trim();
      const credential_id = document.getElementById("credential-id").value.trim();
      await submitQuestion(question, {
        session_id,
        provider_type,
        provider_model,
        credential_id,
      });
    });

    async function submitQuestion(question, options = {}) {
      const session_id = options.session_id !== undefined ? options.session_id : sessionInput.value.trim();
      const provider_type = options.provider_type !== undefined
        ? options.provider_type
        : document.getElementById("provider-type").value;
      const provider_model = options.provider_model !== undefined
        ? options.provider_model
        : document.getElementById("provider-model").value.trim();
      const credential_id = options.credential_id !== undefined
        ? options.credential_id
        : document.getElementById("credential-id").value.trim();
      const body = { session_id, question };
      if (provider_type && provider_model && credential_id) {
        body.provider_profile = {
          provider_type,
          model: provider_model,
          credential_id,
        };
      }
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      currentSessionId = (payload.session && payload.session.session_id) || session_id;
      currentBranchContext = (payload.session && payload.session.branch_context) || null;
      renderBranchFocus(currentBranchContext, currentSessionId);
      loadOutline();
      loadRecentSessions();
      rememberSession(currentSessionId, payload.session.provider_profile && payload.session.provider_profile.provider_type);
      if (payload.session.session_id) {
        sessionInput.value = payload.session.session_id;
        await loadSession();
      } else {
        renderConversationMessages([
          { role: "user", content: question },
          {
            role: "assistant",
            content: payload.answer.assistant_text || payload.answer.detail || "",
            assistant_context: {
              referenced_node_ids: payload.answer.references || [],
            },
          },
        ], currentSessionId);
      }
      focusWorkspaceSection("history-panel");
    }

    loadSessionButton.addEventListener("click", loadSession);
    if (selectionForkAction) {
      selectionForkAction.addEventListener("click", () => {
        const selectedText = getSelectionText();
        if (!selectedText) {
          renderSelectionForkState();
          focusWorkspaceSection("conversation-branch-header");
          return;
        }
        const forkAnchor = resolveSelectionForkAnchor();
        pendingForkFocusQuestion = selectedText;
        renderBranchFocus(currentBranchContext, currentSessionId);
        renderSelectionForkState();
        if (!forkAnchor) {
          if (branchFocusMeta) {
            branchFocusMeta.textContent = "Select a node or reference before forking selected text.";
          }
          focusWorkspaceSection("conversation-branch-header");
          return;
        }
        forkCurrentSession({
          sourceType: "selection",
          nodeId: forkAnchor.nodeId,
          focusQuestionOverride: selectedText,
        });
      });
    }
    document.addEventListener("selectionchange", renderSelectionForkState);
    loadOutline();
    loadRecentSessions();
    renderMarkdownPreview({});
    renderRelatedChats([]);
    renderConversationMessages([]);
    renderBranchFocus(null, "");
    renderSelectionForkState();
    renderRecentSessions();
