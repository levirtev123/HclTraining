const promptInput = document.querySelector("#prompt");
const runButton = document.querySelector("#runButton");
const sqlOutput = document.querySelector("#sqlOutput");
const rowCount = document.querySelector("#rowCount");
const errorBox = document.querySelector("#errorBox");
const table = document.querySelector("#resultTable");
const schemaList = document.querySelector("#schemaList");
const copySql = document.querySelector("#copySql");

function renderSchema(schema) {
  schemaList.innerHTML = "";
  Object.entries(schema || {}).forEach(([tableName, columns]) => {
    const item = document.createElement("div");
    item.className = "schema-table";
    item.innerHTML = `<strong>${tableName}</strong><span>${columns.join(", ")}</span>`;
    schemaList.appendChild(item);
  });
}

function renderTable(columns, rows) {
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");
  thead.innerHTML = "";
  tbody.innerHTML = "";

  if (!columns.length) {
    rowCount.textContent = "0 rows";
    return;
  }

  const headerRow = document.createElement("tr");
  columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = column;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((column) => {
      const td = document.createElement("td");
      td.textContent = row[column] ?? "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  rowCount.textContent = `${rows.length} ${rows.length === 1 ? "row" : "rows"}`;
}

async function runQuery() {
  runButton.disabled = true;
  runButton.textContent = "Running";
  errorBox.hidden = true;

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: promptInput.value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Query failed");

    sqlOutput.textContent = data.sql;
    renderSchema(data.schema);
    renderTable(data.columns, data.rows);
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    runButton.disabled = false;
    runButton.textContent = "Run";
  }
}

document.querySelectorAll(".examples button").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.textContent;
    runQuery();
  });
});

runButton.addEventListener("click", runQuery);
promptInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    runQuery();
  }
});

copySql.addEventListener("click", async () => {
  await navigator.clipboard.writeText(sqlOutput.textContent);
  copySql.textContent = "Copied";
  window.setTimeout(() => {
    copySql.textContent = "Copy";
  }, 1200);
});

runQuery();
