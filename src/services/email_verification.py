from redis.asyncio import Redis

from src.core.auth.creation_tokens import create_token
from src.repositories.redis.verification_token_repository import VerificationTokenRepository
from src.schemas.exceptions.users import UserAlreadyVerifiedException



class EmailVerificationService:
    def __init__(self, redis: Redis):
        self.verification_token_repo = VerificationTokenRepository(redis=redis)

    
    async def save_verification_token(
        self,
        user_id: int,
        is_verified: bool
    ) -> str:
        if is_verified:
            raise UserAlreadyVerifiedException
        
        token, _ = create_token()
        await self.verification_token_repo.save_verification_token(
            user_id=user_id,
            token=token,
        )

        return token
    


        

        
