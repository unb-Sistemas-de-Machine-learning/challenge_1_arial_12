import type { Estado, Veredito } from "./tipos.ts";
import { mensagemDeErro } from "./mensagens-erro.ts";

const ROTULOS: Record<Estado, string> = {
  sustenta: "Sustenta",
  exagera: "Exagera",
  nada_encontrado: "Nada encontrado",
};

function esc(valor: string): string {
  return valor.replace(/[&<>"']/g, (caractere) => {
    const entidades: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entidades[caractere] ?? caractere;
  });
}

function cabecalho(texto: string, classe: string): string {
  return `<div class="vc-topo">
    <span class="vc-badge vc-badge--${classe}">${esc(texto)}</span>
    <button type="button" class="vc-fechar" aria-label="Fechar painel" title="Fechar">&times;</button>
  </div>`;
}

function recorte(trecho: string): string {
  const texto = trecho.length > 180 ? `${trecho.slice(0, 180)}…` : trecho;
  return `<p class="vc-trecho">“${esc(texto)}”</p>`;
}

export function urlDoDoi(doi: string): string {
  return `https://doi.org/${encodeURIComponent(doi.trim()).replace(/%2F/gi, "/")}`;
}

export function htmlCarregando(trecho: string): string {
  return (
    cabecalho("Verificando…", "carregando") +
    recorte(trecho) +
    '<p class="vc-just" role="status">Consultando os estudos…</p>'
  );
}

export function htmlErro(codigo: unknown): string {
  const repetir =
    codigo === "falha_rede"
      ? '<button type="button" class="vc-repetir">Tentar novamente</button>'
      : "";
  return (
    cabecalho("Erro", "erro") +
    `<p class="vc-just" role="alert">${esc(mensagemDeErro(codigo))}</p>` +
    repetir
  );
}

export function htmlVeredito(veredito: Veredito, trecho: string): string {
  const estado = veredito.estado;
  const rotulo = ROTULOS[estado] ?? "Erro";
  const classe = Object.hasOwn(ROTULOS, estado) ? estado : "erro";
  const estudo = veredito.estudo;
  let fonte = "";

  if (estudo) {
    const ano = estudo.ano == null ? "Ano não informado" : String(estudo.ano);
    const doi = estudo.doi?.trim();
    const link = doi
      ? `<a class="vc-doi" href="${esc(urlDoDoi(doi))}" target="_blank" rel="noopener noreferrer">Abrir publicação (DOI: ${esc(doi)})</a>`
      : "";
    const retratacao = estudo.retratado
      ? '<p class="vc-retratacao" role="note">⚠ Estudo retratado — confira a publicação antes de utilizar esta fonte.</p>'
      : "";
    fonte = `<section class="vc-estudo" aria-label="Estudo citado">
      <strong>${esc(estudo.titulo)}</strong>
      <span class="vc-meta">${esc(ano)}</span>
      ${link}${retratacao}
    </section>`;
  }

  const termos = veredito.termos.length
    ? `<div class="vc-termos" aria-label="Termos relacionados">${veredito.termos
        .map((termo) => `<span>${esc(termo)}</span>`)
        .join("")}</div>`
    : "";

  return (
    cabecalho(rotulo, classe) +
    recorte(trecho) +
    `<p class="vc-just">${esc(veredito.justificativa)}</p>` +
    fonte +
    termos
  );
}
