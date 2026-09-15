# distributed-aw

Minimal distributed AI-training worker for the AWBW project.

This repository intentionally contains only the GitHub Actions runner and the remote Node.js worker. The game/server source, SQLite database, private configuration, training results and admin credentials remain outside GitHub.

## Setup

1. Add a repository Actions secret named `AI_TRAINING_KEY` containing the AI Training **worker key** (not the admin key).
2. Open **Actions → AI training worker (manual) → Run workflow**.
3. For the first test use:
   - `site`: `https://awbw.vitamindanswers.com/ai-training`
   - `campaign`: `breadth-100k`
   - `seeds_per_job`: `20`
   - `workers`: `4`
   - `shards_json`: `[1]`
4. If the single-runner test is healthy, bounded parallel tests can use `[1,2]` and then `[1,2,3,4]`.

At runtime the worker downloads the simulation bundle, shared simulation code and suite definitions from the configured AI Training endpoint, claims seeds, computes them locally on the runner, and submits results back in small batches.
