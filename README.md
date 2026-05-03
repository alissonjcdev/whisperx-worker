# whisperx-worker

Fork do `upmeet/whisperx-runpod:6.2.0` com pre-processing robusto de áudio.

Usado pelo [Central de Demandas](https://github.com/alissonjcdev/central-de-demandas)
para transcrição via RunPod Serverless.

## Por que existe

Imagem upstream `upmeet/whisperx-runpod:6.2.0` quebra com `KeyError: 'duration'`
quando recebe arquivos sem `stream.duration` no header (caso comum: WebM live
gerado pelo `MediaRecorder` do navegador em chunks com `timeslice`).

```
Traceback (most recent call last):
  File "/handler.py", line 82, in handler
    audio_duration = get_audio_duration(audio_file)
  File "/handler.py", line 174, in get_audio_duration
    return float(stream['duration']) * 1000
KeyError: 'duration'
```

Esse fork aplica patch que adiciona fallback robusto:

1. `ffprobe format.duration` (top-level, geralmente presente)
2. `ffprobe stream.duration` (comportamento original como fallback)
3. `ffmpeg decode + parse stderr` (último recurso, sempre funciona)

Resto da pipeline WhisperX é idêntico ao upstream — modelo `large-v3`,
faster-whisper, pyannote diarization, etc.

## Build local

```bash
docker build -t ghcr.io/alissonjcdev/whisperx-worker:1.0 .
```

## Push pra ghcr.io

```bash
echo $GH_PAT | docker login ghcr.io -u alissonjcdev --password-stdin
docker push ghcr.io/alissonjcdev/whisperx-worker:1.0
```

## CI/CD via GitHub Actions

Push pra `main` dispara build + push automático pra `ghcr.io/alissonjcdev/whisperx-worker:latest`
e tag versionada. Ver `.github/workflows/build.yml`.

## Atualizar versão

Quando upmeet lançar `6.3.0` (ou versão nova com fix do KeyError):

```dockerfile
# Dockerfile
FROM upmeet/whisperx-runpod:6.3.0  # bump aqui
```

Bump tag, push, RunPod template aponta pra nova.

## Como o RunPod usa essa imagem

1. RunPod template criado com `imageName=ghcr.io/alissonjcdev/whisperx-worker:1.0`
2. Container Registry Auth configurado com PAT do GitHub (escopo `read:packages`)
3. Endpoint usa o template — workers cold-start puxam imagem do ghcr.io

## License

Patch é MIT. Imagem base segue licença do upstream upmeet/whisperx-runpod.
