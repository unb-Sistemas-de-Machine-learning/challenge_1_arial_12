import { defineBackground } from "wxt/utils/define-background";
import { browser } from "wxt/browser";
import type { PedidoCancelar, PedidoVerificar, RespostaVerificar } from "../tipos";
import { ROTAS, urlDaRota } from "../config";
import { criarRequisicoes } from "../requisicoes";

const ENDPOINT = urlDaRota(ROTAS.verificar);

export default defineBackground(() => {
  console.log("[verificador] background pronto —", ENDPOINT);
  const requisicoes = criarRequisicoes(ENDPOINT, fetch, (status, correlacao) => {
    console.warn("[verificador] erro HTTP:", status, "correlation_id:", correlacao);
  });

  browser.runtime.onMessage.addListener(
    (
      msg: unknown,
      _sender: unknown,
      sendResponse: (resposta: RespostaVerificar) => void,
    ) => {
      if (typeof msg !== "object" || msg === null || !("tipo" in msg)) return;
      if (msg.tipo === "cancelar") {
        const pedido = msg as PedidoCancelar;
        if (typeof pedido.id === "string") requisicoes.cancelar(pedido);
        return;
      }
      if (msg.tipo !== "verificar") return;
      const pedido = msg as PedidoVerificar;
      if (
        typeof pedido.id !== "string" ||
        typeof pedido.trecho !== "string" ||
        typeof pedido.url !== "string"
      ) return;

      requisicoes.verificar(pedido, sendResponse);
      // Mantém o canal aberto até a resposta assíncrona.
      return true;
    },
  );
});
