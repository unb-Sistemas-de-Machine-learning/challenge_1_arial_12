import { defineContentScript } from "wxt/utils/define-content-script";
import { browser } from "wxt/browser";
import { criarControleVerificacao } from "../controle-verificacao";
import { htmlCarregando, htmlErro, htmlVeredito } from "../painel";
import type { PedidoVerificar, RespostaVerificar } from "../tipos";

export default defineContentScript({
  matches: ["<all_urls>", "file:///*"],
  runAt: "document_idle",

  main() {
    // O shadow root isola o painel do CSS da página.
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
    painel.setAttribute("role", "dialog");
    painel.setAttribute("aria-label", "Resultado da verificação");
    painel.hidden = true;
    shadow.appendChild(painel);

    const controle = criarControleVerificacao(
      (pedido: PedidoVerificar) =>
        browser.runtime.sendMessage(pedido) as Promise<RespostaVerificar | undefined>,
      (pedido) => {
        void browser.runtime.sendMessage(pedido).catch(() => {
          // O painel já está fechado; a invalidação local é suficiente.
        });
      },
      {
        carregando(trecho) {
          painel.innerHTML = htmlCarregando(trecho);
          painel.hidden = false;
        },
        veredito(valor, trecho) {
          painel.innerHTML = htmlVeredito(valor, trecho);
          painel.hidden = false;
        },
        erro(codigo) {
          painel.innerHTML = htmlErro(codigo);
          painel.hidden = false;
        },
      },
    );

    let trechoAtual = "";

    document.addEventListener("mouseup", (evento) => {
      if (evento.composedPath().includes(host)) return;
      setTimeout(() => {
        const selecao = window.getSelection();
        const trecho = selecao?.toString().trim() ?? "";
        if (trecho.length < 10 || !selecao || selecao.rangeCount === 0) {
          botao.hidden = true;
          return;
        }

        trechoAtual = trecho;
        const retangulo = selecao.getRangeAt(0).getBoundingClientRect();
        botao.style.top = `${Math.max(8, retangulo.top - 40)}px`;
        botao.style.left = `${Math.max(8, retangulo.left)}px`;
        botao.hidden = false;
      }, 0);
    });

    document.addEventListener("mousedown", (evento) => {
      if (evento.composedPath().includes(host)) return;
      botao.hidden = true;
    });

    botao.addEventListener("click", () => {
      botao.hidden = true;
      controle.verificar(trechoAtual, location.href);
    });

    painel.addEventListener("click", (evento) => {
      const alvo = evento.target as HTMLElement;
      if (alvo.closest(".vc-fechar")) {
        controle.fechar();
        painel.hidden = true;
      } else if (alvo.closest(".vc-repetir")) {
        controle.repetir();
      }
    });
  },
});

function estilos(): HTMLStyleElement {
  const estilo = document.createElement("style");
  estilo.textContent = `
    :host { all: initial; }
    .vc-botao, .vc-painel {
      position: fixed; z-index: 2147483647;
      font: 13px/1.45 Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1d1d1d;
    }
    .vc-botao, .vc-repetir {
      border: 0; border-radius: 999px; background: #183fff;
      color: #fff; font-weight: 600; cursor: pointer;
    }
    .vc-botao { padding: 6px 12px; box-shadow: 0 2px 8px rgba(0,0,0,.28); }
    .vc-repetir { margin-top: 6px; padding: 7px 12px; }
    .vc-botao:hover, .vc-repetir:hover { background: #1231c9; }
    .vc-botao:focus-visible, .vc-repetir:focus-visible,
    .vc-fechar:focus-visible, .vc-doi:focus-visible {
      outline: 3px solid #183fff; outline-offset: 3px;
    }
    .vc-painel {
      right: 16px; bottom: 16px; width: min(340px, calc(100vw - 60px));
      max-height: 60vh; overflow: auto; padding: 12px 14px 14px;
      background: #fff; border: 1px solid #828282; border-radius: 10px;
      box-shadow: 0 8px 28px rgba(0,0,0,.22);
    }
    .vc-topo { display: flex; align-items: center; justify-content: space-between; }
    .vc-badge {
      color: #1d1d1d; font-weight: 700; font-size: 11px;
      letter-spacing: .04em; text-transform: uppercase;
      padding: 3px 8px; border-radius: 999px;
    }
    .vc-badge--sustenta { background: #27ae60; }
    .vc-badge--exagera { background: #f89a3c; }
    .vc-badge--nada_encontrado { background: #f9d159; }
    .vc-badge--erro { background: #eb5757; }
    .vc-badge--carregando { background: #828282; color: #fff; }
    .vc-fechar {
      border: 0; background: transparent; cursor: pointer;
      font-size: 18px; line-height: 1; color: #1d1d1d; padding: 0 2px;
    }
    .vc-trecho {
      margin: 10px 0 8px; color: #565656; font-style: italic;
      border-left: 3px solid #828282; padding-left: 8px;
    }
    .vc-just { margin: 8px 0; }
    .vc-estudo {
      margin-top: 10px; padding-top: 10px; border-top: 1px solid #d9d9d9;
      display: flex; flex-direction: column; gap: 4px;
    }
    .vc-meta { color: #565656; font-size: 12px; }
    .vc-doi { color: #1231c9; text-decoration: underline; overflow-wrap: anywhere; }
    .vc-retratacao {
      margin: 7px 0 0; padding: 7px 8px;
      border-left: 4px solid #eb5757; background: #fff1f1;
      color: #1d1d1d; font-weight: 600;
    }
    .vc-termos { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 5px; }
    .vc-termos span {
      background: #ededed; border-radius: 999px; padding: 2px 8px; font-size: 11px;
    }
  `;
  return estilo;
}
