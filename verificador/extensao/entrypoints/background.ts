import { defineBackground } from "wxt/utils/define-background";
import { browser } from "wxt/browser";
import type { PedidoVerificar, RespostaVerificar } from "../tipos";

const ENDPOINT = "http://localhost:8000/verificar";

export default defineBackground(() => {
  console.log("[verificador] background pronto");

  browser.runtime.onMessage.addListener(
    (
      msg: unknown,
      _sender: unknown,
      sendResponse: (r: RespostaVerificar) => void,
    ) => {
      const pedido = msg as PedidoVerificar;
      if (pedido?.tipo !== "verificar") return;

      console.log("[verificador] pedido:", pedido.trecho.slice(0, 80));

      fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trecho: pedido.trecho, url: pedido.url }),
      })
        .then(async (r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          sendResponse({ ok: true, veredito: await r.json() });
        })
        .catch((e) => {
          console.error("[verificador] falhou:", e);
          sendResponse({
            ok: false,
            erro:
              String(e?.message ?? e) +
              " — o back-end esta rodando em localhost:8000?",
          });
        });

      // Obrigatorio: mantem o canal aberto ate o sendResponse assincrono.
      return true;
    },
  );
});
