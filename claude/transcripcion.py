# transcripcion
def transcribir_audio(archivo_original):
    archivo_convertido = "temp_pcm.wav"
    print(" Convirtiendo el audio...")
    sound = AudioSegment.from_file(archivo_original)
    sound = sound.set_frame_rate(16000).set_channels(1)
    sound.export(archivo_convertido, format="wav")

    recognizer = sr.Recognizer()
    audio = AudioSegment.from_wav(archivo_convertido)
    segment_duration = 60 * 1000
    num_segments = ceil(len(audio) / segment_duration)

    transcripcion = ""
    for i in range(num_segments):
        inicio = i * segment_duration
        fin = min((i + 1) * segment_duration, len(audio))
        fragmento = audio[inicio:fin]
        fragment_path = f"temp_fragment_{i}.wav"
        fragmento.export(fragment_path, format="wav")

        with sr.AudioFile(fragment_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio_data = recognizer.record(source)

        try:
            texto = recognizer.recognize_google(audio_data, language="es-ES")
            transcripcion += texto + " "
            print(f"Fragmento {i+1}/{num_segments}: OK")
        except sr.UnknownValueError:
            print(f"Fragmento {i+1}/{num_segments}: no se entiende el audio.")
        except sr.RequestError as e:
            print(f"Error de conexion en el fragmento {i+1}: {e}")
            break
        finally:
            os.remove(fragment_path)

    os.remove(archivo_convertido)
    return transcripcion.strip()
