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
  const cliente = criarRequisicoes("https://api.example/verificar", buscar);
  cliente.verificar(pedido, (resposta) => respostas.push(resposta));
  cliente.cancelar({ tipo: "cancelar", id: pedido.id });
  await new Promise(setImmediate);
  assert.equal(sinal.aborted, true);
  assert.deepEqual(respostas, [{ ok: false, codigo: "cancelada" }]);
});

test("erro HTTP preserva só o código conhecido, sem expor detalhe cru", async () => {
  const respostas = [];
  const cliente = criarRequisicoes("https://api.example/verificar", async () => ({
    ok: false,
    status: 429,
    headers: new Headers({ "X-Correlation-ID": "id-servidor" }),
    json: async () => ({ codigo: "limite_excedido", mensagem: "detalhe privado" }),
  }));
  cliente.verificar(pedido, (resposta) => respostas.push(resposta));
  await new Promise(setImmediate);
  assert.deepEqual(respostas, [{ ok: false, codigo: "limite_excedido" }]);
});
