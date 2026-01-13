import json
import traceback
from datetime import datetime
from abc import ABC, abstractmethod
from connection_settings import (
    AI_PROVIDER, 
    CLAUDE_API_KEY, 
    CLAUDE_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    PROMPT_TEMPLATE
)
from log import log
import os


class AIProvider(ABC):
    """Clase abstracta para proveedores de IA"""
    
    @abstractmethod
    def generate_response(self, prompt: str, max_tokens: int = 4000) -> str:
        """Genera una respuesta del modelo de IA"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Retorna el nombre del proveedor"""
        pass


class ClaudeProvider(AIProvider):
    """Implementación para Claude (Anthropic)"""
    
    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        self.model = CLAUDE_MODEL
    
    def generate_response(self, prompt: str, max_tokens: int = 4000) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text.strip()
        except Exception as e:
            log(f"Error al llamar a Claude: {e}")
            traceback.print_exc()
            return ""
    
    def get_provider_name(self) -> str:
        return "Claude"


class GeminiProvider(AIProvider):
    """Implementación para Gemini (Google)"""
    
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(GEMINI_MODEL)
    
    def generate_response(self, prompt: str, max_tokens: int = 4000) -> str:
        try:
            generation_config = {
                "max_output_tokens": max_tokens,
                "temperature": 0.7,
            }
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            return response.text.strip()
        except Exception as e:
            log(f"Error al llamar a Gemini: {e}")
            traceback.print_exc()
            return ""
    
    def get_provider_name(self) -> str:
        return "Gemini"


def get_ai_provider() -> AIProvider:
    """Factory para obtener el proveedor de IA configurado"""
    if AI_PROVIDER == "claude":
        return ClaudeProvider()
    elif AI_PROVIDER == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(f"Proveedor de IA no soportado: {AI_PROVIDER}")


# Instancia global del proveedor
ai_provider = get_ai_provider()
log(f"Proveedor de IA inicializado: {ai_provider.get_provider_name()}")


def extraer_json_de_texto(texto: str) -> dict:
    """Extrae JSON de un texto que puede contener markdown u otro contenido"""
    # Intentar extraer JSON de bloques de código markdown
    if "```json" in texto:
        inicio = texto.find("```json") + 7
        fin = texto.find("```", inicio)
        if fin != -1:
            json_str = texto[inicio:fin].strip()
            try:
                return json.loads(json_str)
            except:
                pass
    
    # Intentar extraer JSON entre llaves
    if "{" in texto and "}" in texto:
        try:
            json_str = texto[texto.index("{"): texto.rindex("}") + 1]
            return json.loads(json_str)
        except Exception as e:
            log(f"Error al decodificar JSON: {e}")
    
    return {"raw_response": texto}


def analizar_transcripcion(call_text, archivo_original):
    """Analiza la transcripción usando el proveedor de IA configurado"""
    
    # Paso 1: Separación Agente/Cliente
    prompt_transcripcion = f"""
Transcribe y separa la conversación dada en bloques hablados por el Agente o el Cliente.
Devuelve el resultado exclusivamente en formato JSON con esta estructura exacta:

{{
  "transcription": [
    {{"type": "Agente", "message": "Texto del agente"}},
    {{"type": "Cliente", "message": "Texto del cliente"}}
  ]
}}

Aquí está la transcripción original para analizar:
{call_text}
"""
    
    log(f"Separando conversación con {ai_provider.get_provider_name()}...")
    texto_transcripcion = ai_provider.generate_response(prompt_transcripcion, max_tokens=4000)
    
    try:
        transcripcion_json = extraer_json_de_texto(texto_transcripcion)
        if "transcription" not in transcripcion_json:
            raise ValueError("JSON no contiene campo 'transcription'")
    except Exception as e:
        log(f"Error al parsear la transcripción separada: {e}")
        transcripcion_json = {"transcription": [{"type": "Desconocido", "message": call_text}]}
    
    # Paso 2: Evaluación de calidad
    prompt = PROMPT_TEMPLATE.replace("{call_text}", call_text)
    
    log(f"Evaluando calidad con {ai_provider.get_provider_name()}...")
    texto = ai_provider.generate_response(prompt, max_tokens=4000)
    
    if not texto:
        log("No se obtuvo respuesta del proveedor de IA")
        analisis = {"raw_response": "Error: Sin respuesta"}
    else:
        analisis = extraer_json_de_texto(texto)
    
    # Paso 3: Estructura de salida estandarizada
    base, _ = os.path.splitext(archivo_original)
    nombre_base = os.path.basename(base)
    
    evaluacion_estandar = {
        "id_llamada": nombre_base,
        "fecha_evaluacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ruta_audio": archivo_original,
        "proveedor_ia": ai_provider.get_provider_name(),
        "modelo": CLAUDE_MODEL if AI_PROVIDER == "claude" else GEMINI_MODEL,
        "criterios": analisis.get("criterios", {}),
        "scores": {
            "puntuacion_final": analisis.get("puntuacion_final", 0),
            "puntuacion_transcripcion": analisis.get("puntuacion_transcripcion", 0)
        },
        "recomendacion": analisis.get("recomendacion", ""),
        "transcripcion_json": transcripcion_json
    }
    
    # Guardar transcripción JSON con nombre del proveedor
    proveedor_nombre = AI_PROVIDER.upper()
    ruta_transcripcion_json = f"{base};transcripcion_{proveedor_nombre}.json"
    try:
        with open(ruta_transcripcion_json, "w", encoding="utf-8") as f:
            json.dump(transcripcion_json, f, ensure_ascii=False, indent=4)
        log(f"Transcripción JSON guardada en {ruta_transcripcion_json}")
    except Exception as e:
        log(f"Error guardando {ruta_transcripcion_json}: {e}")
    
    return evaluacion_estandar