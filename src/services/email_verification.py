from src.core.auth.creation_tokens import create_token
from src.repositories.protocols import VerificationTokenRepo
from src.schemas.exceptions.users import UserAlreadyVerifiedException



class EmailVerificationService:
    def __init__(self, verification_token_repo: VerificationTokenRepo):
        """Инициализировать сервис подтверждения email.

        Args:
            verification_token_repo (VerificationTokenRepo): Репозиторий токенов
                подтверждения email.
        """
        self.verification_token_repo = verification_token_repo

    
    async def save_verification_token(
        self,
        user_id: int,
        is_verified: bool
    ) -> str:
        """Сгенерировать и сохранить токен подтверждения email.

        Args:
            user_id (int): Идентификатор пользователя.
            is_verified (bool): Подтверждён ли уже email пользователя.

        Raises:
            UserAlreadyVerifiedException: Email пользователя уже подтверждён.

        Returns:
            str: Сгенерированный токен подтверждения.
        """
        if is_verified:
            raise UserAlreadyVerifiedException
        
        token, _ = create_token()
        await self.verification_token_repo.save_verification_token(
            user_id=user_id,
            token=token,
        )

        return token
    


        

        
