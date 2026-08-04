# Lo-fi playlist batch

Gera playlists instrumentais de ~1 hora a partir de prompts em `.txt`.
Cada prompt vira várias faixas curtas concatenadas em um único `playlist.wav`.

**Fase atual:** só áudio (sem vídeo).

## Prompts

Coloque um arquivo por tema em `lofi_batch/prompts/`:

```bash
echo "rainy night lo-fi, soft piano, vinyl crackle, no vocals" > lofi_batch/prompts/rainy_night.txt
```

O nome do arquivo (sem `.txt`) vira o slug da pasta de saída.

## Rodar (Docker)

```bash
cd /raid/user_davidoneil/virtual_singer_clip

# defaults: GPU=1, 20 faixas x 180s, DiT xl-turbo
bash lofi_batch/run_docker.sh

# smoke / teste curto
TRACKS=2 DURATION=30 GPU=1 bash lofi_batch/run_docker.sh
```

Ou dentro de um container já aberto:

```bash
python lofi_batch/run_batch.py --tracks 20 --duration 180
```

## Saída

```text
output/lofi_batch/<run_id>/<slug>/
  tracks/01.wav … NN.wav
  playlist.wav
  manifest.json
```

Resume: faixas já existentes são puladas; se `playlist.wav` existe, o prompt é pulado.

## Agenda (a cada 3 dias)

Veja `crontab.example`.

## Config

Defaults documentados em `config.env.example` (`GPU`, `TRACKS`, `DURATION`, `CONFIG_PATH`, …).
