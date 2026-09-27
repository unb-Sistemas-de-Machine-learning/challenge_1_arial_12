import type { CodigoErroApi, CodigoErroExtensao } from "./tipos.ts";

/** Texto da interface: nunca usar a mensagem arbitrária recebida da API. */
export const MENSAGENS_ERRO = {
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
  falha_rede: "Não foi possível conectar ao servidor. Tente novamente.",
  cancelada: "Verificação cancelada.",
} satisfies Record<CodigoErroExtensao, string>;

export function codigoErroApi(valor: unknown): CodigoErroApi | null {
  if (
    typeof valor === "string" &&
    Object.prototype.hasOwnProperty.call(MENSAGENS_ERRO, valor) &&
    valor !== "falha_rede" &&
    valor !== "cancelada"
  ) {
    return valor as CodigoErroApi;
  }
  return null;
}

export function mensagemDeErro(codigo: unknown): string {
  if (
    typeof codigo === "string" &&
    Object.prototype.hasOwnProperty.call(MENSAGENS_ERRO, codigo)
  ) {
    return MENSAGENS_ERRO[codigo as CodigoErroExtensao];
  }
  return MENSAGENS_ERRO.erro_interno;
}
