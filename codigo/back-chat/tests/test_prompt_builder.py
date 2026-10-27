"""
Unit tests for PromptBuilder operations.
Verifies that the System Prompt defines only the technical assistant role for forms/formats/regulations
and that specific normative documents and situations are injected dynamically via the User Prompt (RAG).
"""

from src.domain.entities import ErrorDiagnostic, KnowledgeSource
from src.domain.value_objects import ErrorPhase, KnowledgeScope
from src.models.common import UIContext, UserContext
from src.operations.prompt_builder import PromptBuilder


def test_build_system_prompt_for_doctor_and_nurse():
    doctor = UserContext(
        usuario="dr.carlos",
        eps="EPS_SURA",
        ips_code="631300040301",
        permisos="PERFIL_IPS_MEDICO"
    )
    prompt_doc = PromptBuilder.build_system_prompt(doctor, client_id="sigires", client_name="SIGIRES")
    assert "Estimado Dr. dr.carlos" in prompt_doc
    assert "formularios" in prompt_doc.lower()
    assert "reglamentos" in prompt_doc.lower()
    # Specific regulations must come from RAG search, not be hardcoded in the system prompt
    assert "118 variables" not in prompt_doc
    assert "Juan Camilo Avendaño" in prompt_doc
    assert "Fran Sneider Quincha" in prompt_doc
    assert "Adriana Moreno" in prompt_doc

    nurse = UserContext(
        usuario="enf.laura",
        eps="EPS_SANITAS",
        ips_code="110010999901",
        permisos="PERFIL_IPS_ENFERMERO"
    )
    prompt_nurse = PromptBuilder.build_system_prompt(nurse, client_id="sigires", client_name="SIGIRES")
    assert "Enfermería enf.laura" in prompt_nurse


def test_build_system_prompt_for_auditor():
    user = UserContext(
        usuario="auditor.sura",
        eps="EPS_SURA",
        ips_code="631300040301",
        permisos="PERFIL_EPS_AUDITOR"
    )
    prompt = PromptBuilder.build_system_prompt(user, client_id="sigires")
    assert "Estimado Auditor (EPS_SURA)" in prompt


def test_build_system_prompt_for_other_client():
    user = UserContext(
        usuario="analista1",
        eps="CORP_SALUD",
        ips_code="100200",
        permisos="PERFIL_ANALISTA"
    )
    prompt = PromptBuilder.build_system_prompt(user, client_id="otra_empresa", client_name="Clínica Central")
    assert "Clínica Central" in prompt
    assert "Juan Camilo Avendaño" in prompt
    assert "Fran Sneider Quincha" in prompt
    assert "Adriana Moreno" in prompt


def test_build_user_prompt_injects_search_documents_and_context():
    ui = UIContext(
        url="https://plataforma.salud.co/formularios/enfermeria",
        pagina_actual="FORMULARIO_SIGNOS_VITALES",
        modulo="FORMULARIOS_CLINICOS",
        formato_archivo="CSV_ESTANDAR",
    )
    user = UserContext(
        usuario="enf.maria",
        eps="EPS_SANITAS",
        ips_code="631300040301",
        permisos="PERFIL_IPS_ENFERMERO"
    )
    diag = ErrorDiagnostic(
        detected_code="CE_VAR_014_INVAL",
        error_phase=ErrorPhase.FASE_2_CE,
        affected_variable_number=14,
        affected_variable_name="Condicion_Usuaria",
        affected_row=45
    )
    sources = [
        KnowledgeSource(
            document_title="Reglamento Técnico de Formularios",
            scope=KnowledgeScope.GLOBAL,
            section="Sección Campo 14",
            snippet="Regla recuperada dinámicamente desde el servicio de búsqueda"
        )
    ]

    prompt = PromptBuilder.build_user_prompt(
        query="¿Cómo corrijo este error en el formulario?",
        system_logs="Error fila 45",
        ui_context=ui,
        user_context=user,
        diagnostic=diag,
        knowledge_sources=sources,
    )

    assert "631300040301" in prompt
    assert "CE_VAR_014_INVAL" in prompt
    assert "Fila / Registro Afectado: 45" in prompt
    assert "Reglamento Técnico de Formularios" in prompt
    assert "Regla recuperada dinámicamente desde el servicio de búsqueda" in prompt
