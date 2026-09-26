/** Contrato JSON compartilhado entre a extensao e o back-end (Fase 01+). */

export type Estado = "sustenta" | "exagera" | "nada_encontrado";

export interface Estudo {
  titulo: string;
  ano: number | null;
  doi: string | null;
  retratado: boolean;
}

export interface Veredito {
  estado: Estado;
  estudo: Estudo | null;
  termos: string[];
  justificativa: string;
}

/** Códigos públicos de erro do gateway. */
export type CodigoErroApi =
  | "entrada_invalida"
  | "limite_excedido"
  | "openalex_indisponivel"
  | "llm_timeout"
  | "recurso_nao_encontrado"
  | "metodo_nao_permitido"
  | "erro_requisicao"
  | "servico_indisponivel"
  | "erro_interno";

export interface ErroApi {
  codigo: CodigoErroApi;
  mensagem: string;
}

/** Mensagem content script -> background. */
export interface PedidoVerificar {
  tipo: "verificar";
  id: string;
  trecho: string;
  url: string;
}

export interface PedidoCancelar {
  tipo: "cancelar";
  id: string;
}

export type CodigoErroExtensao = CodigoErroApi | "falha_rede" | "cancelada";

/** Resposta background -> content script: ou o veredito, ou um erro. */
export type RespostaVerificar =
  | { ok: true; veredito: Veredito }
  | { ok: false; codigo: CodigoErroExtensao };
