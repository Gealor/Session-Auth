from core.auth.passwords import compare_hashed_passwords, hash_password
from repositories.redis.verification_token_repository import VerificationTokenRepository
from repositories.session_repository import TokenRepository
from repositories.user_repository import UserRepository
from schemas.exceptions.users import NewPasswordMatchWithOldException, UserAlreadyVerifiedException, UserNotDeletedException, UserNotFoundException
from schemas.response_schemas import ResponseSchema
from schemas.user_schemas import UserRead, UserUpdate


class UserService:
    def __init__(self, db_session, redis):
        self.db_session = db_session
        self.user_repo = UserRepository(db_session=self.db_session)
        self.verification_token_repo = VerificationTokenRepository(redis)

    async def update_user(
        self, user_id: int, update_data: UserUpdate, exclude_inactive: bool = True
    ) -> UserRead:
        user = await self.user_repo.update_user(
            user_id=user_id,
            update_data=update_data,
            exclude_inactive=exclude_inactive,
        )
        if not user:
            raise UserNotFoundException

        return UserRead.model_validate(user)

    async def delete_self_user(self, user_id: int) -> ResponseSchema:
        await self.user_repo.delete_user(user_id=user_id)
        await TokenRepository(self.db_session).delete_token(user_id=user_id)
        return ResponseSchema(
            msg="Account successfully deleted. You have been logged out."
        )

    async def restore_deleted_user(self, user_id: int) -> ResponseSchema:
        user = await self.user_repo.get_user_by_id(user_id=user_id)
        if not user:
            raise UserNotFoundException

        if not (user.deleted_at or user.is_active):
            raise UserNotDeletedException

        await self.user_repo.restore_user(user_id=user_id)
        return ResponseSchema(msg="User successfully restored")

    async def verify_user(self, token: str):
        user_id = await self.verification_token_repo.verify_and_consume_token(
            token=token,
        )
        
        user_old = await self.user_repo.get_user_by_id(user_id=user_id)
        if user_old is None:
            raise UserNotFoundException
        if user_old.is_verified:
            raise UserAlreadyVerifiedException

        data = {"is_verified": True}
        await self.user_repo.update_data_by_dict(
            user_id=user_id, dict_data=data, exclude_inactive=True
        )

    async def update_user_password(self, user_id: int, new_password: str) -> None:
        user = await self.user_repo.get_user_by_id(user_id=user_id)
        if user is None:
            raise UserNotFoundException

        new_password_bytes = new_password.encode("utf-8")
        old_password_hash = user.password.encode("utf-8")

        if compare_hashed_passwords(new_password_bytes, old_password_hash):
            raise NewPasswordMatchWithOldException
        
        updated_password = {
            "password": hash_password(new_password).decode("utf-8"),
        }

        await self.user_repo.update_data_by_dict(
            user_id=user_id,
            dict_data=updated_password,
        )


