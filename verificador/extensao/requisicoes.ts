import type {
  PedidoCancelar,
  PedidoVerificar,
  RespostaVerificar,
} from "./tipos.ts";
import { codigoErroApi } from "./mensagens-erro.ts";

/** Mantém um AbortController por tentativa para o fechamento do painel. */
export function criarRequisicoes(
  endpoint: string,
  buscar: typeof fetch = fetch,
  registrarErro: (status: number, correlacao: string | null) => void = () => {},
) {
  const ativas = new Map<string, AbortController>();

  function cancelar(pedido: PedidoCancelar): void {
    ativas.get(pedido.id)?.abort();
  }

  function verificar(
    pedido: PedidoVerificar,
    responder: (resposta: RespostaVerificar) => void,
  ): void {
    const controlador = new AbortController();
    ativas.set(pedido.id, controlador);
    void buscar(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trecho: pedido.trecho, url: pedido.url }),
      signal: controlador.signal,
    })
      .then(async (resposta) => {
        if (controlador.signal.aborted) {
          responder({ ok: false, codigo: "cancelada" });
          return;
        }
        if (!resposta.ok) {
          let corpo: unknown;
          try {
            corpo = (await resposta.json()) as unknown;
          } catch {
            corpo = null;
          }
          if (controlador.signal.aborted) {
            responder({ ok: false, codigo: "cancelada" });
            return;
          }
          const codigo =
            typeof corpo === "object" && corpo !== null && "codigo" in corpo
              ? codigoErroApi(corpo.codigo)
              : null;
          registrarErro(resposta.status, resposta.headers.get("X-Correlation-ID"));
          responder({ ok: false, codigo: codigo ?? "erro_interno" });
          return;
        }
        const veredito = await resposta.json();
        if (controlador.signal.aborted) {
          responder({ ok: false, codigo: "cancelada" });
        } else {
          responder({ ok: true, veredito });
        }
      })
      .catch((erro: unknown) => {
        if (controlador.signal.aborted) {
          responder({ ok: false, codigo: "cancelada" });
          return;
        }
        console.error("[verificador] falhou:", erro);
        responder({ ok: false, codigo: "falha_rede" });
      })
      .finally(() => {
        if (ativas.get(pedido.id) === controlador) ativas.delete(pedido.id);
      });
  }

  return { verificar, cancelar };
}
