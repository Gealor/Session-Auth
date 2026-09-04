from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from src.core.auth.security import get_current_user
from src.core.logger import log
from src.dependencies import get_user_service
from src.schemas.exceptions.database import UniqueException
from src.schemas.exceptions.users import NewPasswordMatchWithOldException, UserNotDeletedException, UserNotFoundException
from src.schemas.response_schemas import ResponseSchema
from src.schemas.user_schemas import UserRead, UserUpdate
from src.services.user_service import UserService
from src.tasks.log_tasks import log_action

router = APIRouter(prefix="/user")


@router.get("/me")
async def read_me(
    current_user: UserRead = Depends(get_current_user),
) -> UserRead:
    await log_action.kiq(current_user.id)
    return UserRead.model_validate(current_user)


@router.patch("/update/me")
async def update_my_profile(
    update_data: UserUpdate,
    current_user: UserRead = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserRead:
    try:
        result = await user_service.update_user(
            user_id=current_user.id, update_data=update_data
        )
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except UniqueException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"\'{e}\' with this value already exist"
        )
    except Exception as e:
        log.error("Unexpected error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error"
        )

    return result


@router.delete("/delete/me")
async def delete_my_account(
    current_user: UserRead = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ResponseSchema:
    try:
        result = await user_service.delete_self_user(
            user_id=current_user.id
        )
    except Exception as e:
        log.error("Unexpected error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error"
        )

    return result


@router.patch("/restore")
async def restore_user(
    user_id: int,
    user_service: UserService = Depends(get_user_service),
) -> ResponseSchema:
    try:
        result = await user_service.restore_deleted_user(user_id=user_id)
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except UserNotDeletedException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User not deleted"
        )
    except Exception as e:
        log.error("Unexpected error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error"
        )

    return result

@router.patch("/password")
async def update_user_password_by_id(
    user_id: int = Query(),
    new_password: str = Body(embed=True),
    user_service: UserService = Depends(get_user_service),
) -> ResponseSchema:
    try:
        await user_service.update_user_password(
            user_id=user_id, 
            new_password=new_password
        )
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User by these id not exist"
        )
    except NewPasswordMatchWithOldException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password match with old. Please choose different password."
        )

    return ResponseSchema(
        msg=f"Password change to {new_password}"
    )
