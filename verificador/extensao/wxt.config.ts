import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { defineConfig } from "wxt";
import { permissoesDeHost } from "./config";

// Caminho da pagina de teste resolvido a partir DESTE arquivo, nao da maquina
// de quem clonou: extensao/wxt.config.ts -> ../pagina-teste.html.
// pathToFileURL cuida das diferencas de Windows (C:\ -> file:///C:/) e de
// acentos/espacos no caminho do clone.
const diretorioDaExtensao = dirname(fileURLToPath(import.meta.url));
const urlDaPaginaDeTeste = pathToFileURL(
  resolve(diretorioDaExtensao, "..", "pagina-teste.html"),
).href;

export default defineConfig({
  // manifest como funcao: cada navegador recebe so as chaves que entende.
  manifest: ({ browser }) => ({
    name: "Verificador Cientifico",
    description:
      "Seleciona um trecho de uma materia e verifica se ha estudo publicado por tras.",
    // O service worker (Chrome) / background script (Firefox) precisa alcancar
    // o back-end. O content script NAO faz fetch — ver entrypoints/.
    // A lista sai da mesma WXT_API_BASE_URL que o background usa (config.ts):
    // o build nunca pede permissao para um host que ele nao vai chamar.
    host_permissions: permissoesDeHost(),
    ...(browser === "firefox"
      ? {
          // Declara que a extensao nao coleta dados do usuario.
          data_collection_permissions: { required: ["none"] },
          // O Firefox exige um id estavel para instalar temporariamente.
          browser_specific_settings: {
            gecko: {
              id: "verificador-cientifico@unb.local",
              strict_min_version: "115.0",
            },
          },
        }
      : {}),
  }),

  // O aviso e falso-positivo: o manifest do Firefox ja declara
  // data_collection_permissions logo acima.
  suppressWarnings: { firefoxDataCollection: true },

  // Abre direto a pagina de teste local ao rodar `npm run dev`.
  webExt: {
    startUrls: [
      urlDaPaginaDeTeste,
      "https://pt.wikipedia.org/wiki/Medula_espinhal",
    ],
  },
});
