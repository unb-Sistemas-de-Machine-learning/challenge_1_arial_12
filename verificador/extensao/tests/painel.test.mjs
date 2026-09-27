import assert from "node:assert/strict";
import test from "node:test";

import { codigoErroApi, mensagemDeErro, MENSAGENS_ERRO } from "../.test-dist/mensagens-erro.js";
import { htmlErro, htmlVeredito, urlDoDoi } from "../.test-dist/painel.js";

const base = {
  estado: "exagera",
  estudo: { titulo: "Estudo teste", ano: 2024, doi: "10.1000/teste", retratado: false },
  termos: ["pesquisa"],
  justificativa: "A alegação exagera o resultado.",
};

test("DOI vira link seguro para nova aba", () => {
  const html = htmlVeredito(base, "trecho selecionado");
  assert.match(html, /href="https:\/\/doi\.org\/10\.1000\/teste"/);
  assert.match(html, /target="_blank" rel="noopener noreferrer"/);
  assert.equal(urlDoDoi("10.1000/a?b#c"), "https://doi.org/10.1000/a%3Fb%23c");
});

test("sem estudo não há bloco vazio nem null", () => {
  const html = htmlVeredito(
    { ...base, estado: "nada_encontrado", estudo: null, termos: [] },
    "trecho",
  );
  assert.match(html, /Nada encontrado/);
  assert.doesNotMatch(html, /vc-estudo|vc-doi|\bnull\b/);
});

test("retratação aparece separada do badge e texto externo é escapado", () => {
  const html = htmlVeredito(
    {
      ...base,
      estudo: { ...base.estudo, titulo: "<script>alert(1)</script>", retratado: true },
    },
    "<img src=x>",
  );
  assert.match(html, /vc-retratacao.*Estudo retratado/);
  assert.match(html, /vc-badge--exagera/);
  assert.doesNotMatch(html, /<script>|<img/);
  assert.match(html, /&lt;script&gt;/);
});

test("três estados têm rótulo textual e classes de cor distintas", () => {
  for (const [estado, texto] of [
    ["sustenta", "Sustenta"],
    ["exagera", "Exagera"],
    ["nada_encontrado", "Nada encontrado"],
  ]) {
    assert.match(htmlVeredito({ ...base, estado }, "trecho"), new RegExp(`vc-badge--${estado}[^>]*>${texto}`));
  }
});

test("todos os códigos públicos têm mensagem amigável; desconhecido é genérico", () => {
  const codigos = [
    "entrada_invalida", "limite_excedido", "openalex_indisponivel", "llm_timeout",
    "recurso_nao_encontrado", "metodo_nao_permitido", "erro_requisicao",
    "servico_indisponivel", "erro_interno",
  ];
  for (const codigo of codigos) {
    assert.equal(codigoErroApi(codigo), codigo);
    assert.ok(mensagemDeErro(codigo).length > 10);
    assert.doesNotMatch(htmlErro(codigo), /localhost|stack|8000/);
  }
  assert.equal(codigoErroApi("falha_rede"), null);
  assert.equal(mensagemDeErro("codigo_novo"), MENSAGENS_ERRO.erro_interno);
  assert.match(htmlErro("falha_rede"), /Tentar novamente/);
  assert.doesNotMatch(htmlErro("erro_interno"), /Tentar novamente/);
});
