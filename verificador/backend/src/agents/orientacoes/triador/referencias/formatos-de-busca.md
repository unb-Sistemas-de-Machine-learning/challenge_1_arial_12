# Formatos de busca (a metade determinística)

Este arquivo documenta o que o **código** faz com os termos do variador
semântico. Ele não vai no prompt: é leitura de quem mantém `EIXOS` em
`src/agents/triador.py`, e o lugar onde se discute recall antes de mexer no
prompt.

## Por que a montagem é código

A busca da OpenAlex (`title_and_abstract.search`) exige **todas** as palavras da
string, então cada palavra a mais estreita o resultado. A cobertura vem de rodar
várias strings, não de escrever uma string esperta — e "várias strings" é
exatamente o tipo de decisão que não pode mudar a cada chamada. Com os eixos
fixos, dois trechos iguais produzem as mesmas buscas, na mesma ordem, hoje e no
mês que vem.

## Os eixos

Cada eixo é uma combinação fixa de campos. Um eixo só é emitido quando **todos**
os campos que ele pede estão preenchidos, e três regras cortam o que sobra:

- **palavra repetida entre campos aparece uma vez só.** A condição `malaria` com
  a intervenção `malaria vaccine` daria `malaria malaria vaccine`, e a busca
  exige cada palavra uma vez.
- **dois eixos com o mesmo conjunto de palavras valem como um.** A comparação é
  por conjunto, e não pela string: a busca é a conjunção dos termos, então duas
  ordens das mesmas palavras gastariam duas requisições para trazer o mesmo
  resultado.
- **busca de uma palavra só é descartada.** Ela devolve a literatura inteira da
  área e não verifica alegação nenhuma. Acontece quando dois campos do eixo
  caem no mesmo termo canônico — `depression` como condição e `depressive
  symptoms` como desfecho, que o glossário unifica.

Por isso o número de buscas varia de trecho para trecho (de zero a seis) sem que
a montagem deixe de ser determinística: o que varia é quantos campos o trecho
rendeu, não a decisão do código.

| # | `id` | Campos | Para que serve |
| :-- | :--- | :--- | :--- |
| 1 | `completo` | condição + intervenção + desfecho | a mais precisa: o primeiro colocado dela é o mais provável de ser o estudo certo |
| 2 | `nucleo` | intervenção + desfecho | a alegação nua; é a que mais recupera |
| 3 | `sinonimo` | variante da intervenção + desfecho | cobre o artigo que chama a intervenção por outro nome |
| 4 | `condicao_intervencao` | condição + intervenção | cobre o artigo que mede outro desfecho da mesma relação |
| 5 | `condicao_desfecho` | condição + desfecho | cobre o artigo que chega ao mesmo desfecho por outra intervenção |
| 6 | `populacao` | intervenção + desfecho + população | separa o estudo em humanos do estudo em animais |

Os eixos 2, 4 e 5 esgotam os três pares possíveis entre condição, intervenção e
desfecho. É por isso que **dois** campos preenchidos entre os três já garantem
pelo menos uma busca, e um campo só não garante nenhuma.

A ordem da tabela é a ordem em que as strings saem, e ela importa: a OpenAlex é
consultada em paralelo e `ClienteOpenAlex.buscar_varias` intercala os resultados
por posição — o primeiro colocado do eixo 1, depois o do eixo 2, e assim por
diante. Mudar a ordem muda quais cinco trabalhos chegam ao Juiz.

## O eixo `sinonimo`

A variante vem do glossário, e não do modelo: é a **primeira** da terceira
coluna da linha correspondente (veja `glossario.md`). Se a intervenção não
estiver no glossário, o eixo tenta a variante do desfecho; se nenhum dos dois
estiver, o eixo não é emitido.

A diversidade de vocabulário da busca, portanto, é editada à mão, numa tabela
versionada — e não sorteada a cada chamada.

## Antes e depois da montagem

O código, em `src/agents/triador.py`:

1. **normaliza** cada campo (minúsculas, NFC, apóstrofo removido, pontuação
   virando espaço, conectivo descartado, espaços colapsados, teto de 5
   palavras);
2. **aplica o glossário**, reescrevendo variante e termo em português para o
   termo canônico;
3. **monta** os eixos na ordem da tabela, descartando repetição;
4. **põe o trecho original na frente** da lista, sempre — é o chão
   determinístico da busca e o que sobra quando o LLM não responde;
5. **corta** a lista em `max_variacoes + 1` e descarta string acima de
   `max_tamanho_variacao` caracteres.

Nenhum desses passos consulta o modelo. Um trecho com os mesmos termos extraídos
produz byte a byte a mesma lista.

## Para mexer nos eixos

Mexer aqui é mexer em recall, então o caminho é o mesmo de qualquer mudança de
prompt: rode `scripts/eval_triador.py --repeticoes 3` antes, mexa, rode depois.
Eixo novo custa uma requisição por verificação para todo mundo — o teto está em
`MAXIMO_DE_BUSCAS`, em `src/services/openalex.py`.
