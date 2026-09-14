import { defineContentScript } from "wxt/utils/define-content-script";
import { browser } from "wxt/browser";
import type { PedidoVerificar, RespostaVerificar, Veredito } from "../tipos";

interface Rotulo {
  texto: string;
  cor: string;
}

const ROTULOS = {
  sustenta: { texto: "Sustenta", cor: "#1a7f37" },
  exagera: { texto: "Exagera", cor: "#bc4c00" },
  nada_encontrado: { texto: "Nada encontrado", cor: "#57606a" },
  erro: { texto: "Erro", cor: "#cf222e" },
} satisfies Record<string, Rotulo>;

/** Estado desconhecido cai no rotulo de erro. */
function rotulo(estado: string): Rotulo {
  const mapa: Record<string, Rotulo> = ROTULOS;
  return mapa[estado] ?? ROTULOS.erro;
}

export default defineContentScript({
  matches: ["<all_urls>", "file:///*"],
  runAt: "document_idle",

  main() {
    // Toda a UI vive num shadow root: o CSS da pagina nao vaza pra ca
    // e o nosso nao vaza pra la.
    const host = document.createElement("div");
    host.id = "verificador-cientifico-host";
    const shadow = host.attachShadow({ mode: "closed" });
    document.documentElement.appendChild(host);

    shadow.appendChild(estilos());

    const botao = document.createElement("button");
    botao.className = "vc-botao";
    botao.textContent = "Verificar";
    botao.hidden = true;
    shadow.appendChild(botao);

    const painel = document.createElement("div");
    painel.className = "vc-painel";
    painel.hidden = true;
    shadow.appendChild(painel);

    let trechoAtual = "";

    // --- seleção -----------------------------------------------------------
    document.addEventListener("mouseup", (e) => {
      // Clique dentro da nossa propria UI nao conta como nova selecao.
      if (e.composedPath().includes(host)) return;

      // O navegador so atualiza a selecao depois do mouseup: esperamos um tick.
      setTimeout(() => {
        const sel = window.getSelection();
        const trecho = sel?.toString().trim() ?? "";

        if (trecho.length < 10 || !sel || sel.rangeCount === 0) {
          botao.hidden = true;
          return;
        }

        trechoAtual = trecho;
        const r = sel.getRangeAt(0).getBoundingClientRect();
        // O host e fixed cobrindo a viewport, entao usamos coordenadas de viewport.
        botao.style.top = `${Math.max(8, r.top - 40)}px`;
        botao.style.left = `${Math.max(8, r.left)}px`;
        botao.hidden = false;
      }, 0);
    });

    document.addEventListener("mousedown", (e) => {
      if (e.composedPath().includes(host)) return;
      botao.hidden = true;
    });

    // --- ação --------------------------------------------------------------
    botao.addEventListener("click", async () => {
      botao.hidden = true;
      const trecho = trechoAtual;
      mostrarCarregando(painel, trecho);

      const pedido: PedidoVerificar = {
        tipo: "verificar",
        trecho,
        url: location.href,
      };

      try {
        const resposta = (await browser.runtime.sendMessage(
          pedido,
        )) as RespostaVerificar | undefined;

        if (!resposta) throw new Error("sem resposta do background");
        if (!resposta.ok) mostrarErro(painel, resposta.erro);
        else mostrarVeredito(painel, resposta.veredito, trecho);
      } catch (e: unknown) {
        mostrarErro(painel, String((e as Error)?.message ?? e));
      }
    });

    painel.addEventListener("click", (e) => {
      const alvo = e.target as HTMLElement;
      if (alvo.classList.contains("vc-fechar")) painel.hidden = true;
    });
  },
});

// ---------------------------------------------------------------------------

function cabecalho(rotulo: string, cor: string): string {
  return `
    <div class="vc-topo">
      <span class="vc-badge" style="background:${cor}">${rotulo}</span>
      <button class="vc-fechar" title="Fechar">&times;</button>
    </div>`;
}

function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function recorte(trecho: string): string {
  const t = trecho.length > 180 ? trecho.slice(0, 180) + "…" : trecho;
  return `<p class="vc-trecho">“${esc(t)}”</p>`;
}

function mostrarCarregando(painel: HTMLElement, trecho: string) {
  painel.innerHTML =
    cabecalho("Verificando…", "#57606a") +
    recorte(trecho) +
    `<p class="vc-just">Consultando o back-end…</p>`;
  painel.hidden = false;
}

function mostrarErro(painel: HTMLElement, erro: string) {
  const { texto, cor } = ROTULOS.erro;
  painel.innerHTML =
    cabecalho(texto, cor) + `<p class="vc-just">${esc(erro)}</p>`;
  painel.hidden = false;
}

function mostrarVeredito(
  painel: HTMLElement,
  v: Veredito,
  trecho: string,
) {
  const { texto, cor } = rotulo(v.estado);

  const estudo = v.estudo
    ? `<div class="vc-estudo">
         <strong>${esc(v.estudo.titulo)}</strong>
         <span class="vc-meta">${v.estudo.ano ?? "s/ ano"}${
           v.estudo.doi ? " · doi:" + esc(v.estudo.doi) : ""
         }${v.estudo.retratado ? " · ⚠ RETRATADO" : ""}</span>
       </div>`
    : "";

  const termos = v.termos?.length
    ? `<div class="vc-termos">${v.termos
        .map((t) => `<span>${esc(t)}</span>`)
        .join("")}</div>`
    : "";

  painel.innerHTML =
    cabecalho(texto, cor) +
    recorte(trecho) +
    `<p class="vc-just">${esc(v.justificativa)}</p>` +
    estudo +
    termos;
  painel.hidden = false;
}

function estilos(): HTMLStyleElement {
  const s = document.createElement("style");
  s.textContent = `
    :host { all: initial; }
    .vc-botao, .vc-painel {
      position: fixed;
      z-index: 2147483647;
      font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2328;
    }
    .vc-botao {
      padding: 6px 12px;
      border: 0;
      border-radius: 999px;
      background: #0969da;
      color: #fff;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(0,0,0,.28);
    }
    .vc-botao:hover { background: #0860c4; }
    .vc-painel {
      right: 16px;
      bottom: 16px;
      width: 340px;
      max-height: 60vh;
      overflow: auto;
      padding: 12px 14px 14px;
      background: #fff;
      border: 1px solid #d0d7de;
      border-radius: 10px;
      box-shadow: 0 8px 28px rgba(0,0,0,.22);
    }
    .vc-topo { display: flex; align-items: center; justify-content: space-between; }
    .vc-badge {
      color: #fff; font-weight: 700; font-size: 11px;
      letter-spacing: .04em; text-transform: uppercase;
      padding: 3px 8px; border-radius: 999px;
    }
    .vc-fechar {
      border: 0; background: transparent; cursor: pointer;
      font-size: 18px; line-height: 1; color: #57606a; padding: 0 2px;
    }
    .vc-trecho {
      margin: 10px 0 8px; color: #57606a; font-style: italic;
      border-left: 3px solid #d0d7de; padding-left: 8px;
    }
    .vc-just { margin: 8px 0; }
    .vc-estudo {
      margin-top: 10px; padding-top: 10px; border-top: 1px solid #eaeef2;
      display: flex; flex-direction: column; gap: 3px;
    }
    .vc-meta { color: #57606a; font-size: 12px; }
    .vc-termos { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 5px; }
    .vc-termos span {
      background: #eaeef2; border-radius: 999px; padding: 2px 8px; font-size: 11px;
    }
  `;
  return s;
}
