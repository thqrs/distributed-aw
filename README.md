# distributed-aw

Workers do treino distribuído da CPU do [awbw4](https://awbw.vitamindanswers.com) para o
GitHub Actions, o CircleCI e o Kaggle.

Este repositório só tem os workflows. O código do jogo, as campanhas, os resultados e as
chaves ficam fora do GitHub. Cada máquina descarrega do site o worker empacotado
(`treino/remote-worker.mjs`, Node 18+: traz o motor, a CPU, os mapas e o engine build do
site), pede trabalhos ao servidor, joga-os em todos os núcleos e envia os resultados.

Cada trabalho é um par de partidas a sério (o mesmo mapa dos dois lados, até ao dia 30):
um passo do SPSA (duas versões da CPU com pesos um bocadinho diferentes; os pesos andam
para o lado de quem ganhou) ou um par de uma validação (a CPU que está a aprender contra
a CPU do jogo, em mapas que o treino não usa, até o SPRT decidir se é melhor). O progresso
vê-se no jogo, em "Ajudar a treinar a CPU".

## GitHub Actions

1. O secret `AI_TRAINING_KEY` (Settings → Secrets and variables → Actions) tem a **chave dos
   workers** do awbw4. Nunca a de administração.
2. Actions → **Treino da CPU (awbw4)** → Run workflow. Por omissão: 20 máquinas × 4 núcleos,
   cada uma até 330 minutos (o GitHub corta às 6 h; no fim, cada máquina acaba as partidas a
   meio, envia-as e devolve o resto). Para experimentar: `shards_json` = `[1]`,
   `jobs_per_runner` = `4`.

## Kaggle

Notebook com **Internet** ligada (Settings → Internet on). Numa célula:

```
!curl -fsSL https://awbw.vitamindanswers.com/treino/remote-worker.mjs -o awbw-worker.mjs
!node awbw-worker.mjs --url https://awbw.vitamindanswers.com --chave CHAVE_DOS_WORKERS --workers 4 --nome Kaggle
```

O botão de parar (interromper) acaba as partidas a meio e devolve o resto.

## CircleCI

Variável do projeto `AI_TRAINING_KEY` com a chave dos workers; Trigger Pipeline com
`run_training` = `true` (e `parallelism`, `workers`, `minutes` à escolha).

## Outros PCs

Qualquer PC com Node 18+: os mesmos dois comandos do Kaggle (sem o `!`). Ctrl+C acaba as
partidas a meio e devolve o resto.

---

`ai-training/remote-worker.mjs` é o worker antigo do awbw3 (treino parado desde 15/09/2026);
já não é usado.
