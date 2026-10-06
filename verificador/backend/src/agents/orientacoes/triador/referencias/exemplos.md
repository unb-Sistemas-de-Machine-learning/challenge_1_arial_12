# Exemplos resolvidos

Trechos reais e a resposta esperada para cada um. Quando a dúvida não estiver
resolvida nas orientações, siga o exemplo mais parecido.

## 1. O par que sustenta a busca

> "Consumo de álcool está ligado ao encolhimento do cérebro"

```json
{
  "intervencao": "alcohol consumption",
  "desfecho": "brain atrophy",
  "condicao": "",
  "populacao": ""
}
```

Nenhuma doença é nomeada, então `condicao` fica vazio — e o par
intervenção/desfecho basta. Os dois conceitos estão no glossário: `brain
shrinkage` seria uma tradução defensável e **não** é a aceita.

## 2. O trecho cheio de ruído

> "Pesquisadores da Moderna anunciaram em 2024 que a vacina de mRNA reduziu em
> 44% a recorrência do melanoma"

```json
{
  "intervencao": "mrna vaccine",
  "desfecho": "cancer recurrence",
  "condicao": "melanoma",
  "populacao": ""
}
```

Saíram: a empresa (Moderna), o ano (2024), a magnitude (44%) e o verbo de
anúncio. Sobrou a alegação.

## 3. Quando o trecho não dá busca

> "Novo tratamento para o câncer de mama é promissor"

```json
{
  "intervencao": "",
  "desfecho": "",
  "condicao": "breast cancer",
  "populacao": ""
}
```

"Novo tratamento" não nomeia intervenção nenhuma e "promissor" não é desfecho —
inventar `novel therapy` traria qualquer artigo de oncologia. Com um campo só, o
código não monta busca. Essa é a resposta certa: o trecho, como está escrito,
não é verificável.

## 4. Fora da biomedicina

> "Aumento do nível do mar ameaça cidades costeiras"

```json
{
  "intervencao": "sea level rise",
  "desfecho": "coastal flooding",
  "condicao": "",
  "populacao": "coastal cities"
}
```

Não há doença nem paciente: `intervencao` recebe o fenômeno e `desfecho`, o
efeito. "Ameaça" vira o efeito concreto que a literatura mede.

<!-- interno -->

## Exemplos fora do prompt

Leitura de quem mantém o arquivo; não vai ao modelo.

Os três abaixo saíram do prompt na spec 023, quando a janela de 8 mil tokens por
minuto da Groq passou a ser o gargalo da verificação. Cada um repetia uma regra
que as orientações já enunciam por extenso, com o mesmo exemplo — pagar por eles
em toda chamada tirava orçamento da verificação seguinte. Ficam aqui porque a
decisão é reversível: se a qualidade da extração cair nesses três casos, o
caminho de volta é tirá-los deste bloco.

| Caso | Regra que já o cobre |
| :--- | :--- |
| quatro campos preenchidos, `malaria` repetido em dois | regra 8 |
| marca de medicamento (`Oxycontin` → `oxycodone`) | regra 7, com o mesmo exemplo |
| negação ("Café **não** aumenta o risco de arritmia") | regra 9, com o mesmo exemplo |

### Os quatro campos preenchidos

> "Vacina contra a malária reduz mortalidade infantil"

```json
{
  "intervencao": "malaria vaccine",
  "desfecho": "child mortality",
  "condicao": "malaria",
  "populacao": "children"
}
```

`populacao` vem de "infantil", que está no trecho. Note que `malaria` aparece
duas vezes, em campos diferentes: isso é esperado, e os eixos cuidam de não
produzir strings redundantes.

### Marca de medicamento

> "Oxycontin é o principal causador da crise de opioides"

```json
{
  "intervencao": "oxycodone",
  "desfecho": "opioid epidemic",
  "condicao": "opioid use disorder",
  "populacao": ""
}
```

A marca vira o nome genérico. "Principal causador" é a força da alegação, não um
conceito: nada dela entra nos campos.

### Negação

> "Café não aumenta o risco de arritmia"

```json
{
  "intervencao": "coffee consumption",
  "desfecho": "cardiac arrhythmia",
  "condicao": "",
  "populacao": ""
}
```

Os mesmos campos que "café aumenta o risco de arritmia". A busca procura a
literatura sobre a relação; quem decide a direção é o Juiz. O que não se pode
fazer é trocar `cardiac arrhythmia` por outra doença.

<!-- /interno -->
