const API = "/api";

const el = (id) => document.getElementById(id);
const fmt = (n) => n?.toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const tipoSelect = el("tipo");
const bloqueFijo = el("bloque-fijo");
const bloqueVariable = el("bloque-variable");

tipoSelect.addEventListener("change", () => {
  const t = tipoSelect.value;
  if (t === "fijo") {
    bloqueFijo.classList.remove("hidden");
    bloqueVariable.classList.add("hidden");
  } else {
    bloqueFijo.classList.add("hidden");
    bloqueVariable.classList.remove("hidden");
  }
});

// Submit
el("form-analisis").addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    capital_pendiente: parseFloat(el("capital_pendiente").value),
    anos_restantes: parseInt(el("anos_restantes").value),
    tipo: el("tipo").value,
    tin: parseFloat(el("tin").value) || null,
    euribor: parseFloat(el("euribor").value) || null,
    diferencial: parseFloat(el("diferencial").value) || null,
    cuota_actual: parseFloat(el("cuota_actual").value) || null,
    ingresos_mensuales: parseFloat(el("ingresos_mensuales").value) || null,
    otras_deudas_mensuales: parseFloat(el("otras_deudas_mensuales").value) || 0,
    valor_vivienda: parseFloat(el("valor_vivienda").value) || null,
    oferta_alternativa_tin: parseFloat(el("oferta_alternativa_tin").value) || null,
  };

  try {
    const res = await fetch(`${API}/analisis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "Error en el análisis");
      return;
    }

    // Tarjetas principales
    const cards = [];
    cards.push(card("Tipo", data.entrada.tipo, "hint"));
    cards.push(card("Cuota efectiva", `${fmt(data.metricas.cuota_efectiva)} €`));
    cards.push(card("Intereses restantes (aprox.)", `${fmt(data.metricas.intereses_restantes_aprox)} €`));
    if (data.metricas.dti != null) {
      const cls = data.metricas.dti >= 40 ? "danger" : (data.metricas.dti >= 35 ? "warn" : "ok");
      cards.push(card("DTI", `${data.metricas.dti}%`, cls));
    } else {
      cards.push(card("DTI", "—", "hint"));
    }
    if (data.metricas.ltv != null) {
      const cls = data.metricas.ltv > 80 ? "danger" : (data.metricas.ltv > 70 ? "warn" : "ok");
      cards.push(card("LTV", `${data.metricas.ltv}%`, cls));
    } else {
      cards.push(card("LTV", "—", "hint"));
    }
    el("cards").innerHTML = cards.join("");

    // Tabla resumen amortización
    const tbody = el("tabla-resumen").querySelector("tbody");
    tbody.innerHTML = "";
    (data.resumen_amortizacion || []).forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${r.mes}</td>
        <td>${fmt(r.cuota)} €</td>
        <td>${fmt(r.interes_mes)} €</td>
        <td>${fmt(r.amortizado_mes)} €</td>
        <td>${fmt(r.saldo)} €</td>
        <td>${fmt(r.interes_acum)} €</td>
      `;
      tbody.appendChild(tr);
    });

    // Stress test
    const stressDiv = el("stress");
    const base = data.stress_test?.cuota_base;
    const esc = data.stress_test?.escenarios || [];
    stressDiv.innerHTML = `
      <p>Cuota base: <b>${fmt(base)} €</b></p>
      <ul>
        ${esc.map(s => `<li>+${s.delta_tipo_pp} pp → cuota ${fmt(s.cuota)} € (Δ ${fmt(s.diferencia)} €)</li>`).join("")}
      </ul>
    `;

    // Ahorros por amortización
    const ah = data.amortizacion_extra;
    el("ahorros").innerHTML = `
      <ul>
        <li>Amortizar 1.000 € ahora → ahorro intereses: <b>${fmt(ah.ahorro_1k)} €</b></li>
        <li>Amortizar 5.000 € ahora → ahorro intereses: <b>${fmt(ah.ahorro_5k)} €</b></li>
        <li>Amortizar 10.000 € ahora → ahorro intereses: <b>${fmt(ah.ahorro_10k)} €</b></li>
      </ul>
    `;

    // Subrogación
    const subPanel = el("subrogacion-panel");
    const subDiv = el("subrogacion");
    if (data.comparativa_subrogacion) {
      const c = data.comparativa_subrogacion;
      subPanel.style.display = "block";
      subDiv.innerHTML = `
        <p>TIN alternativo: <b>${c.tin_alternativo}%</b></p>
        <p>Cuota alternativa: <b>${fmt(c.cuota_alternativa)} €</b> (Δ ${fmt(c.diferencia_cuota)} €)</p>
        <p>Intereses alternativos: <b>${fmt(c.intereses_alternativos)} €</b></p>
        <p>Ahorro de intereses total (aprox.): <b>${fmt(c.ahorro_intereses)} €</b></p>
      `;
    } else {
      subPanel.style.display = "none";
      subDiv.innerHTML = "";
    }

    // Avisos
    const avisos = el("avisos");
    avisos.innerHTML = "";
    (data.avisos || []).forEach(a => {
      const li = document.createElement("li");
      li.textContent = a;
      avisos.appendChild(li);
    });

  } catch (err) {
    console.error(err);
    alert("No se pudo conectar con el servidor. ¿Está encendido en 127.0.0.1:8000?");
  }
});

function card(title, value, badge = null) {
  const badgeClass = badge ? `badge ${badge}` : "";
  const valueHtml = badge ? `<span class="${badgeClass}">${value}</span>` : `<span class="value">${value}</span>`;
  return `
    <div class="card">
      <h3>${title}</h3>
      ${valueHtml}
    </div>
  `;
}

// ---------- Chat asistente hipotecario ----------
let ultimoResultado = null; // guardará el último análisis

// Crear contenedor de chat
const chatPanel = document.createElement("div");
chatPanel.id = "chat-panel";
chatPanel.style = "border:1px solid #ccc; padding:10px; margin-top:20px;";

// Título
const chatTitle = document.createElement("h2");
chatTitle.textContent = "Asistente Hipotecario";
chatPanel.appendChild(chatTitle);

// Mensajes
const chatMessages = document.createElement("div");
chatMessages.id = "chat-messages";
chatMessages.style = "border:1px solid #ccc; padding:10px; height:200px; overflow-y:auto; margin-bottom:10px;";
chatPanel.appendChild(chatMessages);

// Input + botón
const chatInput = document.createElement("input");
chatInput.id = "chat-input";
chatInput.placeholder = "Escribe tu pregunta...";
chatInput.style = "width:70%; margin-right:5px;";
chatPanel.appendChild(chatInput);

const chatSend = document.createElement("button");
chatSend.textContent = "Enviar";
chatPanel.appendChild(chatSend);

// Añadir chat al final del contenedor principal
document.querySelector(".container").appendChild(chatPanel);

// Función para mostrar mensajes
function addMessage(sender, text) {
  const div = document.createElement("div");
  div.innerHTML = `<strong>${sender}:</strong> ${text}`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Guardar análisis para usar en el chat
const formAnalisis = el("form-analisis");
formAnalisis.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Después de que el análisis haya ido bien...
  const payload = {
    capital_pendiente: parseFloat(el("capital_pendiente").value),
    anos_restantes: parseInt(el("anos_restantes").value),
    tipo: el("tipo").value,
    tin: parseFloat(el("tin").value) || null,
    euribor: parseFloat(el("euribor").value) || null,
    diferencial: parseFloat(el("diferencial").value) || null,
    cuota_actual: parseFloat(el("cuota_actual").value) || null,
    ingresos_mensuales: parseFloat(el("ingresos_mensuales").value) || null,
    otras_deudas_mensuales: parseFloat(el("otras_deudas_mensuales").value) || 0,
    valor_vivienda: parseFloat(el("valor_vivienda").value) || null,
    oferta_alternativa_tin: parseFloat(el("oferta_alternativa_tin").value) || null,
  };

  try {
    const res = await fetch(`${API}/analisis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (data.ok) {
      ultimoResultado = data; // guardamos el análisis
      addMessage("Sistema", "Análisis completado. Ahora puedes hacer preguntas al asistente.");
    }
  } catch (err) {
    console.error(err);
  }
});

// Enviar preguntas al bot
chatSend.addEventListener("click", async () => {
  if (!ultimoResultado) {
    alert("Primero debes hacer un análisis.");
    return;
  }

  const pregunta = chatInput.value.trim();
  if (!pregunta) return;

  addMessage("Usuario", pregunta);
  chatInput.value = "";

  try {
    const res = await fetch(`${API}/preguntar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pregunta,
        contexto: ultimoResultado // enviamos el análisis como contexto
      })
    });

    const data = await res.json();
    addMessage("Bot", data.respuesta || "No se pudo generar respuesta.");
  } catch (err) {
    console.error(err);
    addMessage("Bot", "Error al conectarse con el servidor.");
  }
});
