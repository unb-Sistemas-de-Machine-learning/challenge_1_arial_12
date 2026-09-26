# Tarefas — 015 Painel de veredicto

- [x] Registrar seção de interface na spec 015 (a spec 001 não existe neste repositório).
- [x] Extrair mapa de códigos de erro para módulo próprio.
- [x] Renderizar DOI clicável, estudo ausente e aviso de retratação.
- [x] Aplicar paleta oficial e rótulos textuais aos três estados.
- [x] Implementar retry do mesmo trecho e URL após falha de rede.
- [x] Cancelar o `fetch` ao fechar e ignorar respostas atrasadas.
- [x] Escrever e executar testes automatizados; compilar e gerar builds.
- [x] Atualizar roteiro manual do README.
- [x] Validar no Chrome o fluxo principal: `exagera`, link do DOI, erro de rede e retry do mesmo trecho. Fluxo aprovado pelo usuário com evidências visuais.
- [x] Evidenciar no Chrome um veredito (`exagera`) e o estado de erro. Os demais estados foram simulados nos testes automatizados, não em capturas do navegador.
- [ ] Executar roteiro manual no Firefox. Não realizado após a aprovação no Chrome, pois o navegador não está disponível no ambiente; o build Firefox passou.
- [x] Anexar capturas de `sustenta` e `nada_encontrado`, além de validar visualmente a retratação e o cancelamento, caso o critério original da issue seja exigido sem flexibilização.
