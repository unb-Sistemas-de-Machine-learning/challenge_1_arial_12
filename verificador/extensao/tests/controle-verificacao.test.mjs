import assert from "node:assert/strict";
import test from "node:test";

import { criarControleVerificacao } from "../.test-dist/controle-verificacao.js";

function promessaPendente() {
  let resolver;
  const promessa = new Promise((resolve) => { resolver = resolve; });
  return { promessa, resolver };
}

function ambiente() {
  const enviados = [];
  const cancelados = [];
  const eventos = [];
  const pendentes = [];
  let proximo = 0;
  const controle = criarControleVerificacao(
    (pedido) => {
      enviados.push(pedido);
      const item = promessaPendente();
      pendentes.push(item);
      return item.promessa;
    },
    (pedido) => cancelados.push(pedido),
    {
      carregando: (trecho) => eventos.push(["carregando", trecho]),
      veredito: (valor, trecho) => eventos.push(["veredito", valor.estado, trecho]),
      erro: (codigo) => eventos.push(["erro", codigo]),
    },
    () => `id-${++proximo}`,
  );
  return { controle, enviados, cancelados, eventos, pendentes };
}

test("falha de rede permite repetir o mesmo trecho e a mesma URL", async () => {
  const ctx = ambiente();
  ctx.controle.verificar("trecho original", "https://materia.example/1");
  ctx.pendentes[0].resolver({ ok: false, codigo: "falha_rede" });
  await Promise.resolve();
  ctx.controle.repetir();
  assert.deepEqual(ctx.enviados[1], {
    tipo: "verificar", id: "id-2", trecho: "trecho original", url: "https://materia.example/1",
  });
  assert.deepEqual(ctx.eventos.at(-1), ["carregando", "trecho original"]);
});

test("fechar cancela a chamada e resposta atrasada não reabre o painel", async () => {
  const ctx = ambiente();
  ctx.controle.verificar("trecho", "https://materia.example");
  ctx.controle.fechar();
  ctx.pendentes[0].resolver({ ok: true, veredito: { estado: "sustenta" } });
  await Promise.resolve();
  assert.deepEqual(ctx.cancelados, [{ tipo: "cancelar", id: "id-1" }]);
  assert.deepEqual(ctx.eventos, [["carregando", "trecho"]]);
});

test("nova verificação cancela a anterior e ignora resultado antigo", async () => {
  const ctx = ambiente();
  ctx.controle.verificar("primeiro", "https://materia.example/1");
  ctx.controle.verificar("segundo", "https://materia.example/2");
  ctx.pendentes[0].resolver({ ok: false, codigo: "erro_interno" });
  await Promise.resolve();
  assert.deepEqual(ctx.cancelados, [{ tipo: "cancelar", id: "id-1" }]);
  assert.deepEqual(ctx.eventos, [["carregando", "primeiro"], ["carregando", "segundo"]]);
});

test("erro HTTP não oferece retry", async () => {
  const ctx = ambiente();
  ctx.controle.verificar("trecho", "https://materia.example");
  ctx.pendentes[0].resolver({ ok: false, codigo: "limite_excedido" });
  await Promise.resolve();
  ctx.controle.repetir();
  assert.equal(ctx.enviados.length, 1);
  assert.deepEqual(ctx.eventos.at(-1), ["erro", "limite_excedido"]);
});
