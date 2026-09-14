#!/usr/bin/env bash
# Empacota a extensao para o Safari. Exige o Xcode completo instalado.
#
#   ./scripts/safari.sh converter    # 1x: gera o projeto Xcode em ../safari/
#   ./scripts/safari.sh sincronizar  # a cada mudanca: copia o build novo
#
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SAIDA="$RAIZ/.output/chrome-mv3"
PROJETO="$RAIZ/../safari"
APP="Verificador Cientifico"

exigir_xcode() {
  if ! xcrun --find safari-web-extension-converter >/dev/null 2>&1; then
    echo "ERRO: o Xcode completo nao esta instalado (ou nao esta selecionado)."
    echo "  1. Instale o Xcode pela App Store"
    echo "  2. sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
    exit 1
  fi
}

# O Safari 16.4+ roda MV3, entao convertemos o build do Chrome —
# nao o alvo safari-mv2 do WXT, que ja nasce depreciado.
construir() {
  ( cd "$RAIZ" && npm run build )
}

case "${1:-}" in
  converter)
    exigir_xcode
    construir
    rm -rf "$PROJETO"
    xcrun safari-web-extension-converter "$SAIDA" \
      --project-location "$PROJETO" \
      --app-name "$APP" \
      --bundle-identifier "br.unb.sml.verificador" \
      --macos-only \
      --no-open \
      --no-prompt
    echo
    echo "Projeto gerado em: $PROJETO"
    echo "Abra o .xcodeproj, ajuste Signing Team, e rode com Cmd+R."
    ;;

  sincronizar)
    construir
    RES="$(find "$PROJETO" -type d -name Resources -path "*Extension*" | head -1)"
    [ -n "$RES" ] || { echo "ERRO: rode './scripts/safari.sh converter' primeiro."; exit 1; }
    rsync -a --delete "$SAIDA"/ "$RES"/
    echo "Recursos atualizados em: $RES"
    echo "Volte ao Xcode e rode Cmd+R para recarregar."
    ;;

  *)
    sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
