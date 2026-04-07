const state = {
    clients: [],
    selectedClientIds: new Set(),
    templates: {
        command: [],
        window: []
    },
    serverConfig: null,
    serverFilter: null,
    tasks: [],
    selectedTaskId: null,
    taskDetail: null,
    taskNotice: {
        level: "info",
        message: "页面已就绪。可以先保存配置、上传 XLSX，或直接发起场控任务。"
    },
    taskPollHandle: null,
    taskDetailRequestId: 0,
    isPolling: false,
    confirmResolver: null,
    taskSubmittedTaskId: null
};

function el(id) {
    return document.getElementById(id);
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function selectedIds() {
    if (document.querySelector(".client-selector")) {
        state.selectedClientIds = new Set(
            Array.from(document.querySelectorAll(".client-selector:checked")).map((item) => item.value)
        );
    }
    return Array.from(state.selectedClientIds);
}

function syncSelectionState() {
    state.selectedClientIds = new Set(selectedIds());
}

function updateSelectionSummary() {
    const count = selectedIds().length;
    el("selection-summary").textContent = count > 0
        ? `当前已选择 ${count} 名考生`
        : "当前未选择，默认操作全部名单";
}

function updateMasterCheckbox() {
    const checkboxes = Array.from(document.querySelectorAll(".client-selector"));
    if (!checkboxes.length) {
        el("master-checkbox").checked = false;
        el("master-checkbox").indeterminate = false;
        return;
    }
    const checkedCount = checkboxes.filter((item) => item.checked).length;
    el("master-checkbox").checked = checkedCount === checkboxes.length;
    el("master-checkbox").indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
}

function statusPill(status) {
    if (!status) {
        return `<span class="status-pill status-empty">未执行</span>`;
    }
    if (status === "success") {
        return `<span class="status-pill status-success">Success</span>`;
    }
    return `<span class="status-pill status-error">${escapeHtml(status)}</span>`;
}

function taskStatusPill(status) {
    const labels = {
        queued: "排队中",
        running: "执行中",
        completed: "已完成",
        error: "失败"
    };
    const className = status ? `task-status-${status}` : "task-status-queued";
    return `<span class="status-pill task-status-pill ${className}">${escapeHtml(labels[status] || status || "未知")}</span>`;
}

function renderInlineMarkdown(text) {
    return escapeHtml(text)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function normalizeMarkdown(markdown) {
    return String(markdown || "")
        .replace(/\r\n/g, "\n")
        .replace(/^(#{1,6})([^\s#])/gm, "$1 $2");
}

function markdownToHtml(markdown) {
    const lines = normalizeMarkdown(markdown).split("\n");
    const html = [];
    let inCodeBlock = false;
    let codeLines = [];
    let listType = null;
    let paragraph = [];

    function flushParagraph() {
        if (!paragraph.length) {
            return;
        }
        html.push(`<p>${renderInlineMarkdown(paragraph.join("<br>"))}</p>`);
        paragraph = [];
    }

    function closeList() {
        if (!listType) {
            return;
        }
        html.push(listType === "ol" ? "</ol>" : "</ul>");
        listType = null;
    }

    function flushCodeBlock() {
        if (!inCodeBlock) {
            return;
        }
        html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        inCodeBlock = false;
        codeLines = [];
    }

    for (const rawLine of lines) {
        const line = rawLine ?? "";
        const trimmed = line.trim();

        if (trimmed.startsWith("```")) {
            flushParagraph();
            closeList();
            if (inCodeBlock) {
                flushCodeBlock();
            } else {
                inCodeBlock = true;
            }
            continue;
        }

        if (inCodeBlock) {
            codeLines.push(line);
            continue;
        }

        if (!trimmed) {
            flushParagraph();
            closeList();
            continue;
        }

        const headingMatch = trimmed.match(/^(#{1,4})\s+(.*)$/);
        if (headingMatch) {
            flushParagraph();
            closeList();
            const level = headingMatch[1].length;
            html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
            continue;
        }

        const orderedMatch = trimmed.match(/^\d+\.\s+(.*)$/);
        if (orderedMatch) {
            flushParagraph();
            if (listType && listType !== "ol") {
                closeList();
            }
            if (!listType) {
                listType = "ol";
                html.push("<ol>");
            }
            html.push(`<li>${renderInlineMarkdown(orderedMatch[1])}</li>`);
            continue;
        }

        const unorderedMatch = trimmed.match(/^[-*]\s+(.*)$/);
        if (unorderedMatch) {
            flushParagraph();
            if (listType && listType !== "ul") {
                closeList();
            }
            if (!listType) {
                listType = "ul";
                html.push("<ul>");
            }
            html.push(`<li>${renderInlineMarkdown(unorderedMatch[1])}</li>`);
            continue;
        }

        if (listType) {
            closeList();
        }
        paragraph.push(trimmed);
    }

    flushParagraph();
    closeList();
    flushCodeBlock();
    return html.join("");
}

function prettyLabel(key) {
    const labels = {
        _client_id: "Client ID",
        client_id: "Client ID",
        user_name: "姓名",
        user_id: "准考证号",
        user_room: "考场",
        user_no: "机位",
        user_ip: "IP",
        group_id: "组别",
        exam_id: "考试编号",
        ping_status: "Ping",
        connect_status: "Connect",
        connect_message: "说明",
        status: "状态",
        mesg: "消息",
        command_id: "Command ID",
        window_id: "Window ID",
        note: "备注",
        command: "命令内容",
        window_title: "窗口标题",
        window_content: "窗口内容",
        front_size: "字号",
        pid: "PID",
        saved_path: "保存路径",
        action: "操作",
        success: "成功",
        fail: "失败",
        total: "总数",
        available: "可达",
        loss: "不可达",
        mapped_count: "已绑定",
        available_ip_count: "可用 IP",
        bind_by: "绑定依据"
    };
    return labels[key] || key;
}

function normalizeRows(items) {
    return items.map((item) => {
        if (item && typeof item === "object" && item.client && item.result) {
            return {
                ...item.client,
                status: item.result.status ?? "",
                mesg: item.result.mesg ?? "",
                command_id: item.result.command_id ?? "",
                pid: item.result.pid ?? ""
            };
        }
        return item;
    });
}

function collectColumns(rows) {
    const preferredOrder = [
        "_client_id",
        "client_id",
        "user_name",
        "user_id",
        "user_room",
        "user_no",
        "user_ip",
        "group_id",
        "exam_id",
        "ping_status",
        "connect_status",
        "connect_message",
        "status",
        "mesg",
        "command_id",
        "pid",
        "saved_path"
    ];
    const keys = new Set();
    rows.forEach((row) => {
        if (row && typeof row === "object") {
            Object.keys(row).forEach((key) => keys.add(key));
        }
    });
    return preferredOrder.filter((key) => keys.has(key)).concat(
        Array.from(keys).filter((key) => !preferredOrder.includes(key))
    );
}

function renderCell(key, value) {
    if (key === "status" || key === "ping_status" || key === "connect_status") {
        return statusPill(value);
    }
    if (value === null || value === undefined || value === "") {
        return '<span class="status-pill status-empty">空</span>';
    }
    if (typeof value === "object") {
        return `<code>${escapeHtml(JSON.stringify(value))}</code>`;
    }
    return escapeHtml(value);
}

function renderResultTable(title, items) {
    const rows = normalizeRows(items);
    if (!rows.length) {
        return `
            <section class="result-section">
                <h3>${escapeHtml(title)}</h3>
                <div class="result-empty">暂无数据。</div>
            </section>
        `;
    }
    const columns = collectColumns(rows);
    return `
        <section class="result-section">
            <h3>${escapeHtml(title)}</h3>
            <div class="result-table-wrap">
                <table class="result-table">
                    <thead>
                        <tr>${columns.map((column) => `<th>${escapeHtml(prettyLabel(column))}</th>`).join("")}</tr>
                    </thead>
                    <tbody>
                        ${rows.map((row) => `
                            <tr>${columns.map((column) => `<td>${renderCell(column, row[column])}</td>`).join("")}</tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        </section>
    `;
}

function renderSummary(summary) {
    if (!summary || typeof summary !== "object") {
        return "";
    }
    return `
        <section class="result-section">
            <h3>摘要</h3>
            <div class="result-summary-grid">
                ${Object.entries(summary).map(([key, value]) => `
                    <div class="result-summary-card">
                        <strong>${escapeHtml(prettyLabel(key))}</strong>
                        <span>${escapeHtml(value)}</span>
                    </div>
                `).join("")}
            </div>
        </section>
    `;
}

function renderResultContent(value) {
    if (typeof value === "string") {
        return `<section class="result-section"><h3>返回结果</h3><div class="result-text">${escapeHtml(value)}</div></section>`;
    }

    if (Array.isArray(value)) {
        return renderResultTable("返回结果", value);
    }

    if (value && typeof value === "object") {
        const sections = [];
        if (value.summary) {
            sections.push(renderSummary(value.summary));
        }
        if (Array.isArray(value.results)) {
            sections.push(renderResultTable("执行明细", value.results));
        }
        if (Array.isArray(value.clients)) {
            sections.push(renderResultTable("当前名单", value.clients));
        }
        if (Array.isArray(value.ping_scan)) {
            sections.push(renderResultTable("Ping 明细", value.ping_scan));
        }
        if (value.saved_path) {
            sections.push(renderSummary({ saved_path: value.saved_path }));
        }
        if (sections.length) {
            return sections.join("");
        }
    }

    return `<section class="result-section"><h3>返回结果</h3><div class="result-text">${escapeHtml(JSON.stringify(value, null, 2))}</div></section>`;
}

function formatDateTime(value) {
    if (!value) {
        return "未开始";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }
    return date.toLocaleString("zh-CN", { hour12: false });
}

function progressText(progress) {
    const completed = Number(progress?.completed || 0);
    const total = Number(progress?.total || 0);
    return `${completed}/${total}`;
}

function progressPercent(progress) {
    const completed = Number(progress?.completed || 0);
    const total = Number(progress?.total || 0);
    if (total <= 0) {
        return completed > 0 ? 100 : 0;
    }
    return Math.max(0, Math.min(100, (completed / total) * 100));
}

function summarizeTaskResult(task) {
    if (!task?.result_summary || typeof task.result_summary !== "object") {
        return "";
    }
    return Object.entries(task.result_summary)
        .slice(0, 3)
        .map(([key, value]) => `${prettyLabel(key)} ${value}`)
        .join(" · ");
}

function taskCountSummary(task) {
    const summary = task?.result_summary || task?.result?.summary;
    if (!summary || typeof summary !== "object") {
        return null;
    }
    const success = Number(summary.success ?? summary.available);
    const fail = Number(summary.fail ?? summary.loss);
    if (Number.isNaN(success) && Number.isNaN(fail)) {
        return null;
    }
    return {
        success: Number.isNaN(success) ? null : success,
        fail: Number.isNaN(fail) ? null : fail
    };
}

function renderTaskCountTags(task) {
    const counts = taskCountSummary(task);
    if (!counts) {
        return "";
    }
    const tags = [];
    if (counts.success !== null) {
        tags.push(`<span class="task-count-tag task-count-success">成功 ${escapeHtml(counts.success)}</span>`);
    }
    if (counts.fail !== null) {
        tags.push(`<span class="task-count-tag task-count-fail">失败 ${escapeHtml(counts.fail)}</span>`);
    }
    return tags.join("");
}

function taskMeta(task) {
    return task?.meta && typeof task.meta === "object" ? task.meta : {};
}

function setTaskNotice(message, level = "info") {
    state.taskNotice = message ? { message, level } : null;
    renderTaskDetail();
}

function clearTaskNotice() {
    state.taskNotice = null;
    renderTaskDetail();
}

function selectionScopeText(selectedIdsInput) {
    const selected = Array.isArray(selectedIdsInput) ? selectedIdsInput : [];
    if (!selected.length) {
        return `当前未单独选择考生，将对筛选后的全部 ${state.clients.length} 台名单生效。`;
    }
    return `本次将对已选择的 ${selected.length} 名考生生效。`;
}

function applyConfig(config) {
    state.serverConfig = config || {};
    const titles = config.CLIENT_EXCEL_TITLE || {};
    el("room-id").value = config.ROOM_ID || "";
    el("ip-range").value = config.IP_RANGE || "";
    el("local-ip").value = config.LOCAL_IP || "";
    el("client-excel-path").value = config.CLIENT_EXCEL_PATH || "./client.xlsx";
    el("title-user-id").value = titles.user_id || "";
    el("title-user-name").value = titles.user_name || "";
    el("title-user-room").value = titles.user_room || "";
    el("title-user-no").value = titles.user_no || "";
    el("title-user-ip").value = titles.user_ip || "";
    el("title-group-id").value = titles.group_id || "";
    el("title-exam-id").value = titles.exam_id || "";
}

function applyFilter(filter) {
    state.serverFilter = filter || {};
    el("filter-active").checked = Boolean(filter.active);
    el("filter-ip").value = (filter.ip || {}).reg || "";
    el("filter-user-name").value = (filter.user_name || {}).reg || "";
    el("filter-user-id").value = (filter.user_id || {}).reg || "";
    el("filter-group-id").value = (filter.group_id || {}).reg || "";
}

function renderTemplates(templates) {
    state.templates = {
        command: Array.isArray(templates?.command) ? templates.command : [],
        window: Array.isArray(templates?.window) ? templates.window : []
    };

    const commandSelect = el("command-template-select");
    const commandSelected = commandSelect.value;
    commandSelect.innerHTML = `<option value="">手动输入</option>${state.templates.command.map((item, index) => (
        `<option value="${index}">${escapeHtml(`${index + 1}. ${item.template_name}`)}</option>`
    )).join("")}`;
    if (Array.from(commandSelect.options).some((item) => item.value === commandSelected)) {
        commandSelect.value = commandSelected;
    }

    const windowSelect = el("window-template-select");
    const windowSelected = windowSelect.value;
    windowSelect.innerHTML = `<option value="">手动输入</option>${state.templates.window.map((item, index) => (
        `<option value="${index}">${escapeHtml(`${index + 1}. ${item.template_name}`)}</option>`
    )).join("")}`;
    if (Array.from(windowSelect.options).some((item) => item.value === windowSelected)) {
        windowSelect.value = windowSelected;
    }
}

function applyCommandTemplateSelection() {
    const selected = el("command-template-select").value;
    if (selected === "") {
        return;
    }
    const index = Number(selected);
    const template = state.templates.command[index];
    if (!template) {
        return;
    }
    el("command-id").value = String(index + 1);
    el("command-text").value = template.command || "";
}

function applyWindowTemplateSelection() {
    const selected = el("window-template-select").value;
    if (selected === "") {
        return;
    }
    const index = Number(selected);
    const template = state.templates.window[index];
    if (!template) {
        return;
    }
    el("window-id").value = String(index + 1);
    el("window-title").value = template.title || "";
    el("window-content").value = template.content || "";
    el("window-font-size").value = template.front_size || 16;
}

function renderClients(clients) {
    state.clients = Array.isArray(clients) ? clients : [];
    const body = el("client-table-body");
    if (!state.clients.length) {
        body.innerHTML = `<tr><td colspan="10">当前没有可展示的名单，请先上传或读取 XLSX。</td></tr>`;
        state.selectedClientIds = new Set();
        updateMasterCheckbox();
        updateSelectionSummary();
        return;
    }

    body.innerHTML = state.clients.map((client) => `
        <tr>
            <td><input class="client-selector" type="checkbox" value="${escapeHtml(client._client_id)}" ${state.selectedClientIds.has(String(client._client_id)) ? "checked" : ""}></td>
            <td>${escapeHtml(client.user_name)}</td>
            <td>${escapeHtml(client.user_id)}</td>
            <td>${escapeHtml(client.user_room)}</td>
            <td>${escapeHtml(client.user_no)}</td>
            <td>${escapeHtml(client.user_ip)}</td>
            <td>${escapeHtml(client.group_id)}</td>
            <td>${statusPill(client.ping_status)}</td>
            <td>${statusPill(client.connect_status)}</td>
            <td>${escapeHtml(client.connect_message)}</td>
        </tr>
    `).join("");

    document.querySelectorAll(".client-selector").forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            syncSelectionState();
            updateMasterCheckbox();
            updateSelectionSummary();
        });
    });

    updateMasterCheckbox();
    updateSelectionSummary();
}

function renderPingSummary(pingScan) {
    if (!Array.isArray(pingScan) || !pingScan.length) {
        el("ping-summary").textContent = "尚未执行 Ping。";
        return;
    }
    const success = pingScan.filter((item) => item.status === "success").length;
    const fail = pingScan.length - success;
    el("ping-summary").textContent = `最近一次 Ping: 可达 ${success} 台，不可达 ${fail} 台，总计 ${pingScan.length} 台。`;
}

function renderAuditLogs(auditLogs) {
    const container = el("audit-log-list");
    if (!Array.isArray(auditLogs) || !auditLogs.length) {
        container.innerHTML = `<div class="audit-item">暂无操作记录。</div>`;
        return;
    }
    container.innerHTML = auditLogs.slice().reverse().map((entry) => `
        <div class="audit-item">
            <div><strong>${escapeHtml(entry.action)}</strong><time>${escapeHtml(entry.timestamp)}</time></div>
            <div>${escapeHtml(JSON.stringify(entry.detail))}</div>
        </div>
    `).join("");
}

function ensureSelectedTask(tasks) {
    const taskIds = new Set(tasks.map((item) => item.task_id));
    if (state.selectedTaskId && taskIds.has(state.selectedTaskId)) {
        return;
    }
    state.selectedTaskId = tasks.length ? tasks[0].task_id : null;
    state.taskDetail = null;
}

function renderTaskList(tasks) {
    state.tasks = Array.isArray(tasks) ? tasks : [];
    ensureSelectedTask(state.tasks);

    const runningCount = state.tasks.filter((task) => task.status === "running").length;
    el("task-summary-text").textContent = state.tasks.length
        ? `运行中 ${runningCount}，历史 ${state.tasks.length}`
        : "暂无任务";

    const container = el("task-list");
    if (!state.tasks.length) {
        container.innerHTML = `<div class="task-empty">等待操作...</div>`;
        renderTaskDetail();
        return;
    }

    container.innerHTML = state.tasks.map((task) => `
        <button class="task-item ${task.task_id === state.selectedTaskId ? "is-active" : ""}" type="button" data-task-id="${escapeHtml(task.task_id)}">
            <div class="task-item-head">
                <span class="task-item-title">${escapeHtml(task.title || task.action || task.task_id)}</span>
                ${taskStatusPill(task.status)}
            </div>
            <div class="task-item-meta">
                <span>${escapeHtml(task.action || "")}</span>
                <span class="task-item-time">${escapeHtml(formatDateTime(task.created_at))}</span>
            </div>
            <div class="task-progress-row">
                <span>进度 ${escapeHtml(progressText(task.progress))}</span>
                <span class="task-count-tags">${renderTaskCountTags(task)}</span>
                <span>${escapeHtml(summarizeTaskResult(task))}</span>
            </div>
            <div class="task-progress-bar">
                <div class="task-progress-fill" style="width: ${progressPercent(task.progress)}%"></div>
            </div>
        </button>
    `).join("");

    renderTaskDetail();
}

function renderTaskLogs(task) {
    const logs = Array.isArray(task?.logs) ? task.logs : [];
    if (!logs.length) {
        return `
            <section class="task-detail-section">
                <h3>执行日志</h3>
                <div class="task-empty">当前没有日志。</div>
            </section>
        `;
    }
    return `
        <section class="task-detail-section">
            <h3>执行日志</h3>
            <div class="task-log-list">
                ${logs.map((entry) => `
                    <div class="task-log-entry ${entry.level === "error" ? "is-error" : ""}">
                        <span class="task-log-level">${escapeHtml(entry.level || "info")}</span>
                        <div class="task-log-message">${escapeHtml(entry.message)}</div>
                        <span class="task-log-time">${escapeHtml(formatDateTime(entry.timestamp))}</span>
                    </div>
                `).join("")}
            </div>
        </section>
    `;
}

function renderTaskCards(task) {
    const counts = taskCountSummary(task);
    const meta = taskMeta(task);
    const cards = [
        ["状态", task.status || "unknown"],
        ["进度", progressText(task.progress)],
        ["成功", counts?.success ?? "-"],
        ["失败", counts?.fail ?? "-"],
        ["创建时间", formatDateTime(task.created_at)],
        ["开始时间", formatDateTime(task.started_at)],
        ["结束时间", task.ended_at ? formatDateTime(task.ended_at) : "未结束"]
    ];
    if (meta.note) {
        cards.splice(2, 0, ["备注", meta.note]);
    }
    if (meta.command_id !== undefined && meta.command_id !== null && meta.command_id !== "") {
        cards.splice(2, 0, ["Command ID", meta.command_id]);
    }
    if (meta.window_id !== undefined && meta.window_id !== null && meta.window_id !== "") {
        cards.splice(2, 0, ["Window ID", meta.window_id]);
    }
    return `
        <div class="task-detail-grid">
            ${cards.map(([title, value]) => `
                <div class="task-detail-card">
                    <strong>${escapeHtml(title)}</strong>
                    <span>${escapeHtml(value)}</span>
                </div>
            `).join("")}
        </div>
    `;
}

function renderTaskMetaSections(task) {
    const meta = taskMeta(task);
    const sections = [];

    if (meta.note) {
        sections.push(`
            <section class="task-detail-section">
                <h3>操作备注</h3>
                <div class="result-text">${escapeHtml(meta.note)}</div>
            </section>
        `);
    }

    if (meta.command) {
        sections.push(`
            <section class="task-detail-section">
                <h3>执行命令</h3>
                <div class="result-text">${escapeHtml(meta.command)}</div>
            </section>
        `);
    }

    if (meta.window_title || meta.window_content || meta.front_size !== undefined) {
        const windowSummary = {
            window_title: meta.window_title || "",
            front_size: meta.front_size ?? ""
        };
        sections.push(renderSummary(windowSummary));
        if (meta.window_content) {
            sections.push(`
                <section class="task-detail-section">
                    <h3>窗口内容</h3>
                    <div class="result-text">${escapeHtml(meta.window_content)}</div>
                </section>
            `);
        }
    }

    return sections.join("");
}

function renderTaskNotice() {
    if (!state.taskNotice?.message) {
        return "";
    }
    return `<div class="task-notice ${state.taskNotice.level === "error" ? "is-error" : ""}">${escapeHtml(state.taskNotice.message)}</div>`;
}

function renderTaskDetail() {
    const container = el("task-detail");
    const summaryTask = state.tasks.find((item) => item.task_id === state.selectedTaskId) || null;
    const detailTask = state.taskDetail && state.taskDetail.task_id === state.selectedTaskId ? state.taskDetail : null;
    const task = detailTask || summaryTask;

    if (!task) {
        container.innerHTML = `
            <div class="task-detail-body">
                ${renderTaskNotice()}
                <div class="task-empty">当前没有任务，执行 Ping、Connect Check、批量命令或窗口操作后会显示在这里。</div>
            </div>
        `;
        return;
    }

    const metaText = [
        task.action ? `动作: ${task.action}` : "",
        task.task_id ? `任务 ID: ${task.task_id}` : ""
    ].filter(Boolean).join(" | ");

    let bodyHtml = `
        <div class="task-detail-body">
            <div class="task-detail-header">
                <div>
                    <strong>${escapeHtml(task.title || task.action || task.task_id)}</strong>
                    <div class="task-detail-meta">${escapeHtml(metaText)}</div>
                </div>
                ${taskStatusPill(task.status)}
            </div>
            ${renderTaskNotice()}
            ${renderTaskCards(task)}
    `;

    if (task.error) {
        bodyHtml += `
            <section class="task-detail-section">
                <h3>错误信息</h3>
                <div class="result-text">${escapeHtml(task.error)}</div>
            </section>
        `;
    }

    if (detailTask) {
        bodyHtml += renderTaskMetaSections(detailTask);
        bodyHtml += renderTaskLogs(detailTask);
        if (detailTask.result !== null && detailTask.result !== undefined) {
            bodyHtml += renderResultContent(detailTask.result);
        } else {
            bodyHtml += `
                <section class="task-detail-section">
                    <h3>执行结果</h3>
                    <div class="task-empty">${task.status === "running" || task.status === "queued" ? "任务执行中，结果尚未返回。" : "当前没有结果。"}</div>
                </section>
            `;
        }
    } else {
        bodyHtml += `
            <section class="task-detail-section">
                <h3>执行日志</h3>
                <div class="task-empty">正在加载任务详情...</div>
            </section>
        `;
    }

    bodyHtml += "</div>";
    container.innerHTML = bodyHtml;
}

function isTerminalTaskStatus(status) {
    return status === "completed" || status === "error";
}

function selectedTaskSummary() {
    return state.tasks.find((item) => item.task_id === state.selectedTaskId) || null;
}

function valueOrFallback(value, fallback, preserveEmpty) {
    const normalized = String(value ?? "").trim();
    if (preserveEmpty && normalized === "") {
        return fallback ?? "";
    }
    return normalized;
}

function collectSettingsPayload(options = {}) {
    const { preserveEmptyConfig = false } = options;
    const serverConfig = state.serverConfig || {};
    const serverTitles = serverConfig.CLIENT_EXCEL_TITLE || {};
    return {
        config: {
            ROOM_ID: valueOrFallback(el("room-id").value, serverConfig.ROOM_ID, preserveEmptyConfig),
            IP_RANGE: valueOrFallback(el("ip-range").value, serverConfig.IP_RANGE, preserveEmptyConfig),
            LOCAL_IP: valueOrFallback(el("local-ip").value, serverConfig.LOCAL_IP, preserveEmptyConfig),
            CLIENT_EXCEL_PATH: valueOrFallback(el("client-excel-path").value, serverConfig.CLIENT_EXCEL_PATH, preserveEmptyConfig),
            CLIENT_EXCEL_TITLE: {
                user_id: valueOrFallback(el("title-user-id").value, serverTitles.user_id, preserveEmptyConfig),
                user_name: valueOrFallback(el("title-user-name").value, serverTitles.user_name, preserveEmptyConfig),
                user_room: valueOrFallback(el("title-user-room").value, serverTitles.user_room, preserveEmptyConfig),
                user_no: valueOrFallback(el("title-user-no").value, serverTitles.user_no, preserveEmptyConfig),
                user_ip: valueOrFallback(el("title-user-ip").value, serverTitles.user_ip, preserveEmptyConfig),
                group_id: valueOrFallback(el("title-group-id").value, serverTitles.group_id, preserveEmptyConfig),
                exam_id: valueOrFallback(el("title-exam-id").value, serverTitles.exam_id, preserveEmptyConfig)
            }
        },
        filter: {
            active: el("filter-active").checked,
            ip: { reg: el("filter-ip").value.trim() },
            user_name: { reg: el("filter-user-name").value.trim() },
            user_id: { reg: el("filter-user-id").value.trim() },
            group_id: { reg: el("filter-group-id").value.trim() }
        }
    };
}

async function apiRequest(url, options = {}) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok || payload.status !== "success") {
        throw new Error(payload.mesg || "请求失败");
    }
    return payload.data;
}

function applyStateData(data, options = {}) {
    const { updateForms = true } = options;
    if (updateForms) {
        applyConfig(data.config);
        applyFilter(data.filter);
    }
    renderTemplates(data.templates || { command: [], window: [] });
    renderClients(data.clients || []);
    renderPingSummary(data.ping_scan || []);
    renderAuditLogs(data.audit_logs || []);
    renderTaskList(data.tasks || []);
}

async function fetchTaskDetail(taskId, silent = false) {
    if (!taskId) {
        state.taskDetail = null;
        renderTaskDetail();
        return null;
    }
    const requestId = ++state.taskDetailRequestId;
    try {
        const data = await apiRequest(`/api/tasks/${taskId}`);
        if (requestId !== state.taskDetailRequestId || taskId !== state.selectedTaskId) {
            return null;
        }
        state.taskDetail = data;
        renderTaskDetail();
        return data;
    } catch (error) {
        if (!silent) {
            setTaskNotice(error.message, "error");
        }
        return null;
    }
}

async function fetchState(options = {}) {
    const {
        updateForms = true,
        refreshTaskDetail = true
    } = options;
    const data = await apiRequest("/api/state");
    applyStateData(data, { updateForms });
    const selectedTask = selectedTaskSummary();
    const detailTask = state.taskDetail && state.taskDetail.task_id === state.selectedTaskId ? state.taskDetail : null;
    const shouldRefreshTerminalTask = selectedTask
        && isTerminalTaskStatus(selectedTask.status)
        && (
            !detailTask
            || detailTask.status !== selectedTask.status
            || (selectedTask.status === "completed" && (detailTask.result === null || detailTask.result === undefined))
            || (selectedTask.status === "error" && !detailTask.error)
        );
    if (
        refreshTaskDetail
        && state.selectedTaskId
        && selectedTask
        && (!isTerminalTaskStatus(selectedTask.status) || shouldRefreshTerminalTask)
    ) {
        await fetchTaskDetail(state.selectedTaskId, true);
    }
}

async function openReadmeModal() {
    const data = await apiRequest("/api/readme");
    const normalizedMarkdown = normalizeMarkdown(data.content || "");
    el("readme-path").textContent = data.path || "";
    if (window.marked && typeof window.marked.parse === "function") {
        el("readme-content").innerHTML = window.marked.parse(normalizedMarkdown);
    } else {
        el("readme-content").innerHTML = markdownToHtml(normalizedMarkdown);
    }
    el("readme-modal").classList.remove("hidden");
}

function closeReadmeModal() {
    el("readme-modal").classList.add("hidden");
}

function showConfirmModal({
    title,
    subtitle = "",
    message,
    confirmText = "确认下发",
    danger = false,
    collectNote = false,
    initialNote = ""
}) {
    const noteField = el("confirm-note-field");
    const noteInput = el("confirm-note-input");
    el("confirm-modal-title").textContent = title || "确认操作";
    el("confirm-modal-subtitle").textContent = subtitle || "";
    el("confirm-modal-message").innerHTML = Array.isArray(message)
        ? message.map((line) => `<p>${escapeHtml(line)}</p>`).join("")
        : `<p>${escapeHtml(message || "")}</p>`;

    const submitButton = el("confirm-submit-btn");
    submitButton.textContent = confirmText;
    submitButton.classList.toggle("danger-button", Boolean(danger));
    if (!danger) {
        submitButton.classList.remove("ghost-button");
    }
    noteField.classList.toggle("hidden", !collectNote);
    noteInput.value = initialNote;

    el("confirm-modal").classList.remove("hidden");

    return new Promise((resolve) => {
        state.confirmResolver = resolve;
    });
}

function closeConfirmModal(confirmed = false) {
    el("confirm-modal").classList.add("hidden");
    const resolver = state.confirmResolver;
    state.confirmResolver = null;
    if (resolver) {
        resolver({
            confirmed: Boolean(confirmed),
            note: el("confirm-note-input").value.trim()
        });
    }
}

function showTaskSubmittedModal(taskSummary, messageLines = []) {
    state.taskSubmittedTaskId = taskSummary?.task_id || null;
    el("task-submitted-subtitle").textContent = taskSummary?.title || taskSummary?.action || "任务已创建";
    el("task-submitted-message").innerHTML = messageLines.map((line) => `<p>${escapeHtml(line)}</p>`).join("");
    el("task-submitted-meta").innerHTML = `
        <div class="task-submitted-row">
            <strong>任务 ID</strong>
            <span>${escapeHtml(taskSummary?.task_id || "")}</span>
        </div>
        <div class="task-submitted-row">
            <strong>状态</strong>
            <span>${escapeHtml(taskSummary?.status || "queued")}</span>
        </div>
        <div class="task-submitted-row">
            <strong>创建时间</strong>
            <span>${escapeHtml(formatDateTime(taskSummary?.created_at))}</span>
        </div>
    `;
    el("task-submitted-modal").classList.remove("hidden");
}

function closeTaskSubmittedModal() {
    el("task-submitted-modal").classList.add("hidden");
}

async function syncSettingsSilently() {
    const data = await apiRequest("/api/settings", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(collectSettingsPayload({ preserveEmptyConfig: true }))
    });
    applyStateData(data, { updateForms: false });
    return data;
}

function mergeTaskSummary(taskSummary) {
    const otherTasks = state.tasks.filter((item) => item.task_id !== taskSummary.task_id);
    state.tasks = [taskSummary, ...otherTasks];
}

async function performStateAction(url, payload, options = {}) {
    const {
        syncSettings = true,
        startMessage = "正在执行操作...",
        successMessage = "操作已完成。",
        updateForms = false
    } = options;

    syncSelectionState();
    setTaskNotice(startMessage, "info");
    try {
        if (syncSettings) {
            await syncSettingsSilently();
        }
        const data = await apiRequest(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload || {})
        });
        applyStateData(data, { updateForms });
        setTaskNotice(successMessage, "info");
    } catch (error) {
        setTaskNotice(error.message, "error");
    }
}

async function startTask(url, payload, options = {}) {
    const {
        syncSettings = true,
        startMessage = "正在创建任务...",
        confirm = null,
        submittedMessage = null
    } = options;

    const selected = Array.isArray(payload?.selected_ids) ? payload.selected_ids : [];
    if (confirm) {
        const confirmPayload = {
            title: confirm.title || "确认下发",
            subtitle: confirm.subtitle || "",
            message: typeof confirm.message === "function"
                ? confirm.message({ selectedIds: selected, payload })
                : (confirm.message || "请确认是否继续执行。"),
            confirmText: confirm.confirmText || "确认下发",
            danger: Boolean(confirm.danger),
            collectNote: Boolean(confirm.collectNote),
            initialNote: confirm.initialNote || ""
        };
        const confirmResult = await showConfirmModal(confirmPayload);
        if (!confirmResult.confirmed) {
            return;
        }
        if (confirm.collectNote) {
            payload = {
                ...(payload || {}),
                note: confirmResult.note
            };
        }
    }

    syncSelectionState();
    setTaskNotice(startMessage, "info");
    try {
        if (syncSettings) {
            await syncSettingsSilently();
        }
        const taskSummary = await apiRequest(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload || {})
        });
        mergeTaskSummary(taskSummary);
        state.selectedTaskId = taskSummary.task_id;
        state.taskDetail = null;
        clearTaskNotice();
        renderTaskList(state.tasks);
        showTaskSubmittedModal(
            taskSummary,
            typeof submittedMessage === "function"
                ? submittedMessage({ taskSummary, selectedIds: selected, payload })
                : (submittedMessage || [
                    "任务已提交到后台执行。",
                    "你可以在执行结果区域切换查看该任务的进度、日志和结果。"
                ])
        );
        await fetchTaskDetail(taskSummary.task_id, true);
        await fetchState({ updateForms: false, refreshTaskDetail: false });
    } catch (error) {
        setTaskNotice(error.message, "error");
    }
}

function selectTask(taskId) {
    if (!taskId || taskId === state.selectedTaskId) {
        return;
    }
    state.selectedTaskId = taskId;
    state.taskDetail = null;
    renderTaskList(state.tasks);
    fetchTaskDetail(taskId, true);
}

function startTaskPolling() {
    if (state.taskPollHandle) {
        window.clearInterval(state.taskPollHandle);
    }
    state.taskPollHandle = window.setInterval(async () => {
        if (state.isPolling) {
            return;
        }
        state.isPolling = true;
        try {
            await fetchState({ updateForms: false, refreshTaskDetail: true });
        } catch (error) {
            setTaskNotice(error.message, "error");
        } finally {
            state.isPolling = false;
        }
    }, 2000);
}

function bindButtons() {
    el("usage-guide-btn").addEventListener("click", async () => {
        setTaskNotice("正在读取使用说明...", "info");
        try {
            await openReadmeModal();
            clearTaskNotice();
        } catch (error) {
            setTaskNotice(error.message, "error");
        }
    });

    el("close-readme-btn").addEventListener("click", closeReadmeModal);
    el("readme-modal").addEventListener("click", (event) => {
        if (event.target.dataset.closeReadme === "true") {
            closeReadmeModal();
        }
    });

    el("confirm-cancel-btn").addEventListener("click", () => closeConfirmModal(false));
    el("confirm-submit-btn").addEventListener("click", () => closeConfirmModal(true));
    el("confirm-modal").addEventListener("click", (event) => {
        if (event.target.dataset.closeConfirm === "true") {
            closeConfirmModal(false);
        }
    });

    el("task-submitted-close-btn").addEventListener("click", closeTaskSubmittedModal);
    el("task-submitted-view-btn").addEventListener("click", () => {
        closeTaskSubmittedModal();
        if (state.taskSubmittedTaskId) {
            selectTask(state.taskSubmittedTaskId);
        }
    });
    el("task-submitted-modal").addEventListener("click", (event) => {
        if (event.target.dataset.closeTaskSubmitted === "true") {
            closeTaskSubmittedModal();
        }
    });

    el("refresh-state-btn").addEventListener("click", () => {
        fetchState({ updateForms: false, refreshTaskDetail: true }).catch((error) => setTaskNotice(error.message, "error"));
    });

    el("save-settings-btn").addEventListener("click", () => {
        performStateAction("/api/settings", collectSettingsPayload(), {
            syncSettings: false,
            startMessage: "正在保存配置...",
            successMessage: "配置已保存。",
            updateForms: true
        });
    });

    el("reload-clients-btn").addEventListener("click", () => {
        performStateAction("/api/reload-clients", {}, {
            startMessage: "正在重新读取名单...",
            successMessage: "名单已重新读取。"
        });
    });

    el("upload-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        syncSelectionState();
        setTaskNotice("正在上传 XLSX...", "info");
        try {
            await syncSettingsSilently();
            const file = el("xlsx-file").files[0];
            if (!file) {
                throw new Error("请先选择 Excel 文件");
            }
            const formData = new FormData();
            formData.append("file", file);
            const response = await fetch("/api/upload-xlsx", {
                method: "POST",
                body: formData
            });
            const payload = await response.json();
            if (!response.ok || payload.status !== "success") {
                throw new Error(payload.mesg || "上传失败");
            }
            applyStateData(payload.data, { updateForms: false });
            setTaskNotice("XLSX 已上传并重新载入。", "info");
        } catch (error) {
            setTaskNotice(error.message, "error");
        }
    });

    el("ping-btn").addEventListener("click", () => {
        startTask("/api/actions/ping", {}, {
            startMessage: "正在创建 Ping 任务...",
            confirm: {
                title: "确认执行 Ping",
                message: [
                    "即将对当前配置的 IP 段发起 Ping 探测。",
                    "该操作会刷新最近一次 Ping 结果。"
                ],
                collectNote: true
            },
            submittedMessage: [
                "Ping 任务已下发。",
                "可在任务详情中查看实时进度和最终探测结果。"
            ]
        });
    });

    el("update-list-btn").addEventListener("click", () => {
        startTask("/api/actions/update-client-list", {}, {
            startMessage: "正在创建更新绑定任务...",
            confirm: {
                title: "确认更新绑定",
                message: [
                    "即将按 connect-check 成功的机器更新 client.xlsx 绑定结果。",
                    "该操作会改写名单中的 IP 绑定信息。"
                ],
                collectNote: true
            },
            submittedMessage: [
                "更新绑定任务已下发。",
                "完成后可在任务结果中查看新的绑定列表。"
            ]
        });
    });

    el("connect-check-btn").addEventListener("click", () => {
        startTask("/api/actions/connect-check", {
            selected_ids: selectedIds()
        }, {
            startMessage: "正在创建 Connect Check 任务...",
            confirm: {
                title: "确认执行 Connect Check",
                message: ({ selectedIds: ids }) => [
                    "即将对 client 发起联通检查请求。",
                    selectionScopeText(ids)
                ],
                collectNote: true
            },
            submittedMessage: ({ selectedIds: ids }) => [
                "Connect Check 任务已下发。",
                selectionScopeText(ids)
            ]
        });
    });

    el("set-client-info-btn").addEventListener("click", () => {
        startTask("/api/actions/set-client-info", {
            selected_ids: selectedIds()
        }, {
            startMessage: "正在创建下发考生信息任务...",
            confirm: {
                title: "确认下发考生信息",
                message: ({ selectedIds: ids }) => [
                    "即将把当前名单中的考生信息下发到 client。",
                    selectionScopeText(ids)
                ],
                collectNote: true
            },
            submittedMessage: ({ selectedIds: ids }) => [
                "考生信息下发任务已创建。",
                selectionScopeText(ids)
            ]
        });
    });

    el("get-client-status-btn").addEventListener("click", () => {
        startTask("/api/actions/get-client-status", {
            selected_ids: selectedIds()
        }, {
            startMessage: "正在创建获取客户端状态任务...",
            confirm: {
                title: "确认获取客户端状态",
                message: ({ selectedIds: ids }) => [
                    "即将向 client 请求当前状态。",
                    selectionScopeText(ids)
                ],
                collectNote: true
            },
            submittedMessage: ({ selectedIds: ids }) => [
                "状态采集任务已下发。",
                selectionScopeText(ids)
            ]
        });
    });

    el("get-client-log-btn").addEventListener("click", () => {
        startTask("/api/actions/get-client-log", {
            selected_ids: selectedIds()
        }, {
            startMessage: "正在创建获取客户端日志任务...",
            confirm: {
                title: "确认获取客户端日志",
                message: ({ selectedIds: ids }) => [
                    "即将向 client 请求日志内容。",
                    selectionScopeText(ids)
                ],
                collectNote: true
            },
            submittedMessage: ({ selectedIds: ids }) => [
                "日志采集任务已下发。",
                selectionScopeText(ids)
            ]
        });
    });

    el("run-command-btn").addEventListener("click", () => {
        startTask("/api/actions/run-command", {
            selected_ids: selectedIds(),
            command_id: el("command-id").value.trim() || "default",
            command: el("command-text").value
        }, {
            startMessage: "正在创建批量命令任务...",
            confirm: {
                title: "确认批量执行命令",
                message: ({ selectedIds: ids, payload: confirmPayload }) => [
                    `即将下发命令 ID: ${confirmPayload.command_id}`,
                    selectionScopeText(ids),
                    `命令内容: ${confirmPayload.command || "(空)"}`
                ],
                collectNote: true
            },
            submittedMessage: ({ selectedIds: ids, payload: submitPayload }) => [
                `批量命令任务已下发，命令 ID: ${submitPayload.command_id}`,
                selectionScopeText(ids)
            ]
        });
    });

    el("kill-command-btn").addEventListener("click", () => {
        startTask("/api/actions/kill-command", {
            selected_ids: selectedIds(),
            command_id: el("command-id").value.trim() || "default"
        }, {
            startMessage: "正在创建停止命令任务...",
            confirm: {
                title: "确认停止命令",
                message: ({ selectedIds: ids, payload: confirmPayload }) => [
                    `即将停止命令 ID: ${confirmPayload.command_id}`,
                    selectionScopeText(ids)
                ],
                confirmText: "确认停止",
                danger: true,
                collectNote: true
            },
            submittedMessage: ({ selectedIds: ids, payload: submitPayload }) => [
                `停止命令任务已下发，命令 ID: ${submitPayload.command_id}`,
                selectionScopeText(ids)
            ]
        });
    });

    el("open-window-btn").addEventListener("click", () => {
        startTask("/api/actions/open-window", {
            selected_ids: selectedIds(),
            window_id: Number(el("window-id").value || 1),
            title: el("window-title").value,
            content: el("window-content").value,
            front_size: Number(el("window-font-size").value || 16)
        }, {
            startMessage: "正在创建打开窗口任务...",
            confirm: {
                title: "确认打开窗口",
                message: ({ selectedIds: ids, payload: confirmPayload }) => [
                    `即将打开窗口 ID: ${confirmPayload.window_id}`,
                    `标题: ${confirmPayload.title || "(空)"}`,
                    selectionScopeText(ids)
                ],
                collectNote: true
            },
            submittedMessage: ({ selectedIds: ids, payload: submitPayload }) => [
                `打开窗口任务已下发，窗口 ID: ${submitPayload.window_id}`,
                selectionScopeText(ids)
            ]
        });
    });

    el("close-window-btn").addEventListener("click", () => {
        startTask("/api/actions/close-window", {
            selected_ids: selectedIds(),
            window_id: Number(el("window-id").value || 1)
        }, {
            startMessage: "正在创建关闭窗口任务...",
            confirm: {
                title: "确认关闭窗口",
                message: ({ selectedIds: ids, payload: confirmPayload }) => [
                    `即将关闭窗口 ID: ${confirmPayload.window_id}`,
                    selectionScopeText(ids)
                ],
                confirmText: "确认关闭",
                danger: true,
                collectNote: true
            },
            submittedMessage: ({ selectedIds: ids, payload: submitPayload }) => [
                `关闭窗口任务已下发，窗口 ID: ${submitPayload.window_id}`,
                selectionScopeText(ids)
            ]
        });
    });

    el("select-all-btn").addEventListener("click", () => {
        document.querySelectorAll(".client-selector").forEach((item) => {
            item.checked = true;
        });
        syncSelectionState();
        updateMasterCheckbox();
        updateSelectionSummary();
    });

    el("clear-selection-btn").addEventListener("click", () => {
        document.querySelectorAll(".client-selector").forEach((item) => {
            item.checked = false;
        });
        syncSelectionState();
        updateMasterCheckbox();
        updateSelectionSummary();
    });

    el("master-checkbox").addEventListener("change", (event) => {
        document.querySelectorAll(".client-selector").forEach((item) => {
            item.checked = event.target.checked;
        });
        syncSelectionState();
        updateMasterCheckbox();
        updateSelectionSummary();
    });

    el("command-template-select").addEventListener("change", applyCommandTemplateSelection);
    el("window-template-select").addEventListener("change", applyWindowTemplateSelection);
    el("use-command-template-btn").addEventListener("click", applyCommandTemplateSelection);
    el("use-window-template-btn").addEventListener("click", applyWindowTemplateSelection);

    el("task-list").addEventListener("click", (event) => {
        const taskButton = event.target.closest(".task-item");
        if (!taskButton) {
            return;
        }
        selectTask(taskButton.dataset.taskId);
    });

    el("clear-task-history-btn").addEventListener("click", async () => {
        const confirmResult = await showConfirmModal({
            title: "确认清空历史任务",
            message: [
                "将清空所有已完成或失败的历史任务记录。",
                "正在执行中的任务不会被删除。"
            ],
            confirmText: "确认清空",
            danger: true
        });
        if (!confirmResult.confirmed) {
            return;
        }
        try {
            const data = await apiRequest("/api/tasks/clear-history", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({})
            });
            await fetchState({ updateForms: false, refreshTaskDetail: true });
            setTaskNotice(`已清空 ${data.cleared_count} 条历史任务，剩余 ${data.remaining_count} 条任务记录。`, "info");
        } catch (error) {
            setTaskNotice(error.message, "error");
        }
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    bindButtons();
    try {
        await fetchState({ updateForms: true, refreshTaskDetail: true });
        startTaskPolling();
    } catch (error) {
        setTaskNotice(error.message, "error");
    }
});
