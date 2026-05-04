# Fork do upmeet/whisperx-runpod com pre-processing robusto de áudio.
#
# Motivação: imagem upstream usa ffprobe stream['duration'] direto sem fallback,
# crasha com KeyError 'duration' em WebM live (MediaRecorder do navegador
# em chunks live não escreve Duration no header). Issue empiricamente
# confirmada via job RunPod test:
#   "KeyError: 'duration'\n  File '/handler.py', line 174, in get_audio_duration"
#
# Solução: aplica patch que adiciona fallback robusto na função problemática.
# Não muda nada da pipeline WhisperX — só torna o pre-processing tolerante.
#
# Stack herdada SEM mudança:
#   - WhisperX
#   - faster-whisper (backend)
#   - pyannote (diarization)
#   - Modelo large-v3 (HF download em runtime)
#   - CUDA, PyTorch, ffmpeg

FROM upmeet/whisperx-runpod:6.2.0

# Patch INLINE da linha problemática usando Python (mais seguro que sed
# pra strings com caracteres especiais). Tentativa anterior de append falhou
# — provavelmente porque handler.py importa get_audio_duration de outro
# lugar OU faz binding de closure que não respeita override no namespace.
#
# Estratégia agora: substituir o BODY da função get_audio_duration direto
# no source pra ter cascata robusta de fallbacks. Build falha (não roda)
# se string esperada não bater, então sabemos cedo se imagem upstream mudou.
COPY handler-patch.py /handler-patch.py
RUN python3 << 'PYEOF'
import shutil, re

shutil.copy('/handler.py', '/handler-original.py')

with open('/handler.py', 'r') as f:
    src = f.read()

# Snippet a substituir (linha que crasha hoje)
needle = "return float(stream['duration']) * 1000"
if needle not in src:
    raise SystemExit(f"PATCH FAIL: snippet '{needle}' não encontrado em /handler.py — imagem upstream mudou?")

# Substitui pela chamada robusta. _safe_get_audio_duration_ms está definida
# no patch que prepended abaixo.
patched = src.replace(needle, "return _safe_get_audio_duration_ms(audio_file, stream)")

# Lê o helper standalone do patch e prepends no topo (garantido em escopo
# do módulo, sem depender de override tardio).
with open('/handler-patch.py', 'r') as f:
    patch = f.read()

with open('/handler.py', 'w') as f:
    f.write(patch + '\n# === HANDLER ORIGINAL ABAIXO ===\n' + patched)

# Valida sintaxe
import py_compile
py_compile.compile('/handler.py', doraise=True)
print('[build] patch aplicado com sucesso — substituiu linha buggy pela versão safe')
PYEOF

# CMD original da imagem upmeet — não muda.
