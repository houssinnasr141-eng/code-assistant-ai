
const codeEditor = document.getElementById("code");

const analyzeButton = document.getElementById("analyze");
const clearButton = document.getElementById("clear");
const fixButton = document.getElementById("fixCode");

const lineNumbers = document.getElementById("lineNumbers");
const lineCount = document.getElementById("lineCount");
const charCount = document.getElementById("charCount");

const issuesList = document.getElementById("issuesList");
const loopsList = document.getElementById("loopsList");

const resultMessage = document.getElementById("resultMessage");
const messageText = document.getElementById("messageText");

const fixPanel = document.getElementById("fixPanel");
const fixedCodeElement = document.getElementById("fixedCode");
const fixDescription = document.getElementById("fixDescription");
const fixChanges = document.getElementById("fixChanges");

let latestFixedCode = null;


// ------------------------------------
// EDITOR INFORMATION
// ------------------------------------

function updateEditorInfo() {

    const code = codeEditor.value;
    const lines = code.split("\n").length;

    lineNumbers.textContent = Array.from(
        { length: lines },
        (_, index) => index + 1
    ).join("\n");

    lineCount.textContent = `${lines} lines`;
    charCount.textContent = `${code.length} characters`;
}

codeEditor.addEventListener("input", function() {

    updateEditorInfo();

    // The old suggestion is no longer guaranteed to match edited code.
    latestFixedCode = null;
    fixButton.disabled = true;
    fixPanel.classList.add("hidden");
});


// Synchronize line number scrolling.
codeEditor.addEventListener("scroll", function() {
    lineNumbers.scrollTop = codeEditor.scrollTop;
});


// Add four spaces when Tab is pressed.
codeEditor.addEventListener("keydown", function(event) {

    if (event.key === "Tab") {

        event.preventDefault();

        const start = codeEditor.selectionStart;
        const end = codeEditor.selectionEnd;

        codeEditor.value =
            codeEditor.value.substring(0, start) +
            "    " +
            codeEditor.value.substring(end);

        codeEditor.selectionStart = start + 4;
        codeEditor.selectionEnd = start + 4;

        updateEditorInfo();
    }

    if (event.ctrlKey && event.key === "Enter") {
        analyzeCode();
    }
});


// ------------------------------------
// RESET DASHBOARD
// ------------------------------------

function resetDashboard() {

    document.getElementById("errorCount").textContent = "0";
    document.getElementById("warningCount").textContent = "0";
    document.getElementById("infoCount").textContent = "0";

    document.getElementById("codeStatus").textContent = "Ready";

    document.getElementById("totalLines").textContent = "—";
    document.getElementById("nonEmptyLines").textContent = "—";
    document.getElementById("functionCount").textContent = "—";
    document.getElementById("classCount").textContent = "—";
    document.getElementById("importCount").textContent = "—";

    document.getElementById("issueTotal").textContent = "0 ISSUES";

    document.getElementById("analysisStatus").textContent =
        "Waiting for analysis";

    document.getElementById("analysisStatus").className =
        "status-badge";

    resultMessage.className = "result-message";

    messageText.textContent =
        "Your analysis results will appear here.";

    issuesList.innerHTML = `
        <div class="empty-state">
            <div>⌕</div>
            <h3>No analysis yet</h3>
            <p>Enter Python code to start analyzing.</p>
        </div>
    `;

    loopsList.innerHTML = `
        <div class="empty-state">
            <div>↻</div>
            <h3>No loops analyzed</h3>
            <p>Loop information will appear here.</p>
        </div>
    `;

    fixPanel.classList.add("hidden");
    fixButton.disabled = true;
    latestFixedCode = null;
}


// ------------------------------------
// CLEAR EDITOR
// ------------------------------------

clearButton.addEventListener("click", function() {

    codeEditor.value = "";

    updateEditorInfo();
    resetDashboard();

    codeEditor.focus();
});


// ------------------------------------
// DISPLAY MAIN MESSAGE
// ------------------------------------

function displayMessage(message, success) {

    messageText.textContent = message;

    resultMessage.className = success
        ? "result-message success"
        : "result-message error";
}


// ------------------------------------
// DISPLAY STATISTICS
// ------------------------------------

function updateStatistics(statistics) {

    if (!statistics) {
        return;
    }

    document.getElementById("totalLines").textContent =
        statistics.total_lines ?? "—";

    document.getElementById("nonEmptyLines").textContent =
        statistics.non_empty_lines ?? "—";

    document.getElementById("functionCount").textContent =
        statistics.functions ?? "—";

    document.getElementById("classCount").textContent =
        statistics.classes ?? "—";

    document.getElementById("importCount").textContent =
        statistics.imports ?? "—";
}


// ------------------------------------
// DISPLAY SUMMARY
// ------------------------------------

function updateSummary(summary) {

    const errors = summary?.errors ?? 0;
    const warnings = summary?.warnings ?? 0;
    const information = summary?.information ?? 0;

    document.getElementById("errorCount").textContent = errors;
    document.getElementById("warningCount").textContent = warnings;
    document.getElementById("infoCount").textContent = information;

    document.getElementById("codeStatus").textContent =
        errors > 0 ? "Issues" : "Passed";
}


// ------------------------------------
// DISPLAY ISSUES AND EXPLANATIONS
// ------------------------------------

function displayIssues(issues) {

    issuesList.innerHTML = "";

    document.getElementById("issueTotal").textContent =
        `${issues.length} ISSUES`;

    if (issues.length === 0) {

        issuesList.innerHTML = `
            <div class="empty-state">
                <div>✓</div>
                <h3>No detected problems!</h3>
                <p>Your code passed the available checks.</p>
            </div>
        `;

        return;
    }

    issues.forEach(function(issue) {

        const severity = ["error", "warning", "info"].includes(
            issue.severity
        ) ? issue.severity : "info";

        const card = document.createElement("div");
        card.className = `issue-card ${severity}`;

        const top = document.createElement("div");
        top.className = "issue-top";

        const category = document.createElement("span");
        category.className = "issue-category";
        category.textContent = issue.category || "General";

        const line = document.createElement("span");
        line.className = "issue-line";
        line.textContent = `Line ${issue.line ?? "?"}`;

        const label = document.createElement("span");
        label.className = `severity ${severity}`;
        label.textContent = severity;

        top.append(category, line, label);

        const message = document.createElement("p");
        message.className = "issue-message";
        message.textContent = issue.message || "Unknown issue.";

        const explanation = document.createElement("div");
        explanation.className = "explanation-box";

        const explanationTitle = document.createElement("strong");
        explanationTitle.textContent = "What does this mean?";

        const explanationText = document.createElement("p");
        explanationText.textContent =
            issue.explanation || "No explanation is available.";

        explanation.append(explanationTitle, explanationText);

        const suggestion = document.createElement("div");
        suggestion.className = "issue-suggestion";
        suggestion.textContent =
            "💡 Suggested solution: " +
            (issue.suggestion || "Review this part of your code.");

        card.append(top, message, explanation, suggestion);

        issuesList.appendChild(card);
    });
}


// ------------------------------------
// DISPLAY LOOP ANALYSIS
// ------------------------------------

function displayLoops(loops) {

    loopsList.innerHTML = "";

    if (!loops || loops.length === 0) {

        loopsList.innerHTML = `
            <div class="empty-state">
                <div>↻</div>
                <h3>No loops found</h3>
                <p>
                    This program does not contain a detected
                    for or while loop.
                </p>
            </div>
        `;

        return;
    }

    loops.forEach(function(loop) {

        const card = document.createElement("div");
        card.className = "loop-card";

        const title = document.createElement("h4");
        title.textContent =
            `${loop.type} — Line ${loop.line}`;

        const explanation = document.createElement("p");
        explanation.textContent = loop.explanation;

        const suggestion = document.createElement("div");
        suggestion.className = "issue-suggestion";
        suggestion.textContent =
            "💡 " + loop.suggestion;

        card.append(title, explanation, suggestion);

        loopsList.appendChild(card);
    });
}


// ------------------------------------
// DISPLAY FIXED CODE
// ------------------------------------

function displayFixedCode(data) {

    latestFixedCode = data.fixed_code ?? "";

    fixedCodeElement.textContent = latestFixedCode;

    fixPanel.classList.remove("hidden");
    fixButton.disabled = false;

    if (data.fixes && data.fixes.length > 0) {

        fixDescription.textContent =
            "The analyzer made the following safe automatic improvements:";

        fixChanges.innerHTML = "";

        data.fixes.forEach(function(change) {

            const item = document.createElement("p");
            item.textContent = "✓ " + change;

            fixChanges.appendChild(item);
        });

    } else {

        fixDescription.textContent =
            "No automatic changes were made. Review the issue explanations and suggestions before editing your code.";

        fixChanges.innerHTML = "";

        const item = document.createElement("p");
        item.textContent =
            "No safe automatic fix was identified.";

        fixChanges.appendChild(item);
    }
}


// ------------------------------------
// MAIN ANALYSIS FUNCTION
// ------------------------------------

async function analyzeCode() {

    const code = codeEditor.value;

    if (!code.trim()) {

        displayMessage(
            "Please enter Python code before starting the analysis.",
            false
        );

        return;
    }

    analyzeButton.disabled = true;
    fixButton.disabled = true;

    analyzeButton.textContent = "Analyzing...";

    latestFixedCode = null;
    fixPanel.classList.add("hidden");

    document.getElementById("analysisStatus").textContent =
        "Analyzing";

    resultMessage.className = "result-message";
    messageText.textContent = "Analyzing your Python code...";

    issuesList.innerHTML = `
        <div class="empty-state">
            <div>◌</div>
            <h3>Analyzing your code</h3>
            <p>Please wait...</p>
        </div>
    `;

    loopsList.innerHTML = `
        <div class="empty-state">
            <div>◌</div>
            <h3>Analyzing loops</h3>
            <p>Please wait...</p>
        </div>
    `;

    try {

        const response = await fetch("/api/analyze", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                code: code
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Server request failed.");
        }

        displayMessage(data.message, data.success);

        updateStatistics(data.statistics);
        updateSummary(data.summary);

        displayIssues(
            Array.isArray(data.issues) ? data.issues : []
        );

        displayLoops(
            Array.isArray(data.loops) ? data.loops : []
        );

        displayFixedCode(data);

        const status = document.getElementById("analysisStatus");

        if (data.success) {

            status.textContent = "Analysis Passed";
            status.className = "status-badge success";

        } else {

            status.textContent = "Issues Detected";
            status.className = "status-badge error";
        }

    } catch (error) {

        displayMessage(
            error.message || "Connection error. Check your Python server.",
            false
        );

        issuesList.innerHTML = `
            <div class="empty-state">
                <div>!</div>
                <h3>Analysis failed</h3>
                <p>Make sure app.py is running.</p>
            </div>
        `;

        document.getElementById("analysisStatus").textContent =
            "Connection Error";

        document.getElementById("analysisStatus").className =
            "status-badge error";

    } finally {

        analyzeButton.disabled = false;
        analyzeButton.textContent = "✦ Analyze Code →";
    }
}


// ------------------------------------
// ANALYZE BUTTON
// ------------------------------------

analyzeButton.addEventListener("click", analyzeCode);


// ------------------------------------
// FIX CODE BUTTON
// ------------------------------------

fixButton.addEventListener("click", function() {

    if (latestFixedCode === null) {
        return;
    }

    fixPanel.classList.remove("hidden");

    fixPanel.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });
});


// ------------------------------------
// APPLY FIX TO EDITOR
// ------------------------------------

document.getElementById("applyFix").addEventListener(
    "click",
    function() {

        if (latestFixedCode === null) {
            return;
        }

        codeEditor.value = latestFixedCode;

        updateEditorInfo();

        codeEditor.focus();

        // A new analysis is needed after applying the changes.
        latestFixedCode = null;
        fixButton.disabled = true;

        fixDescription.textContent =
            "Suggested code was copied into the editor. Analyze it again to check the result.";
    }
);


// ------------------------------------
// COPY FIXED CODE
// ------------------------------------

document.getElementById("copyFix").addEventListener(
    "click",
    async function() {

        if (latestFixedCode === null) {
            return;
        }

        try {

            await navigator.clipboard.writeText(latestFixedCode);

            this.textContent = "Copied!";

            setTimeout(() => {
                this.textContent = "Copy Suggested Code";
            }, 1500);

        } catch (error) {

            fixDescription.textContent =
                "Copy failed. You can select and copy the code manually.";
        }
    }
);


// ------------------------------------
// INITIALIZE
// ------------------------------------

updateEditorInfo();
resetDashboard();
