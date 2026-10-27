"""
Router for Administrator Authentication and Management (auth-service).
Endpoints:
- POST /api/v1/admin/auth/login
- GET  /api/v1/admin/auth/me
- POST /api/v1/admin/auth/change-password
- GET  /api/v1/admin/users (SUPERADMIN only)
- POST /api/v1/admin/users (SUPERADMIN only)
- PATCH /api/v1/admin/users/{admin_id} (SUPERADMIN only)
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.core.exceptions import ServiceError
from src.db.database import AdminUserORM
from src.dependencies import get_client_ip, get_current_admin, get_db, require_superadmin
from src.schemas import (
    AdminLoginRequest,
    AdminProfile,
    AdminTokenResponse,
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    ChangePasswordRequest,
)
from src.services.admin_service import AdminAuthService, AdminUserService

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
            client_id=result.admin.client_id,
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
):
    return AdminProfile(
        admin_id=admin.id,
        username=admin.username,
        full_name=admin.full_name,
        role=admin.role,
        client_id=admin.client_id,
        is_active=admin.is_active,
        last_login_at=admin.last_login_at,
        created_at=admin.created_at,
    )


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
# Admin User Management (SUPERADMIN only)
# ---------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=List[AdminProfile],
    status_code=status.HTTP_200_OK,
    summary="Listar Administradores",
    description="Requiere rol SUPERADMIN. Retorna la lista de todos los administradores registrados."
)
async def list_admin_users(
    actor: AdminUserORM = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    service = AdminUserService(db)
    admins = service.list_admins()
    return [
        AdminProfile(
            admin_id=a.id,
            username=a.username,
            full_name=a.full_name,
            role=a.role,
            client_id=a.client_id,
            is_active=a.is_active,
            last_login_at=a.last_login_at,
            created_at=a.created_at,
        )
        for a in admins
    ]


@router.post(
    "/users",
    response_model=AdminProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Crear Administrador",
    description="Requiere rol SUPERADMIN. Crea un nuevo administrador asignándole rol (SUPERADMIN o CLIENT_ADMIN)."
)
async def create_admin_user(
    body: AdminUserCreateRequest,
    actor: AdminUserORM = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    service = AdminUserService(db)
    try:
        new_admin = service.create_admin(
            actor=actor,
            username=body.username,
            password=body.password,
            role=body.role,
            client_id=body.client_id,
            full_name=body.full_name,
        )
        return AdminProfile(
            admin_id=new_admin.id,
            username=new_admin.username,
            full_name=new_admin.full_name,
            role=new_admin.role,
            client_id=new_admin.client_id,
            is_active=new_admin.is_active,
            last_login_at=new_admin.last_login_at,
            created_at=new_admin.created_at,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.patch(
    "/users/{admin_id}",
    response_model=AdminProfile,
    status_code=status.HTTP_200_OK,
    summary="Actualizar Administrador",
    description="Requiere rol SUPERADMIN. Permite modificar estado, rol, cliente o contraseña de un administrador."
)
async def update_admin_user(
    admin_id: str,
    body: AdminUserUpdateRequest,
    actor: AdminUserORM = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    service = AdminUserService(db)
    changes = body.model_dump(exclude_unset=True)
    try:
        updated = service.update_admin(actor=actor, admin_id=admin_id, changes=changes)
        return AdminProfile(
            admin_id=updated.id,
            username=updated.username,
            full_name=updated.full_name,
            role=updated.role,
            client_id=updated.client_id,
            is_active=updated.is_active,
            last_login_at=updated.last_login_at,
            created_at=updated.created_at,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
