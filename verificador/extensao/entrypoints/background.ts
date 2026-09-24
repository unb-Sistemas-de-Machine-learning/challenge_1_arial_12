import { defineBackground } from "wxt/utils/define-background";
import { browser } from "wxt/browser";
import type { CodigoErroApi, PedidoVerificar, RespostaVerificar } from "../tipos";

const ENDPOINT = "http://localhost:8000/verificar";

const MENSAGENS_ERRO: Record<CodigoErroApi, string> = {
  entrada_invalida: "Revise o texto selecionado e tente novamente.",
  limite_excedido: "Muitas solicitações. Aguarde um pouco e tente novamente.",
  openalex_indisponivel:
    "A busca de estudos está indisponível. Tente novamente mais tarde.",
  llm_timeout: "A análise demorou demais. Tente novamente.",
  recurso_nao_encontrado: "Serviço não encontrado.",
  metodo_nao_permitido: "Esta operação não está disponível.",
  erro_requisicao: "Não foi possível processar a solicitação.",
  servico_indisponivel: "Serviço indisponível. Tente novamente mais tarde.",
  erro_interno: "Não foi possível concluir a verificação agora.",
};

function mensagemDeErro(codigo: unknown): string {
  if (
    typeof codigo === "string" &&
    Object.prototype.hasOwnProperty.call(MENSAGENS_ERRO, codigo)
  ) {
    return MENSAGENS_ERRO[codigo as CodigoErroApi];
  }
  return "Não foi possível concluir a verificação agora.";
}

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
          if (!r.ok) {
            let corpo: unknown;
            try {
              corpo = (await r.json()) as unknown;
            } catch {
              corpo = null;
            }
            const codigo =
              typeof corpo === "object" && corpo !== null && "codigo" in corpo
                ? corpo.codigo
                : null;
            console.warn(
              "[verificador] erro HTTP:",
              r.status,
              "correlation_id:",
              r.headers.get("X-Correlation-ID"),
            );
            sendResponse({ ok: false, erro: mensagemDeErro(codigo) });
            return;
          }
          sendResponse({ ok: true, veredito: await r.json() });
        })
        .catch((e) => {
          console.error("[verificador] falhou:", e);
          sendResponse({
            ok: false,
            erro: "Não foi possível conectar ao servidor. Tente novamente.",
          });
        });

      // Obrigatorio: mantem o canal aberto ate o sendResponse assincrono.
      return true;
    },
  );
});
