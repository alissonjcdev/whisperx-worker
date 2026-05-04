# ─────────────────────────────────────────────────────────────────────
# Helper STANDALONE prepended ao handler.py via Dockerfile.
#
# Substitui a linha problemática `return float(stream['duration']) * 1000`
# por `return _safe_get_audio_duration_ms(audio_file, stream)` (sed inline
# no Dockerfile garante o swap).
#
# Cascata de fallbacks pra arquivos sem stream.duration (caso comum: WebM
# live do MediaRecorder do navegador):
#   1) usa stream['duration'] se presente (comportamento original, mantido)
#   2) ffprobe `format.duration` (top-level container)
#   3) ffmpeg decode + parse stderr "Duration:" (último recurso)
# ─────────────────────────────────────────────────────────────────────

import json as _patch_json
import subprocess as _patch_subprocess


def _safe_get_audio_duration_ms(audio_file, stream):
    """Retorna duração em ms. Robusto contra arquivos sem stream.duration."""
    # Tentativa 1: comportamento original (stream.duration) — funciona pra
    # MP3, WAV, MP4 com header completo
    try:
        d = stream.get('duration')
        if d is not None:
            return float(d) * 1000
    except Exception as e:
        print(f'[patch] stream.duration falhou: {e}')

    # Tentativa 2: format.duration (top-level do container, geralmente
    # presente mesmo quando stream.duration falta)
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


print('[patch] _safe_get_audio_duration_ms disponível no namespace global')
