import type {
  CodigoErroExtensao,
  PedidoCancelar,
  PedidoVerificar,
  RespostaVerificar,
  Veredito,
} from "./tipos.ts";

export interface AcoesPainel {
  carregando(trecho: string): void;
  veredito(valor: Veredito, trecho: string): void;
  erro(codigo: CodigoErroExtensao): void;
}

type Enviar = (pedido: PedidoVerificar) => Promise<RespostaVerificar | undefined>;
type Cancelar = (pedido: PedidoCancelar) => void;

/** Coordena uma tentativa ativa; uma resposta antiga nunca altera o painel. */
export function criarControleVerificacao(
  enviar: Enviar,
  cancelar: Cancelar,
  acoes: AcoesPainel,
  novoId: () => string = () => crypto.randomUUID(),
) {
  let atual: { id: string; trecho: string; url: string; pendente: boolean } | null =
    null;
  let podeRepetir = false;

  function invalidarAtual(): void {
    if (atual?.pendente) cancelar({ tipo: "cancelar", id: atual.id });
    atual = null;
    podeRepetir = false;
  }

  function verificar(trecho: string, url: string): void {
    invalidarAtual();
    const id = novoId();
    atual = { id, trecho, url, pendente: true };
    acoes.carregando(trecho);

    void enviar({ tipo: "verificar", id, trecho, url })
      .then((resposta) => {
        if (atual?.id !== id) return;
        atual.pendente = false;
        if (!resposta) {
          podeRepetir = true;
          acoes.erro("falha_rede");
        } else if (resposta.ok) {
          podeRepetir = false;
          acoes.veredito(resposta.veredito, trecho);
        } else if (resposta.codigo !== "cancelada") {
          podeRepetir = resposta.codigo === "falha_rede";
          acoes.erro(resposta.codigo);
        }
      })
      .catch(() => {
        if (atual?.id !== id) return;
        atual.pendente = false;
        podeRepetir = true;
        acoes.erro("falha_rede");
      });
  }

  function repetir(): void {
    if (atual && podeRepetir) verificar(atual.trecho, atual.url);
  }

  return { verificar, repetir, fechar: invalidarAtual };
}
