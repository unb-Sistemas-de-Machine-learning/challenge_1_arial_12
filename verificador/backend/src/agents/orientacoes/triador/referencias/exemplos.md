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

## 2. Os quatro campos preenchidos

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

## 3. Marca de medicamento

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

## 4. O trecho cheio de ruído

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

## 5. Quando o trecho não dá busca

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
código não monta busca e a verificação segue apenas com o trecho original. Essa
é a resposta certa: o trecho, como está escrito, não é verificável.

## 6. Negação

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

## 7. Fora da biomedicina

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
