__all__ = ( # Этот __init__.py нужен, чтобы taskiq воркер увидел эти задачи (мы указали явно --fs-discover --tasks-pattern "src/tasks")
    "cleanup_expired_tokens",
    "send_email_for_verification",
    "log_action",
)

from .clear_expired_tokens import cleanup_expired_tokens
from .email_send_tasks import send_email_for_verification
from .log_tasks import log_action
