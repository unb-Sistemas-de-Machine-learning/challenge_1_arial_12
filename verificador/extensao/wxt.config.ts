import { defineConfig } from "wxt";

export default defineConfig({
  // manifest como funcao: cada navegador recebe so as chaves que entende.
  manifest: ({ browser }) => ({
    name: "Verificador Cientifico",
    description:
      "Seleciona um trecho de uma materia e verifica se ha estudo publicado por tras.",
    // O service worker (Chrome) / background script (Firefox) precisa alcancar
    // o back-end local. O content script NAO faz fetch — ver entrypoints/.
    host_permissions: ["http://localhost:8000/*", "http://127.0.0.1:8000/*"],
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
      "file:///Users/cadum/Documents/UnB/SML/challenge_1_arial_12/verificador/pagina-teste.html",
      "https://pt.wikipedia.org/wiki/Medula_espinhal",
    ],
  },
});
