# Lo-fi daily YouTube pipeline

Gera um pacote Lo-Fi por run: prompt (Qwen) → playlist (ACE-Step) → capa (Wan) → MP4 estático → fila → upload YouTube (**no máximo 1 vídeo/dia**).

## Modos

| Modo | Comando | Efeito |
|------|---------|--------|
| Daily | `bash lofi_batch/run_daily.sh` | 1 pacote + tenta upload |
| Burst | `COUNT=5 bash lofi_batch/run_burst.sh` | N pacotes na fila, **sem** furar o limite diário |
| Daemon | `bash lofi_batch/run_daemon.sh` | Espera GPU livre e roda daily |

## Smoke (sem YouTube)

```bash
cd /raid/user_davidoneil/virtual_singer_clip
TRACKS=2 DURATION=30 SKIP_UPLOAD=1 MODE=daily GPU=1 bash lofi_batch/run_docker.sh
```

## YouTube

Ver [YOUTUBE_SETUP.md](YOUTUBE_SETUP.md). Depois:

```bash
pip install -r lofi_batch/requirements-youtube.txt
python lofi_batch/youtube_auth.py
python lofi_batch/youtube_upload.py --dry-run
YOUTUBE_PRIVACY=unlisted python lofi_batch/youtube_upload.py
```

## Saída

```text
output/lofi_batch/
  queue/<run_id>_<slug>/
    prompt.json, playlist.wav, cover.png, video.mp4, meta.json, …
  published/<run_id>_<slug>/
  state.json
```

## Prompts manuais (debug)

Ainda funciona o caminho antigo com `lofi_batch/prompts/*.txt` via `python lofi_batch/run_batch.py`.

## Regras do LLM

Edite `lofi_batch/rules/lofi_rules.md` (Lo-Fi clássico + estrutura restritiva tipo odisseu).

## Checklist E2E

1. `PYTHONPATH=. python -m pytest lofi_batch/tests -v`
2. Smoke Docker com `TRACKS=2 DURATION=30 SKIP_UPLOAD=1`
3. OAuth uma vez (`youtube_auth.py`)
4. `--dry-run` no uploader
5. Upload real com `YOUTUBE_PRIVACY=unlisted`
6. Confirmar segundo upload no mesmo dia → `skipped_daily_cap`
7. Burst `COUNT=2` → dois pacotes `ready`, um upload/dia

## Config

Ver `config.env.example`.
