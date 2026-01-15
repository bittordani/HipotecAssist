// const API = "http://localhost:8000";
const API = "https://hipotecassist-backend-613538748724.europe-west1.run.app";

// Generar un ID de sesión único por usuario
let session_id = sessionStorage.getItem("session_id");
if (!session_id) {
  session_id = crypto.randomUUID(); // ID aleatorio
  sessionStorage.setItem("session_id", session_id);
}

// Llamar al backend para reiniciar la sesión cada vez que se refresca la página
fetch(`${API}/reiniciar_sesion`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ session_id })
});



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

    
    // Guardamos el análisis para el chat
    ultimoResultado = data;
    addMessage("Sistema", "Análisis completado. Ahora puedes hacer preguntas al asistente.");

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
// ---------- Chat asistente hipotecario mejorado (versión grande) ----------

// ---------- Chat asistente hipotecario mejorado (con typing y Enter) ----------

let ultimoResultado = null;
let typingIndicator = null;

// Crear contenedor del chat
const chatPanel = document.createElement("div");
chatPanel.id = "chat-panel";
chatPanel.style = `
  border: 1px solid #ddd;
  border-radius: 12px;
  padding: 20px;
  margin-top: 30px;
  background: #fafafa;
  max-width: 800px;
  min-height: 550px;
  margin-left: auto;
  margin-right: auto;
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
  display: flex;
  flex-direction: column;
`;

// Título
const chatTitle = document.createElement("h2");
chatTitle.textContent = "Asistente Hipotecario 💬";
chatTitle.style = `
  margin-bottom: 15px;
  text-align: center;
  color: #333;
  font-size: 1.6rem;
`;
chatPanel.appendChild(chatTitle);

// Contenedor de mensajes
const chatMessages = document.createElement("div");
chatMessages.id = "chat-messages";
chatMessages.style = `
  flex: 1;
  border: 1px solid #ccc;
  border-radius: 10px;
  padding: 14px;
  height: 400px;
  overflow-y: auto;
  background: white;
  margin-bottom: 16px;
  font-family: system-ui, sans-serif;
  font-size: 16px;
  position: relative;
`;
chatPanel.appendChild(chatMessages);

// Input + botón
const chatInputContainer = document.createElement("div");
chatInputContainer.style = `
  display: flex;
  gap: 10px;
  align-items: center;
`;

const chatInput = document.createElement("input");
chatInput.id = "chat-input";
chatInput.placeholder = "Escribe tu pregunta...";
chatInput.style = `
  flex: 1;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #ccc;
  font-size: 15px;
`;
chatInputContainer.appendChild(chatInput);

const chatSend = document.createElement("button");
chatSend.textContent = "Enviar";
chatSend.style = `
  background: #007bff;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 10px 16px;
  cursor: pointer;
  font-weight: bold;
  font-size: 15px;
`;
chatSend.onmouseover = () => (chatSend.style.background = "#0069d9");
chatSend.onmouseout = () => (chatSend.style.background = "#007bff");
chatInputContainer.appendChild(chatSend);

chatPanel.appendChild(chatInputContainer);
document.querySelector(".container").appendChild(chatPanel);

function addMessage(sender, text, documentos = []) {
  console.log("📄 documentos:", documentos);

  const msg = document.createElement("div");
  msg.className = sender === "Usuario" ? "msg-user" : "msg-bot";

  let docsHTML = "";
  if (documentos.length > 0) {
    docsHTML = `<div style="text-align:center; margin-top:6px;">
      <ul style='list-style:none; padding-left:0; margin:0; display:inline-flex; gap:6px;'>`;
    documentos.forEach(d => {
    docsHTML += `
      <li>
        <a href="${API}${d.url}" target="_blank"
          style="
            display:inline-flex;
            align-items:center;
            gap:6px;
            padding:3px 5px;
            background:#0d6efd;
            color:#fff;
            border-radius:4px;
            text-decoration:none;
            font-size:0.65em;
          ">
          <span style="font-size:0.7em;">📄</span> ${d.origen}
        </a>
      </li>
    `;
  });

    docsHTML += "</ul></div>";
  }


"#e0e0e0ff"
  msg.innerHTML = `<strong>${sender}:</strong><br>${text}${docsHTML}`;

  msg.style.margin = "10px 0";
  msg.style.padding = "10px 12px";
  msg.style.borderRadius = "10px";
  msg.style.maxWidth = "75%";
  msg.style.whiteSpace = "pre-wrap";

  msg.style.background = sender === "Usuario" ? "#e7f1ff" : "#f3f3f3";
  msg.style.marginLeft = sender === "Usuario" ? "auto" : "0";

  chatMessages.appendChild(msg);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}


// CSS animación typing estilo WhatsApp (3 puntos)
const style = document.createElement("style");
style.textContent = `
.typing {
  display: flex;
  justify-content: space-between;
  width: 24px;
  margin-left: 8px;
}
.typing span {
  width: 6px;
  height: 6px;
  background: #999;
  border-radius: 50%;
  animation: blink 1.4s infinite both;
}
.typing span:nth-child(2) {
  animation-delay: 0.2s;
}
.typing span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0%, 80%, 100% { opacity: 0.3; }
  40% { opacity: 1; }
}
`;
document.head.appendChild(style);

function showTyping() {
  typingIndicator = document.createElement("div");
  typingIndicator.className = "msg-bot";
  typingIndicator.innerHTML = `
    <strong>Bot:</strong>
    <div class="typing">
      <span></span><span></span><span></span>
    </div>
  `;
  chatMessages.appendChild(typingIndicator);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function hideTyping() {
  if (typingIndicator) {
    typingIndicator.remove();
    typingIndicator = null;
  }
}



async function sendMessage() {
  const pregunta = chatInput.value.trim();
  if (!pregunta) return;

  addMessage("Usuario", pregunta);
  chatInput.value = "";

  if (!ultimoResultado) {
    addMessage("Bot", "Primero realiza un análisis antes de preguntar. 🏡");
    return;
  }

  showTyping();

  try {
    const res = await fetch(`${API}/preguntar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        pregunta,
        session_id,      // <-- agregamos aquí el session_id
        temperature: 0.2, // opcional, igual que en backend
        max_tokens: 250   // opcional
      })
    });

    const data = await res.json();
    hideTyping();

    // Aquí pasamos también los documentos usados al chat
    console.log(data.documentos_usados);
    addMessage("Bot", data.respuesta, data.documentos_usados);

  } catch (err) {
    hideTyping();
    console.error(err);
    addMessage("Bot", "Error al conectarse con el servidor ❌");
  }
}



// Click para enviar
chatSend.addEventListener("click", sendMessage);

// Enter para enviar
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

