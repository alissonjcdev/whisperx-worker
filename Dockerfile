# Fork do upmeet/whisperx-runpod com pre-processing robusto de áudio.
#
# Estratégia: NÃO mexe no /handler.py original (zero risco de quebrar
# imports/closures). Em vez disso, copia handler-patch.py como novo
# entrypoint que importa o handler.py original, sobrescreve a função
# buggy get_audio_duration via monkey-patch no namespace do módulo, e
# inicia o runpod.serverless.start.
#
# Bug original (linha 174 do handler.py upmeet):
#   return float(stream['duration']) * 1000  # KeyError se sem 'duration'
#
# Causa: WebM live (MediaRecorder do navegador) não escreve Duration no
# header — encoder não sabe tempo final no start.
#
# Stack herdada SEM mudança:
#   - WhisperX, faster-whisper, pyannote, large-v3, CUDA, PyTorch, ffmpeg

FROM upmeet/whisperx-runpod:6.2.0

# Copia wrapper como NOVO entrypoint (handler.py original intacto)
COPY handler-patch.py /safe_handler.py

# Sobrescreve CMD pra rodar nosso wrapper em vez do handler.py direto.
# Wrapper importa handler original + monkey-patch + chama runpod.serverless.start.
CMD ["python", "-u", "/safe_handler.py"]
