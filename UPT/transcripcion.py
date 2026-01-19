"""
Transcripción de audio mejorada con manejo robusto de archivos temporales
"""
import os
from math import ceil
import speech_recognition as sr
from pydub import AudioSegment
from log import get_logger
import tempfile
import time

logger = get_logger()


def transcribir_audio(archivo_original):
    """
    Transcribe un archivo de audio a texto
    
    Args:
        archivo_original: Ruta del archivo de audio original
    
    Returns:
        str: Texto transcrito
    """
    # Crear nombres únicos para archivos temporales usando timestamp
    timestamp = str(int(time.time() * 1000))
    temp_dir = tempfile.gettempdir()
    
    archivo_convertido = os.path.join(temp_dir, f"temp_pcm_{timestamp}.wav")
    
    try:
        logger.info("Convirtiendo el audio...")
        sound = AudioSegment.from_file(archivo_original)
        sound = sound.set_frame_rate(16000).set_channels(1)
        sound.export(archivo_convertido, format="wav")

        recognizer = sr.Recognizer()
        audio = AudioSegment.from_wav(archivo_convertido)
        segment_duration = 60 * 1000  # 60 segundos
        num_segments = ceil(len(audio) / segment_duration)

        transcripcion = ""
        
        for i in range(num_segments):
            inicio = i * segment_duration
            fin = min((i + 1) * segment_duration, len(audio))
            fragmento = audio[inicio:fin]
            
            # Nombre único para cada fragmento
            fragment_path = os.path.join(temp_dir, f"temp_fragment_{timestamp}_{i}.wav")
            
            try:
                fragmento.export(fragment_path, format="wav")

                with sr.AudioFile(fragment_path) as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio_data = recognizer.record(source)

                try:
                    texto = recognizer.recognize_google(audio_data, language="es-ES")
                    transcripcion += texto + " "
                    logger.debug(f"Fragmento {i+1}/{num_segments}: OK")
                except sr.UnknownValueError:
                    logger.warning(f"Fragmento {i+1}/{num_segments}: no se entiende el audio")
                except sr.RequestError as e:
                    logger.error(f"Error de conexión en el fragmento {i+1}: {e}")
                    break
                    
            finally:
                # Asegurar que el fragmento se elimine
                try:
                    if os.path.exists(fragment_path):
                        os.remove(fragment_path)
                except Exception as e:
                    logger.warning(f"No se pudo eliminar {fragment_path}: {e}")

        return transcripcion.strip()
        
    except Exception as e:
        logger.error(f"Error en transcripción: {e}")
        raise
        
    finally:
        # Limpiar archivo convertido
        try:
            if os.path.exists(archivo_convertido):
                os.remove(archivo_convertido)
        except Exception as e:
            logger.warning(f"No se pudo eliminar {archivo_convertido}: {e}")