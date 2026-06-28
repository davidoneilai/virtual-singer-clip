# Virtual Singer Clip Pipeline

Pipeline para gerar videoclipes com cantor virtual: letra → música (ACE-Step) → áudio final → cenas de vídeo → montagem. Suporta voice conversion (RVC / Seed-VC), lip-sync (LatentSync, MuseTalk, EchoMimic, Hallo3) e variantes pré-configuradas.

> **Aviso:** use apenas vozes, letras e imagens que você tem direito de usar. Você é responsável pelo conteúdo gerado.

## O que o pipeline faz

1. Gera ou carrega letra (`assets/lyrics/`)
2. Gera música cantada via ACE-Step
3. Separa stems (Demucs) e finaliza áudio
4. (Opcional) Converte voz com RVC ou Seed-VC
5. Gera prompts e cenas de vídeo
6. (Opcional) Lip-sync / avatar talking-head
7. Monta o videoclipe final

Saída padrão: `output/` ou `output/variants/<nome>/`.

## Pré-requisitos

- Python 3.10+
- GPU NVIDIA (recomendado)
- Git
- Token Hugging Face (`HF_TOKEN`) para modelos gated — exporte antes de rodar:

```bash
export HF_TOKEN=hf_...
```

## Setup

```bash
git clone https://github.com/davidoneilai/virtual-singer-clip.git
cd virtual-singer-clip

python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
bash setup_external.sh
```

Instale dependências dos backends que for usar:

```bash
# Geração de música (ACE-Step)
pip install -r requirements-acestep.txt

# Voice conversion
pip install -r requirements-seedvc.txt    # Seed-VC
pip install -r requirements-rvc.txt       # RVC (ver scripts/setup_rvc.sh)

# Lip-sync / avatar (escolha um ou mais)
bash scripts/setup_latentsync.sh
bash scripts/setup_musetalk.sh
bash scripts/setup_echomimic.sh
bash scripts/setup_hallo3.sh
```

O passo `01_generate_song_acestep.py` usa backend `pt` por padrão (sem flash-attn). Para `vllm`:

```bash
pip install -e external/ACE-Step-1.5/acestep/third_parts/nano-vllm
python scripts/01_generate_song_acestep.py --backend vllm
```

## Assets locais

Arquivos em `assets/` **não vão para o repositório**. Veja [assets/README.md](assets/README.md).

Resumo:

| Pasta | Conteúdo |
|-------|----------|
| `assets/lyrics/` | Letra `.txt` |
| `assets/references/<tag>/` | Clips vocais `.wav` para conversão |
| `assets/voices/<tag>/` | Modelo RVC (`model.pth`, `model.index`) |
| `assets/avatars/<tag>/` | `avatar.png` / `avatar.mp4` para lip-sync |

## Cache e downloads

Por padrão, caches Hugging Face / torch ficam em `.cache/` dentro do projeto (não em `~/.cache`):

```bash
export VSC_CACHE_DIR=./.cache   # opcional; este é o default
```

Checkpoints ACE-Step: `external/ACE-Step-1.5/checkpoints/` (após primeiro uso).

## Rodar pipeline básico

Coloque sua letra em `assets/lyrics/` e configure variáveis se necessário, depois:

```bash
python scripts/00_generate_lyrics.py
python scripts/01_generate_song_acestep.py
python scripts/02_split_stems_demucs.py
python scripts/04_finalize_audio.py --mode song
python scripts/05_make_scene_prompts.py
python scripts/06_generate_video_wan.py
python scripts/08_assemble_clip.py
```

Ou tudo de uma vez (sem lip-sync):

```bash
python run_all.py
```

## Variantes

Scripts de alto nível em `scripts/run_*.sh` configuram estilo musical, avatar e prompts. Exemplos:

```bash
bash scripts/run_pipeline.sh sabrina_sao_joao_quadrilha
bash scripts/run_pipeline.sh anderson_modao_goiano
bash scripts/run_pipeline.sh espresso_blues_jazz
```

Saída em `output/variants/<variant>/final_videoclip.mp4`.

Variáveis úteis:

| Variável | Descrição |
|----------|-----------|
| `VSC_CLIP_MODE` | `hybrid` (default) ou outro modo de montagem |
| `VSC_VOICE_CONVERSION` | `1` para ativar RVC |
| `VSC_VIDEO_ONLY` | `1` para pular áudio e só renderizar vídeo |
| `VSC_CACHE_DIR` | Diretório de cache HF/torch |

## Lip-sync opcional

Coloque avatar em `assets/avatar.mp4` (ou `assets/avatars/<tag>/`) e rode o backend desejado:

```bash
python scripts/07_lipsync_latentsync.py
python scripts/07_lipsync_musetalk.py
python scripts/07_avatar_echomimic.py
python scripts/07_avatar_hallo3.py
```

## Docker

Monte o projeto em `/workspace` dentro do container:

```bash
docker run --rm -it --gpus all \
  -e HF_TOKEN="$HF_TOKEN" \
  -w /workspace \
  -v "$(pwd)":/workspace \
  sua-imagem-gpu bash
```

Pipeline em background (log em `output/pipeline.log`):

```bash
docker rm -f vsc-pipeline 2>/dev/null || true

docker run -d --name vsc-pipeline \
  --gpus device=0 \
  -e HF_TOKEN="$HF_TOKEN" \
  -w /workspace \
  -v "$(pwd)":/workspace \
  sua-imagem-gpu \
  bash scripts/docker_pipeline.sh

tail -f output/pipeline.log
```

Passe scripts específicos como argumentos de `docker_pipeline.sh`.

## Estrutura do repositório

```
virtual-singer-clip/
├── scripts/           # Pipeline e setup
├── assets/            # Entrada local (não versionada)
├── external/          # Repos clonados por setup_external.sh
├── output/            # Saídas geradas
├── .cache/            # Cache HF/torch
├── run_all.py         # Pipeline básico end-to-end
└── setup_external.sh  # Clona ACE-Step, MuseTalk, LatentSync, etc.
```

## Licença

MIT — veja [LICENSE](LICENSE).
