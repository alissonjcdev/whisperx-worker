"""
Wrapper que importa o handler.py original do upmeet/whisperx-runpod:6.2.0,
sobrescreve a função get_audio_duration por uma versão robusta antes do
runpod.serverless.start, e re-expõe o handler patcheado.

Bug original (linha 174 de handler.py):
    return float(stream['duration']) * 1000  # KeyError se stream sem 'duration'

Causa: WebM live (MediaRecorder do navegador) não escreve Duration no header
do Segment Info — encoder não sabe o tempo final no momento do start.

Fix: replace get_audio_duration no namespace do MODULE handler ANTES do
runpod.serverless.start. Como Python faz lookup tardio em runtime,
qualquer chamada interna a `get_audio_duration(...)` no handler() vai
pegar nossa versão.
"""

import json
import subprocess
import sys

import handler as _handler_module  # /handler.py original do upmeet


def _safe_get_audio_duration(audio_file):
    """Retorna duração em ms. Cascata robusta de fallbacks."""
    # Tentativa 1: ffprobe stream.duration (comportamento original)
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=duration',
             '-of', 'json', audio_file],
            capture_output=True, text=True, check=True, timeout=30
        )
        for s in json.loads(r.stdout).get('streams', []):
            d = s.get('duration')
            if d is not None:
                return float(d) * 1000
    except Exception as e:
        print(f'[patch] ffprobe stream.duration falhou: {e}', file=sys.stderr)

    # Tentativa 2: ffprobe format.duration (top-level container)
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'json', audio_file],
            capture_output=True, text=True, check=True, timeout=30
        )
        d = json.loads(r.stdout).get('format', {}).get('duration')
        if d is not None:
            return float(d) * 1000
    except Exception as e:
        print(f'[patch] ffprobe format.duration falhou: {e}', file=sys.stderr)

    # Tentativa 3: decode com ffmpeg + parse "Duration:" do stderr
    try:
        r = subprocess.run(
            ['ffmpeg', '-i', audio_file, '-f', 'null', '-'],
            capture_output=True, text=True, timeout=120
        )
        for line in r.stderr.split('\n'):
            if 'Duration:' in line:
                t = line.split('Duration:')[1].split(',')[0].strip()
                if t and t != 'N/A':
                    h, m, s = t.split(':')
                    return (float(h) * 3600 + float(m) * 60 + float(s)) * 1000
    except Exception as e:
        print(f'[patch] ffmpeg decode-measure falhou: {e}', file=sys.stderr)

    print(f'[patch] AVISO: não foi possível medir duração de {audio_file}, retornando 0', file=sys.stderr)
    return 0


# Sobrescreve get_audio_duration no namespace do MODULE original.
# Lookup global do handler() em runtime pega nossa versão.
_handler_module.get_audio_duration = _safe_get_audio_duration
print('[patch] handler.get_audio_duration sobrescrito com versão robusta', flush=True)


# Re-expõe o handler() pra runpod.serverless detectar
handler = _handler_module.handler

if __name__ == '__main__':
    import runpod
    runpod.serverless.start({'handler': handler})
