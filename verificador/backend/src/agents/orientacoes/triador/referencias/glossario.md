# Glossário controlado

A lista dos conceitos que já apareceram em trechos reais e da tradução que a
equipe **fixou** para cada um. Ela existe porque a escolha livre de sinônimo era
a maior fonte de instabilidade da busca: `encolhimento do cérebro` saía como
`brain shrinkage` numa chamada e `cerebral volume reduction` na seguinte, e a
OpenAlex devolve conjuntos diferentes para as duas.

Como ela é usada, em dois lugares:

1. **Pelo variador semântico**, como instrução: conceito que está na tabela tem
   termo decidido, e é o da segunda coluna.
2. **Pelo código**, como garantia: antes de montar as strings, ele reescreve
   para o termo canônico qualquer campo que tenha vindo como uma das variantes
   da terceira coluna (ou como o conceito em português). O glossário não é um
   pedido — é aplicado.

A terceira coluna tem uma segunda função: **a primeira variante de cada linha é
o termo que o eixo `sinonimo` usa** (veja `formatos-de-busca.md`). É ela que dá
diversidade de vocabulário à busca sem depender de o modelo inventar uma na
hora. Por isso a ordem importa: ponha na frente a alternativa mais usada na
literatura, não a mais exótica.

## Tabela

O código lê a tabela desta seção, e só dela: o resto do arquivo é prosa para
quem edita. Três colunas por linha, variantes separadas por `;`.

| Conceito (PT) | Termo canônico (EN) | Variantes reescritas pelo código |
| :--- | :--- | :--- |
| consumo de álcool | alcohol consumption | alcohol intake; alcohol use; drinking |
| encolhimento do cérebro | brain atrophy | brain volume reduction; brain shrinkage; cerebral atrophy |
| exercício físico | physical exercise | physical activity; exercise training; aerobic exercise |
| depressão | depression | depressive symptoms; major depressive disorder |
| dieta mediterrânea | mediterranean diet | mediterranean dietary pattern |
| expectativa de vida | life expectancy | longevity; all cause mortality |
| jejum intermitente | intermittent fasting | time restricted feeding; alternate day fasting |
| perda de peso | weight loss | body weight reduction; weight reduction |
| controle glicêmico | glycemic control | blood glucose control; insulin sensitivity |
| sono irregular | sleep irregularity | sleep variability; irregular sleep timing |
| qualidade do sono | sleep quality | sleep duration; sleep disturbance |
| demência | dementia | cognitive decline; cognitive impairment |
| cafeína | caffeine | coffee consumption; caffeine intake |
| doença de parkinson | parkinson disease | parkinsonism; parkinsons disease |
| probióticos | probiotics | probiotic supplementation |
| saúde intestinal | gut microbiota | gut health; intestinal microbiome |
| uso de telas | screen time | screen use; electronic media use |
| antibióticos | antibiotics | antibiotic exposure; antimicrobial exposure |
| obesidade | obesity | overweight; body mass index |
| opioides | opioids | opioid analgesics; prescription opioids |
| oxicodona | oxycodone | oxycontin; oxycodone hydrochloride |
| cigarro eletrônico | electronic cigarette | e cigarette; vaping; electronic nicotine delivery |
| dano pulmonar | lung injury | pulmonary injury; respiratory damage |
| exposição ao sol | sun exposure | ultraviolet radiation; uv exposure |
| câncer de pele | skin cancer | cutaneous carcinoma; keratinocyte carcinoma |
| câncer de mama | breast cancer | breast carcinoma; mammary carcinoma |
| consumo de sal | sodium intake | salt intake; dietary sodium |
| pressão arterial | blood pressure | hypertension; arterial pressure |
| meditação | meditation | mindfulness meditation; mindfulness |
| cortisol | cortisol | salivary cortisol; serum cortisol |
| flúor na água | water fluoridation | fluoridated water; fluoride exposure |
| cárie | dental caries | tooth decay; caries experience |
| vírus zika | zika virus | zika virus infection |
| microcefalia | microcephaly | congenital microcephaly |
| microplásticos | microplastics | microplastic particles; plastic particles |
| bisfenol a | bisphenol a | bpa; bpa exposure |
| desregulação endócrina | endocrine disruption | hormone disruption; estrogenic activity |
| vacina contra a malária | malaria vaccine | plasmodium falciparum vaccine |
| mortalidade infantil | child mortality | infant mortality; under five mortality |
| medula espinhal | spinal cord | spinal cord tissue |
| regeneração | regeneration | axonal regeneration; nerve regeneration |
| terapia genética | gene therapy | genetic therapy; gene transfer |
| anemia falciforme | sickle cell disease | sickle cell anemia |
| asma | asthma | asthma exacerbation; bronchial asthma |
| mudanças climáticas | climate change | global warming |
| aumento do nível do mar | sea level rise | sea level change |

## Como acrescentar uma linha

Acrescente quando o problema **aparecer de verdade**, e não por antecipação: um
glossário inflado é prompt caro e manutenção sem dono. O sinal é um destes:

- o mesmo trecho achou o estudo numa rodada e não achou na seguinte, e a
  diferença entre as duas foi a escolha de termo;
- a rodada de avaliação (`scripts/eval_triador.py --repeticoes 3`) acusou
  instabilidade no caso.

Então:

1. Rode o caso e anote os termos que saíram em cada rodada.
2. Escolha como canônico o termo que **mais aparece em título e resumo na
   OpenAlex** — compare o `total_por_busca` das duas formas, não o gosto de
   quem escreve.
3. Ponha as outras formas observadas na terceira coluna, a mais comum primeiro.
4. Rode a avaliação de novo e confirme que o caso ficou estável **e** que a taxa
   de acerto geral não caiu.

Uma linha só vale se as três colunas estiverem preenchidas; o código ignora em
silêncio qualquer linha incompleta, e uma linha sem variante não participa do
eixo `sinonimo`.
