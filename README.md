# distributed-aw

Workers do treino distribuído da CPU do [awbw4](https://awbw.vitamindanswers.com) para o
GitHub Actions, o CircleCI, o Kaggle e o Google Colab.

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

Relançamento automático: o workflow "Treino da CPU (awbw4)" também corre sozinho a cada 6 horas
(20 máquinas). Sem campanha ativa da versão do site, cada máquina sai logo.

## Kaggle e Google Colab

O notebook pronto está no site: https://awbw.vitamindanswers.com/treino/awbw4-worker.ipynb
(e as instruções no jogo, em "Ajudar a treinar a CPU").

A mesma célula serve para os dois. A chave fica nos segredos do notebook, nunca no código:

- **Kaggle**: Settings → **Internet on**; Add-ons → **Secrets** → `AI_TRAINING_KEY` = a chave
  dos workers (ligar o segredo a este notebook). Uma sessão de CPU dura até ~12 h, com 4 núcleos.
- **Colab**: ícone da chave (Secrets) → `AI_TRAINING_KEY` = a chave dos workers, com acesso
  do notebook ligado. O Colab grátis tem 2 núcleos e desliga se a página ficar parada
  (~90 min sem a ver) ou ao fim de ~12 h.

Numa célula Python:

```python
import os, subprocess, time
SITE = "https://awbw.vitamindanswers.com"
MINUTOS = 600          # quanto tempo a máquina joga (Kaggle até ~700; Colab grátis, 240 é mais seguro)
CAMPANHA = ""          # vazio = a primeira campanha ativa da versão do site

# a chave dos workers (nunca a de administração), dos segredos do Kaggle ou do Colab
try:
    from kaggle_secrets import UserSecretsClient
    KEY, NOME = UserSecretsClient().get_secret("AI_TRAINING_KEY"), "Kaggle"
except ImportError:
    from google.colab import userdata
    KEY, NOME = userdata.get("AI_TRAINING_KEY"), "Colab"

# Node 22 (o do sistema pode ser antigo)
NODE = "node-v22.11.0-linux-x64"
if not os.path.exists(NODE):
    subprocess.run(f"curl -fsSL https://nodejs.org/dist/v22.11.0/{NODE}.tar.xz | tar -xJ", shell=True, check=True)

# joga até ao fim do tempo; quando uma campanha acaba (ou o site muda de versão), volta a
# descarregar o worker e passa à campanha ativa seguinte
fim, falhas = time.time() + MINUTOS * 60, 0
while time.time() < fim - 120 and falhas < 6:
    subprocess.run(f"curl -fsSL {SITE}/treino/remote-worker.mjs -o awbw-worker.mjs", shell=True, check=True)
    cmd = [f"./{NODE}/bin/node", "awbw-worker.mjs", "--url", SITE, "--workers", str(os.cpu_count()),
           "--minutos", str(int((fim - time.time()) / 60)), "--nome", NOME]
    if CAMPANHA: cmd += ["--campanha", CAMPANHA]
    r = subprocess.run(cmd, env={**os.environ, "AI_TRAINING_KEY": KEY})
    falhas = 0 if r.returncode == 0 else falhas + 1
    time.sleep(30 if r.returncode == 0 else 120)
print("fim")
```

Parar a célula (interromper) acaba as partidas a meio e devolve o resto. Sem campanhas ativas
o worker sai com erro; ao fim de 6 tentativas (~12 min) a célula desiste.

## CircleCI

Variável do projeto `AI_TRAINING_KEY` com a chave dos workers; Trigger Pipeline com
`run_training` = `true` (e `parallelism`, `workers`, `minutes` à escolha).

## Outros PCs

Qualquer PC com Node 18+: os mesmos dois comandos do Kaggle (sem o `!`). Ctrl+C acaba as
partidas a meio e devolve o resto.

---

`ai-training/remote-worker.mjs` é o worker antigo do awbw3 (treino parado desde 15/09/2026);
já não é usado.
