import assert from "node:assert/strict";
import test from "node:test";

import { criarRequisicoes } from "../.test-dist/requisicoes.js";

const pedido = {
  tipo: "verificar",
  id: "tentativa-1",
  trecho: "texto selecionado",
  url: "https://materia.example",
};

test("cancelamento aborta o fetch e retorna código cancelada", async () => {
  let sinal;
  const respostas = [];
  const buscar = (_url, opcoes) => {
    sinal = opcoes.signal;
    return new Promise((_resolve, reject) => {
      sinal.addEventListener("abort", () => reject(new DOMException("Abortada", "AbortError")));
    });
  };
  const cliente = criarRequisicoes({ verificar: "https://api.example/verificar", feedback: "https://api.example/feedback" }, buscar);
  cliente.verificar(pedido, (resposta) => respostas.push(resposta));
  cliente.cancelar({ tipo: "cancelar", id: pedido.id });
  await new Promise(setImmediate);
  assert.equal(sinal.aborted, true);
  assert.deepEqual(respostas, [{ ok: false, codigo: "cancelada" }]);
});

test("erro HTTP preserva só o código conhecido, sem expor detalhe cru", async () => {
  const respostas = [];
  const cliente = criarRequisicoes({ verificar: "https://api.example/verificar", feedback: "https://api.example/feedback" }, async () => ({
    ok: false,
    status: 429,
    headers: new Headers({ "X-Correlation-ID": "id-servidor" }),
    json: async () => ({ codigo: "limite_excedido", mensagem: "detalhe privado" }),
  }));
  cliente.verificar(pedido, (resposta) => respostas.push(resposta));
  await new Promise(setImmediate);
  assert.deepEqual(respostas, [{ ok: false, codigo: "limite_excedido" }]);
});

test("enviarFeedback faz POST em fire-and-forget", async () => {
  let urlChamada, corpoChamado;
  const buscar = async (url, opcoes) => {
    urlChamada = url;
    corpoChamado = JSON.parse(opcoes.body);
    return { ok: true };
  };
  const cliente = criarRequisicoes({ verificar: "...", feedback: "https://api.example/feedback" }, buscar);
  cliente.enviarFeedback(123, true);
  await new Promise(setImmediate);
  assert.equal(urlChamada, "https://api.example/feedback");
  assert.equal(corpoChamado.veredicto_id, 123);
  assert.equal(corpoChamado.util, true);
  assert.ok(typeof corpoChamado.data_hora === "string");
});
