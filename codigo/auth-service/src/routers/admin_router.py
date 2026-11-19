"""
Router for Administrator Authentication and Management (auth-service).
Endpoints:
- POST  /api/v1/admin/auth/login
- GET   /api/v1/admin/auth/me
- POST  /api/v1/admin/auth/change-password
- GET   /api/v1/admin/users (GLOBAL_ADMIN only)
- POST  /api/v1/admin/users (GLOBAL_ADMIN only)
- PATCH /api/v1/admin/users/{admin_id} (GLOBAL_ADMIN only)
- GET   /api/v1/admin/organizations (GLOBAL_ADMIN all, ORG_ADMIN own)
- POST  /api/v1/admin/organizations (GLOBAL_ADMIN only)
- PATCH /api/v1/admin/organizations/{org_id} (GLOBAL_ADMIN full, ORG_ADMIN site_label/site_label_plural only)
- GET   /api/v1/admin/sites (GLOBAL_ADMIN all/filtered, ORG_ADMIN own)
- POST  /api/v1/admin/sites (GLOBAL_ADMIN / ORG_ADMIN own)
- PATCH /api/v1/admin/sites/{site_id} (GLOBAL_ADMIN / ORG_ADMIN own)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.core.exceptions import ServiceError
from src.db.database import AdminUserORM
from src.dependencies import get_client_ip, get_current_admin, get_db, require_global_admin
from src.schemas import (
    AdminLoginRequest,
    AdminProfile,
    AdminTokenResponse,
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    ChangePasswordRequest,
    OrganizationCreateRequest,
    OrganizationSummaryResponse,
    OrganizationUpdateRequest,
    SiteCreatedResponse,
    SiteCreateRequest,
    SiteSummaryResponse,
    SiteUpdatedResponse,
    SiteUpdateRequest,
)
from src.services.admin_service import AdminAuthService, AdminUserService
from src.services.organization_service import OrganizationSiteService

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Authentication & Management"])


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/auth/login",
    response_model=AdminTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Inicio de Sesión de Administrador",
    description="Autentica a un administrador mediante usuario y contraseña (bcrypt). Retorna token JWT de admin."
)
async def login_admin(
    body: AdminLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = get_client_ip(
        x_forwarded_for=request.headers.get("x-forwarded-for"),
        x_real_ip=request.headers.get("x-real-ip"),
    )
    service = AdminAuthService(db)
    try:
        result = service.login(username=body.username, password=body.password, ip_address=ip)
        return AdminTokenResponse(
            access_token=result.access_token,
            expires_in_seconds=result.expires_in_seconds,
            admin_id=result.admin.id,
            username=result.admin.username,
            role=result.admin.role,
            org_id=result.admin.org_id,
            org_name=result.org_name,
            site_label=result.site_label,
            site_label_plural=result.site_label_plural,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get(
    "/auth/me",
    response_model=AdminProfile,
    status_code=status.HTTP_200_OK,
    summary="Perfil del Administrador Actual",
    description="Obtiene información del administrador autenticado según su token Bearer."
)
async def get_current_admin_profile(
    admin: AdminUserORM = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return AdminUserService(db).build_profile(admin)


@router.post(
    "/auth/change-password",
    status_code=status.HTTP_200_OK,
    summary="Cambiar Contraseña de Administrador",
    description="Permite al administrador autenticado cambiar su contraseña actual."
)
async def change_password(
    body: ChangePasswordRequest,
    admin: AdminUserORM = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = AdminAuthService(db)
    try:
        service.change_password(admin=admin, current_password=body.current_password, new_password=body.new_password)
        return {"status": "success", "message": "Contraseña actualizada exitosamente."}
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


# ---------------------------------------------------------------------------
# Admin User Management (GLOBAL_ADMIN only)
# ---------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=List[AdminProfile],
    status_code=status.HTTP_200_OK,
    summary="Listar Administradores",
    description="Requiere rol GLOBAL_ADMIN. Retorna la lista de todos los administradores registrados."
)
async def list_admin_users(
    actor: AdminUserORM = Depends(require_global_admin),
    db: Session = Depends(get_db),
):
    service = AdminUserService(db)
    admins = service.list_admins()
    return service.build_profiles(admins)


@router.post(
    "/users",
    response_model=AdminProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Crear Administrador",
    description="Requiere rol GLOBAL_ADMIN. Crea un nuevo administrador asignándole rol (GLOBAL_ADMIN u ORG_ADMIN)."
)
async def create_admin_user(
    body: AdminUserCreateRequest,
    actor: AdminUserORM = Depends(require_global_admin),
    db: Session = Depends(get_db),
):
    service = AdminUserService(db)
    try:
        new_admin = service.create_admin(
            actor=actor,
            username=body.username,
            password=body.password,
            role=body.role,
            org_id=body.org_id,
            full_name=body.full_name,
        )
        return service.build_profile(new_admin)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.patch(
    "/users/{admin_id}",
    response_model=AdminProfile,
    status_code=status.HTTP_200_OK,
    summary="Actualizar Administrador",
    description="Requiere rol GLOBAL_ADMIN. Permite modificar estado, rol, organización o contraseña de un administrador."
)
async def update_admin_user(
    admin_id: str,
    body: AdminUserUpdateRequest,
    actor: AdminUserORM = Depends(require_global_admin),
    db: Session = Depends(get_db),
):
    service = AdminUserService(db)
    changes = body.model_dump(exclude_unset=True)
    try:
        updated = service.update_admin(actor=actor, admin_id=admin_id, changes=changes)
        return service.build_profile(updated)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


# ---------------------------------------------------------------------------
# Organization & Site Management
# ---------------------------------------------------------------------------

@router.get(
    "/organizations",
    response_model=List[OrganizationSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar Organizaciones",
    description="GLOBAL_ADMIN lista todas las organizaciones; ORG_ADMIN solo ve su organización.",
)
async def list_organizations(
    actor: AdminUserORM = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = OrganizationSiteService(db)
    try:
        return service.list_organizations(actor=actor)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post(
    "/organizations",
    response_model=OrganizationSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear Organización",
    description="Requiere rol GLOBAL_ADMIN. Registra una nueva organización.",
)
async def create_organization(
    body: OrganizationCreateRequest,
    actor: AdminUserORM = Depends(require_global_admin),
    db: Session = Depends(get_db),
):
    service = OrganizationSiteService(db)
    try:
        return service.create_organization(
            actor=actor,
            org_id=body.org_id,
            nombre=body.nombre,
            busqueda_api_url=body.busqueda_api_url,
            dominios_permitidos=body.dominios_permitidos,
            site_label=body.site_label,
            site_label_plural=body.site_label_plural,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.patch(
    "/organizations/{org_id}",
    response_model=OrganizationSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar Organización",
    description="GLOBAL_ADMIN actualiza toda la configuración; ORG_ADMIN solo puede personalizar site_label y site_label_plural de su propia organización.",
)
async def update_organization(
    org_id: str,
    body: OrganizationUpdateRequest,
    actor: AdminUserORM = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = OrganizationSiteService(db)
    changes = body.model_dump(exclude_unset=True)
    try:
        return service.update_organization(actor=actor, org_id=org_id, changes=changes)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get(
    "/sites",
    response_model=List[SiteSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar Sedes",
    description="GLOBAL_ADMIN lista todas las sedes (con filtro opcional por org_id); ORG_ADMIN solo ve las de su organización.",
)
async def list_sites(
    org_id: Optional[str] = Query(None, description="Filtro opcional por org_id (solo GLOBAL_ADMIN)"),
    actor: AdminUserORM = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = OrganizationSiteService(db)
    try:
        return service.list_sites(actor=actor, org_id=org_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post(
    "/sites",
    response_model=SiteCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear Sede",
    description="Crea una nueva sede bajo una organización y retorna la API Key generada.",
)
async def create_site(
    body: SiteCreateRequest,
    actor: AdminUserORM = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = OrganizationSiteService(db)
    try:
        return service.create_site(
            actor=actor,
            org_id=body.org_id,
            nombre=body.nombre,
            site_code=body.site_code,
            dominios_permitidos=body.dominios_permitidos,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.patch(
    "/sites/{site_id}",
    response_model=SiteUpdatedResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar Sede o Rotar API Key",
    description="Actualiza datos, dominios o estado de una sede y permite rotar su API Key.",
)
async def update_site(
    site_id: str,
    body: SiteUpdateRequest,
    actor: AdminUserORM = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = OrganizationSiteService(db)
    changes = body.model_dump(exclude_unset=True)
    try:
        return service.update_site(actor=actor, site_id=site_id, changes=changes)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
