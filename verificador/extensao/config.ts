/**
 * Endereco do back-end em um lugar so: a base vem do ambiente no momento do
 * build, as rotas sao fixas.
 *
 *   npm run build                                          -> localhost:8000
 *   WXT_API_BASE_URL=https://api.exemplo.com npm run build -> api.exemplo.com
 *
 * O prefixo WXT_ nao e decorativo: so variaveis com ele (ou VITE_) chegam ao
 * codigo empacotado. Ver "Apontar o build para outro back-end" no README.
 */

/** Back-end local: o padrao de desenvolvimento, quando nao ha variavel. */
export const BASE_PADRAO = "http://localhost:8000";

/** Caminhos servidos pelo back-end (backend/src/api/gateway/routes.py). */
export const ROTAS = {
  verificar: "/verificar",
  health: "/health",
} as const;

export type Rota = (typeof ROTAS)[keyof typeof ROTAS];

/**
 * A variavel chega por dois caminhos porque este modulo e lido dos dois lados
 * do build: nos entrypoints o Vite troca `import.meta.env.WXT_API_BASE_URL`
 * pelo literal; no `wxt.config.ts`, que roda em Node, ela vem do processo — o
 * WXT carrega os arquivos `.env` antes de montar o manifest.
 *
 * A leitura e preguicosa de proposito: em Node, um valor lido na importacao
 * chegaria antes dos arquivos `.env`, e o manifest apontaria para um host
 * diferente do que o background chama.
 */
function doAmbiente(): string | undefined {
  try {
    const empacotada = import.meta.env.WXT_API_BASE_URL as string | undefined;
    if (empacotada) return empacotada;
  } catch {
    // Node puro: `import.meta.env` nao existe.
  }
  if (typeof process === "undefined") return undefined;
  return process.env.WXT_API_BASE_URL;
}

/**
 * Normaliza a base: sem valor, vale o padrao. Valor quebrado derruba o build —
 * melhor errar aqui do que empacotar uma extensao que so falha no primeiro
 * fetch do usuario.
 */
export function resolverBase(valor?: string | null): string {
  const bruto = valor?.trim();
  if (!bruto) return BASE_PADRAO;

  let url: URL;
  try {
    url = new URL(bruto);
  } catch {
    throw new Error(`WXT_API_BASE_URL nao e uma URL absoluta: "${bruto}"`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`WXT_API_BASE_URL precisa usar http ou https: "${bruto}"`);
  }
  if (url.search !== "" || url.hash !== "") {
    throw new Error(
      `WXT_API_BASE_URL nao aceita query nem fragmento: "${bruto}"`,
    );
  }
  // As rotas ja comecam com "/", entao a base nunca termina com uma.
  return url.href.replace(/\/+$/, "");
}

/** Base do back-end deste build. */
export function baseDaApi(): string {
  return resolverBase(doAmbiente());
}

/** URL absoluta de uma rota do back-end. */
export function urlDaRota(rota: Rota, base: string = baseDaApi()): string {
  return `${base}${rota}`;
}

/**
 * `host_permissions` derivadas da mesma base: o manifest pede o host que este
 * build realmente chama, e nenhum outro. O padrao cobre qualquer caminho da
 * origem, porque todas as rotas ficam sob ela.
 */
export function permissoesDeHost(base: string = baseDaApi()): string[] {
  return [`${new URL(base).origin}/*`];
}
