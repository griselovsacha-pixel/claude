import asyncio
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, limit: float = 1.0):
        self.limit = limit
        self._users: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        now = asyncio.get_event_loop().time()
        last = self._users.get(user_id, 0)
        if now - last < self.limit:
            await event.answer("⏳ Пожалуйста, не так быстро!")
            return
        self._users[user_id] = now
        return await handler(event, data)
