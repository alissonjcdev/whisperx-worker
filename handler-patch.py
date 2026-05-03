# ─────────────────────────────────────────────────────────────────────
# PATCH appended ao handler.py original via Dockerfile.
#
# Sobrescreve `get_audio_duration` no namespace do módulo. Como o handler()
# só chama essa função em runtime (lookup tardio no namespace global),
# nossa versão é a que vale quando o RunPod invoca o job.
#
# Bug original (upmeet/whisperx-runpod:6.2.0):
#   File "/handler.py", line 174, in get_audio_duration
#     return float(stream['duration']) * 1000
#   KeyError: 'duration'
#
# Causa: WebM live (MediaRecorder do navegador) não escreve `Duration` no
# header do Segment Info — encoder não sabe quando user vai parar de gravar.
# ffprobe stream[].duration vem ausente, mas format.duration vem ok ou
# pode ser calculado decodando.
#
# Estratégia em cascata (do mais barato pro mais caro):
#   1) ffprobe `format.duration` (top-level container, geralmente presente)
#   2) ffprobe `stream.duration` (comportamento original — mantido como fallback)
#   3) ffmpeg decode + parse stderr "Duration:" (sempre funciona em arquivo válido)
# ─────────────────────────────────────────────────────────────────────

import json as _patch_json
import subprocess as _patch_subprocess


def _safe_get_audio_duration(audio_file):
    """Retorna duração em ms. Robusto contra arquivos sem stream.duration."""
    # Tentativa 1: format.duration (top-level do container, mais confiável)
    try:
        r = _patch_subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'json', audio_file],
            capture_output=True, text=True, check=True, timeout=30
        )
        d = _patch_json.loads(r.stdout).get('format', {}).get('duration')
        if d is not None:
            return float(d) * 1000
    except Exception as e:
        print(f'[patch] ffprobe format.duration falhou: {e}')

    # Tentativa 2: ffprobe stream.duration (comportamento original do upmeet)
    try:
        r = _patch_subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=duration',
             '-of', 'json', audio_file],
            capture_output=True, text=True, check=True, timeout=30
        )
        for s in _patch_json.loads(r.stdout).get('streams', []):
            d = s.get('duration')
            if d is not None:
                return float(d) * 1000
    except Exception as e:
        print(f'[patch] ffprobe stream.duration falhou: {e}')

    # Tentativa 3 (último recurso): decode com ffmpeg + parse "Duration:" do stderr
    try:
        r = _patch_subprocess.run(
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
        print(f'[patch] ffmpeg decode-measure falhou: {e}')

    print(f'[patch] AVISO: não foi possível medir duração de {audio_file}, retornando 0')
    return 0


# Sobrescreve no namespace do módulo. Como esse arquivo é appended DEPOIS do
# handler.py original, nossa atribuição vence o `def get_audio_duration(...)`
# original. O handler() chama get_audio_duration em runtime via lookup global,
# pega nossa versão.
get_audio_duration = _safe_get_audio_duration
print('[patch] get_audio_duration sobrescrito com versão robusta')
