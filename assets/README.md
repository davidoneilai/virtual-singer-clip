# Assets locais

Estes diretórios **não são versionados** (exceto este README e os `.gitkeep`).
Cada usuário coloca os próprios arquivos antes de rodar o pipeline.

## Estrutura

```
assets/
├── lyrics/              # Letra de entrada (.txt)
├── references/<nome>/   # Clips de referência vocal (.wav) para voice conversion
├── voices/<nome>/       # Modelos RVC treinados (model.pth, model.index) — criar localmente
├── avatars/<variante>/  # avatar.png e/ou avatar.mp4 para lip-sync — criar localmente
├── avatar.png           # Avatar padrão (fallback)
└── avatar.mp4           # Vídeo avatar padrão (fallback)
```

As pastas `voices/` e `avatars/` são criadas pelos scripts de variantes (`mkdir -p`); não há placeholders versionados nelas.

## O que colocar em cada pasta

| Pasta | Formato | Uso |
|-------|---------|-----|
| `lyrics/` | `.txt` | Letra usada por `00_generate_lyrics.py` ou variantes |
| `references/<tag>/` | `.wav` | Amostras vocais para RVC / Seed-VC |
| `voices/<tag>/` | `.pth`, `.index` | Modelo RVC já treinado |
| `avatars/<tag>/` | `.png`, `.mp4` | Personagem virtual para lip-sync |

## Aviso legal

Use apenas vozes, letras e imagens que você tem direito de usar (próprias, licenciadas ou sintéticas).
Não distribua clips de artistas reais, letras protegidas por copyright ou modelos treinados em vozes de terceiros sem autorização.
