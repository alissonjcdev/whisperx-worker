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

# Aplica patch via APPEND (não prepend!) no handler.py original.
# Python avalia top-down: a última `def get_audio_duration` ganha. Como o
# handler() só CHAMA get_audio_duration em runtime (lookup tardio no
# namespace global do módulo), a sobrescrita pelo patch funciona — handler
# vai usar nossa versão patcheada quando o RunPod invocar o job.
COPY handler-patch.py /handler-patch.py
RUN python3 -c "import shutil; shutil.copy('/handler.py', '/handler-original.py')" && \
    cat /handler-original.py /handler-patch.py > /handler.py && \
    python3 -c "import py_compile; py_compile.compile('/handler.py', doraise=True)"

# CMD original da imagem upmeet — não muda.
