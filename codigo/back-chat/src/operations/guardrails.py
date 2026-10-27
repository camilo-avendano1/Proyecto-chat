"""
Behavioral Guardrails and Pre-LLM Filters for Chat Assistant.
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.

Protects LLM resources and enforces strict behavioral boundaries:
1. Fast-Path Greetings / Courtesies: Answer common greetings instantly with 0 LLM tokens.
2. Prompt Injection & Jailbreak Defense: Blocks evasion, prompt leakage, and roleplay exploits.
3. Out-of-Domain Interception: Prevents off-topic queries (recipes, jokes, politics) without LLM calls.
4. Unauthorized Function Rejection: Prohibits code execution or out-of-scope actions.
"""

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class GuardrailResult:
    """Outcome of evaluating an incoming query against guardrails."""
    is_intercepted: bool
    status: str  # "PASS", "FAST_RESPONSE_GREETING", "SECURITY_BLOCKED", "OUT_OF_DOMAIN"
    direct_response: Optional[str] = None
    reason: Optional[str] = None
    severity: str = "INFO"  # "INFO", "WARNING", "HIGH", "CRITICAL"


class ChatGuardrails:
    """Pre-LLM Guardrail engine executing deterministic fast-path checks."""

    # ------------------------------------------------------------------------
    # 1. Greetings, Farewells, and Pleasantries Patterns
    # ------------------------------------------------------------------------
    GREETING_REGEX = re.compile(
        r'^\s*(?:¡|¿)?\s*(?:'
        r'(?:hola|hey|hi|hello|saludos)\b[,\s]*(?:buenos?\s+d[ií]as?|buenas?\s+tardes?|buenas?\s+noches?|buen\s+d[ií]a|amig[oa]|asistente|doc(?:tor)?|qu[eé]\s+tal|c[oó]mo\s+est[aá]s?|c[oó]mo\s+va|buenas?)?|'
        r'buenos?\s+d[ií]as?(?:\s+(?:a\s+todos|tardes|equipo|doc(?:tor)?))?|'
        r'buenas?\s+tardes?(?:\s+(?:a\s+todos|equipo|doc(?:tor)?))?|'
        r'buenas?\s+noches?(?:\s+(?:a\s+todos|equipo|doc(?:tor)?))?|'
        r'buen\s+d[ií]a|'
        r'qu[eé]\s+tal|c[oó]mo\s+est[aá]s?|c[oó]mo\s+va|'
        r'buenas?'
        r')\s*(?:!|\?|\.)*\s*$',
        re.IGNORECASE
    )

    FAREWELL_REGEX = re.compile(
        r'^\s*(?:¡|¿)?\s*(?:'
        r'chao|adi[oó]s|hasta\s+luego|hasta\s+pronto|bye|nos\s+vemos|hasta\s+mañana'
        r')\s*(?:!|\?|\.)*\s*$',
        re.IGNORECASE
    )

    GRATITUDE_REGEX = re.compile(
        r'^\s*(?:¡|¿)?\s*(?:'
        r'gracias|muchas\s+gracias|mil\s+gracias|te\s+agradezco|ok\s+gracias|vale\s+gracias|'
        r'much[ií]simas\s+gracias|perfecto\s+gracias'
        r')\s*(?:!|\?|\.)*\s*$',
        re.IGNORECASE
    )

    IDENTITY_REGEX = re.compile(
        r'^\s*(?:¡|¿)?\s*(?:'
        r'qui[eé]n\s+eres|c[oó]mo\s+te\s+llamas|cu[aá]l\s+es\s+tu\s+nombre|'
        r'qu[eé]\s+haces|para\s+qu[eé]\s+sirves|en\s+qu[eé]\s+puedes\s+ayudar(?:me)?|'
        r'qu[eé]\s+puedes\s+hacer|cu[aá]les\s+son\s+tus\s+funciones'
        r')\s*(?:!|\?|\.)*\s*$',
        re.IGNORECASE
    )

    AFFIRMATION_REGEX = re.compile(
        r'^\s*(?:ok|vale|listo|de\s+acuerdo|entendido|bien|perfecto|okey|okay)\s*(?:!|\?|\.)*\s*$',
        re.IGNORECASE
    )

    # ------------------------------------------------------------------------
    # 2. Prompt Injection, Jailbreaks, and Unauthorized Actions Patterns
    # ------------------------------------------------------------------------
    INJECTION_PATTERNS = [
        # Instruction overrides
        re.compile(r'ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions', re.IGNORECASE),
        re.compile(r'ignora\s+(?:todas\s+las\s+)?instrucciones\s+(?:anteriores|previas)', re.IGNORECASE),
        re.compile(r'olvida\s+(?:todas\s+tus\s+)?(?:reglas|instrucciones|directrices)', re.IGNORECASE),
        re.compile(r'disregard\s+(?:all\s+)?(?:previous|system)\s+prompts?', re.IGNORECASE),
        # Persona hijacking / Roleplay exploits
        re.compile(r'\b(?:you\s+are\s+now|ahora\s+eres|act\s+as|act[uú]a\s+como|simula\s+ser)\b', re.IGNORECASE),
        re.compile(r'\b(?:dan\s+mode|jailbreak|developer\s+mode|modo\s+desarrollador)\b', re.IGNORECASE),
        re.compile(r'\bhazte\s+pasar\s+por\b', re.IGNORECASE),
        re.compile(r'\bpretend\s+to\s+be\b', re.IGNORECASE),
        # Prompt leaking
        re.compile(r'\b(?:reveal|show|print|display|tell\s+me)\s+(?:your\s+)?(?:system\s+prompt|initial\s+prompt|instructions)\b', re.IGNORECASE),
        re.compile(r'\b(?:revela|muestra|cu[aá]l\s+es|dime|imprime)\s+(?:tu\s+)?(?:system\s+prompt|prompt\s+del\s+sistema|instrucciones\s+iniciales)\b', re.IGNORECASE),
        # Code execution or shell commands exploitation
        re.compile(r'\b(?:exec|eval|system\(|os\.system|subprocess|sh\s+-c|cmd\.exe|powershell)\b', re.IGNORECASE),
        re.compile(r'\b(?:ejecuta\s+(?:este\s+)?script|ejecuta\s+c[oó]digo|lanza\s+un\s+ataque|borra\s+la\s+base\s+de\s+datos)\b', re.IGNORECASE),
    ]

    # ------------------------------------------------------------------------
    # 3. Off-Topic / Out-of-Domain Triggers
    # ------------------------------------------------------------------------
    OUT_OF_DOMAIN_PATTERNS = [
        re.compile(r'\b(?:receta|cocinar|ingredientes\s+para|horno|pastel|arroz\s+con)\b', re.IGNORECASE),
        re.compile(r'\b(?:escribe\s+un\s+poema|poes[ií]a|canta\s+una\s+canci[oó]n|cu[eé]ntame\s+un\s+chiste)\b', re.IGNORECASE),
        re.compile(r'\b(?:partido\s+de\s+f[uú]tbol|campeonato|quien\s+gan[oó]\s+el\s+mundial)\b', re.IGNORECASE),
        re.compile(r'\b(?:hor[oó]scopo|signo\s+zodiacal|astrolog[ií]a)\b', re.IGNORECASE),
        re.compile(r'\b(?:opinasi[oó]n\s+pol[ií]tica|candidato\s+presidencial|votar\s+por)\b', re.IGNORECASE),
    ]

    # Whitelist of domain anchor terms (if any of these exist, do NOT classify as out-of-domain)
    DOMAIN_ANCHORS = [
        "formulario", "formato", "reglamento", "norma", "normativa", "documento",
        "plantilla", "anexo", "resolucion", "manual", "guia", "instructivo",
        "medico", "doctor", "enfermero", "enfermera", "profesional", "paciente",
        "radicador", "auditor", "analista", "radicacion", "cargue", "subir",
        "variable", "campo", "columna", "fila", "registro", "error", "alerta",
        "validador", "validacion", "rechazo", "inconsistencia", "archivo", "plano",
        "txt", "csv", "xml", "json", "zip", "excel", "xlsx", "fase", "delimitador",
        "pipeline", "estructura", "calidad", "dato", "eps", "ips", "habilitacion",
        "rips", "cac", "rias", "sigires", "202", "3280", "3374"
    ]

    @classmethod
    def evaluate(cls, query: str, system_logs: Optional[str] = None, client_name: str = "la Plataforma") -> GuardrailResult:
        """
        Evaluates the message. Returns a GuardrailResult.
        If is_intercepted is True, caller MUST NOT query the LLM.
        """
        clean_query = (query or "").strip()

        # Check 1: Security - Prompt Injections & Jailbreaks
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(clean_query):
                return GuardrailResult(
                    is_intercepted=True,
                    status="SECURITY_BLOCKED",
                    severity="HIGH",
                    reason="PROMPT_INJECTION_DETECTED",
                    direct_response=(
                        f"Como Asistente Técnico y Normativo de {client_name}, opero bajo estrictas "
                        "políticas de gobernanza y seguridad de la información. No tengo permitido "
                        "modificar mis directrices de comportamiento, ejecutar código o funciones externas, "
                        "ni atender instrucciones ajenas a la asistencia técnica de formularios, formatos y reglamentos."
                    )
                )

        # Check 2: Fast-Path Greetings and Courtesies
        # Prioritize greetings/pleasantries so simple "hola" responds instantly (0 tokens)
        # without forcing a lengthy error diagnosis even if background screen logs exist.
        if cls.GREETING_REGEX.match(clean_query):
            return GuardrailResult(
                is_intercepted=True,
                status="FAST_RESPONSE_GREETING",
                severity="INFO",
                reason="GREETING_DETECTED",
                direct_response=(
                    f"¡Hola! Soy tu Asistente Técnico para {client_name}.\n\n"
                    "¿En qué puedo orientarte hoy con el diligenciamiento de formularios, validación de formatos o consulta de reglamentos técnicos?"
                )
            )

        if cls.IDENTITY_REGEX.match(clean_query):
            return GuardrailResult(
                is_intercepted=True,
                status="FAST_RESPONSE_GREETING",
                severity="INFO",
                reason="IDENTITY_INQUIRY",
                direct_response=(
                    f"Soy el Asistente Técnico y Normativo de {client_name}.\n\n"
                    "Asisto a médicos, enfermeros, radicadores y auditores en el diligenciamiento y validación "
                    "de formularios en distintos formatos conforme a los reglamentos vigentes. Indícame tu consulta, "
                    "el formulario o el código de error y consultaré la documentación normativa para guiarte."
                )
            )

        if cls.GRATITUDE_REGEX.match(clean_query):
            return GuardrailResult(
                is_intercepted=True,
                status="FAST_RESPONSE_GREETING",
                severity="INFO",
                reason="GRATITUDE_DETECTED",
                direct_response=(
                    f"¡Con mucho gusto! Recuerda que estoy disponible para apoyarte en la validación y cargue "
                    f"de tus formularios y archivos según los reglamentos en {client_name}. ¡Que tengas un excelente día!"
                )
            )

        if cls.FAREWELL_REGEX.match(clean_query):
            return GuardrailResult(
                is_intercepted=True,
                status="FAST_RESPONSE_GREETING",
                severity="INFO",
                reason="FAREWELL_DETECTED",
                direct_response=(
                    f"¡Hasta luego! Quedo a tu disposición cuando requieras asistencia técnica con tus formularios y reglamentos en {client_name}."
                )
            )

        if cls.AFFIRMATION_REGEX.match(clean_query):
            return GuardrailResult(
                is_intercepted=True,
                status="FAST_RESPONSE_GREETING",
                severity="INFO",
                reason="AFFIRMATION_DETECTED",
                direct_response=(
                    f"Entendido. Si presentas alguna inconsistencia en un formulario o tienes dudas sobre un formato "
                    f"o reglamento técnico en {client_name}, por favor indícame el campo o error para orientarte."
                )
            )

        # If system logs are attached and query is not a greeting, it is a technical validation request
        has_logs = bool(system_logs and len(system_logs.strip()) > 5)

        # Check 3: Out-of-Domain Filter
        # Only check if query has more than a few words, no technical logs, and no domain anchor keywords
        if not has_logs:
            lower_query = clean_query.lower()
            contains_domain_anchor = any(anchor in lower_query for anchor in cls.DOMAIN_ANCHORS)
            if not contains_domain_anchor:
                for pattern in cls.OUT_OF_DOMAIN_PATTERNS:
                    if pattern.search(clean_query):
                        return GuardrailResult(
                            is_intercepted=True,
                            status="OUT_OF_DOMAIN",
                            severity="WARNING",
                            reason="OUT_OF_DOMAIN_QUERY",
                            direct_response=(
                                f"Mi función está especializada exclusivamente en el diagnóstico técnico de formularios, "
                                f"validación de archivos en distintos formatos y consulta de reglamentos técnicos en {client_name}.\n\n"
                                "No tengo permitido responder consultas sobre temas ajenos a la plataforma asistencial. "
                                "Si presentas alguna inconsistencia en un formulario, formato de cargue o regla de validación, "
                                "con gusto te asisto."
                            )
                        )

        # If none triggered, allow pass to search & LLM
        return GuardrailResult(
            is_intercepted=False,
            status="PASS",
            severity="INFO",
            reason="PASSED_GUARDRAILS"
        )
