(() => {
  "use strict";
  const key = "atlas-ui";
  const defaults = { style: "arrondi", mode: "system", accent: "green", size: "16" };
  const choices = { style: ["dense", "arrondi", "document"], mode: ["system", "light", "dark"], accent: ["green", "blue", "orange", "violet", "graphite"], size: ["14", "16", "18", "20"] };
  const translations = {
    en: { title: "Display settings", style: "Style", mode: "Mode", accent: "Accent", size: "Text size", dense: "Dense", arrondi: "Rounded", document: "Document", system: "System", light: "Light", dark: "Dark", green: "Green", blue: "Blue", orange: "Orange", violet: "Violet", graphite: "Graphite", showMore: "Show more", showLess: "Show less" },
    fr: { title: "Paramètres d’affichage", style: "Style", mode: "Mode", accent: "Couleur", size: "Taille du texte", dense: "Dense", arrondi: "Arrondi", document: "Document", system: "Système", light: "Clair", dark: "Sombre", green: "Vert", blue: "Bleu", orange: "Orange", violet: "Violet", graphite: "Graphite", showMore: "Afficher plus", showLess: "Afficher moins" },
    de: { title: "Anzeigeeinstellungen", style: "Stil", mode: "Modus", accent: "Akzentfarbe", size: "Textgröße", dense: "Dicht", arrondi: "Abgerundet", document: "Dokument", system: "System", light: "Hell", dark: "Dunkel", green: "Grün", blue: "Blau", orange: "Orange", violet: "Violett", graphite: "Graphit", showMore: "Mehr anzeigen", showLess: "Weniger anzeigen" },
    es: { title: "Ajustes de pantalla", style: "Estilo", mode: "Modo", accent: "Color de acento", size: "Tamaño del texto", dense: "Compacto", arrondi: "Redondeado", document: "Documento", system: "Sistema", light: "Claro", dark: "Oscuro", green: "Verde", blue: "Azul", orange: "Naranja", violet: "Violeta", graphite: "Grafito", showMore: "Mostrar más", showLess: "Mostrar menos" },
    it: { title: "Impostazioni di visualizzazione", style: "Stile", mode: "Modalità", accent: "Colore principale", size: "Dimensione del testo", dense: "Compatto", arrondi: "Arrotondato", document: "Documento", system: "Sistema", light: "Chiaro", dark: "Scuro", green: "Verde", blue: "Blu", orange: "Arancione", violet: "Viola", graphite: "Grafite", showMore: "Mostra di più", showLess: "Mostra di meno" }
  };
  const saved = (() => { try { return { ...defaults, ...JSON.parse(localStorage.getItem(key) || "{}") }; } catch { return defaults; } })();
  const apply = value => { ["style", "accent", "size"].forEach(name => document.documentElement.dataset[`atlas${name[0].toUpperCase()}${name.slice(1)}`] = value[name]); };
  apply(saved);
  const persist = value => { Object.assign(saved, value); localStorage.setItem(key, JSON.stringify(saved)); apply(saved); };
  const locale = () => {
    // The interface locale (including document.documentElement.lang) is independent.
    const stored = localStorage.getItem("atlas-ui-language");
    const candidate = stored || navigator.language || "en";
    const language = candidate.toLowerCase().split("-")[0];
    return translations[language] ? language : "en";
  };
  const messageContent = bubble => bubble.querySelector(".markdown-prose") || bubble.querySelector("[class*='message-content']") || bubble.querySelector(".chat-user > .w-full > .flex");
  const lineHeight = content => {
    const value = parseFloat(getComputedStyle(content).lineHeight);
    return Number.isFinite(value) ? value : parseFloat(getComputedStyle(content).fontSize) * 1.5;
  };
  const setAttachmentTitles = bubble => bubble.querySelectorAll(".chat-user > .mb-1 > .self-end > button .truncate").forEach(name => { if (name.textContent.trim()) name.title = name.textContent.trim(); });
  const prepareBubble = bubble => {
    const content = messageContent(bubble);
    if (!content) return;
    setAttachmentTitles(bubble);
    const toggle = bubble.querySelector(".atlas-message-toggle");
    const wasExpanded = toggle && toggle.getAttribute("aria-expanded") === "true";
    bubble.classList.remove("atlas-message-collapsed");
    const isLong = content.scrollHeight > lineHeight(content) * 6.1;
    bubble.classList.toggle("atlas-long-message", isLong);
    if (!isLong) { if (toggle) toggle.remove(); return; }
    const words = translations[locale()];
    const button = toggle || document.createElement("button");
    button.type = "button";
    button.className = "atlas-message-toggle";
    button.setAttribute("aria-expanded", String(Boolean(wasExpanded)));
    button.textContent = wasExpanded ? words.showLess : words.showMore;
    if (!toggle) {
      button.addEventListener("click", () => {
        const expanded = button.getAttribute("aria-expanded") !== "true";
        button.setAttribute("aria-expanded", String(expanded));
        button.textContent = expanded ? translations[locale()].showLess : translations[locale()].showMore;
        bubble.classList.toggle("atlas-message-collapsed", !expanded);
      });
      bubble.append(button);
    }
    bubble.classList.toggle("atlas-message-collapsed", !wasExpanded);
  };
  const observeMessages = () => {
    let queued = false;
    const scan = () => { queued = false; document.querySelectorAll(".user-message").forEach(prepareBubble); };
    const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(scan); } };
    new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["data-atlas-size"] });
    window.addEventListener("resize", schedule);
    schedule();
  };
  const mount = () => {
    if (document.getElementById("atlas-ui-selector")) return;
    const words = translations[locale()];
    const option = (group, value) => `<button type="button" data-atlas-option="${group}" data-value="${value}" aria-label="${group === "size" ? `${value} px` : words[value]}" title="${group === "size" ? `${value} px` : words[value]}" aria-pressed="${saved[group] === value}" class="atlas-option">${group === "size" ? `${value} px` : words[value]}</button>`;
    const root = document.createElement("div"); root.id = "atlas-ui-selector";
    root.innerHTML = `<button id="atlas-ui-toggle" type="button" aria-label="${words.title}" aria-expanded="false">Aa</button><section id="atlas-ui-popover" aria-label="${words.title}" hidden><h2>${words.title}</h2>${Object.keys(choices).map(group => `<fieldset><legend>${words[group]}</legend><div class="atlas-options" data-atlas-group="${group}">${choices[group].map(value => option(group, value)).join("")}</div></fieldset>`).join("")}</section>`;
    document.body.append(root);
    const toggle = root.querySelector("#atlas-ui-toggle"), popover = root.querySelector("#atlas-ui-popover");
    const close = () => { popover.hidden = true; toggle.setAttribute("aria-expanded", "false"); toggle.focus(); };
    toggle.addEventListener("click", () => { popover.hidden = !popover.hidden; toggle.setAttribute("aria-expanded", String(!popover.hidden)); if (!popover.hidden) popover.querySelector("button").focus(); });
    root.addEventListener("click", event => { const button = event.target.closest("[data-atlas-option]"); if (!button) return; const group = button.dataset.atlasOption; persist({ [group]: button.dataset.value }); root.querySelectorAll(`[data-atlas-option="${group}"]`).forEach(item => item.setAttribute("aria-pressed", String(item === button))); if (group === "mode") { localStorage.setItem("theme", button.dataset.value); location.reload(); } });
    document.addEventListener("keydown", event => { if (event.key === "Escape" && !popover.hidden) { event.preventDefault(); event.stopImmediatePropagation(); close(); } }, true);
  };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", mount, { once: true }) : mount();
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", observeMessages, { once: true }) : observeMessages();
})();
