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

/** Mensagem content script -> background. */
export interface PedidoVerificar {
  tipo: "verificar";
  trecho: string;
  url: string;
}

/** Resposta background -> content script: ou o veredito, ou um erro. */
export type RespostaVerificar =
  | { ok: true; veredito: Veredito }
  | { ok: false; erro: string };
