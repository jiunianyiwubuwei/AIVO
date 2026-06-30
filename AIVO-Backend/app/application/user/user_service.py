"""用户服务层"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token
from app.infrastructure.database.models import User


class UserService:
    """用户服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(self, username: str, password: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        if user is None or user.del_flag == 1:
            return None
        if not verify_password(password, user.password or ""):
            return None
        return user

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        username: str,
        password: str,
        real_name: Optional[str] = None,
        phone: Optional[str] = None,
        mail: Optional[str] = None,
    ) -> User:
        user = User(
            username=username,
            password=hash_password(password),
            real_name=real_name,
            phone=phone,
            mail=mail,
            deletion_time=None,
            create_time=datetime.now(timezone.utc),
            update_time=datetime.now(timezone.utc),
            del_flag=0,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def list_users(
        self,
        username: Optional[str] = None,
        real_name: Optional[str] = None,
        del_flag: int = 0,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        conditions = [User.del_flag == del_flag]
        if username:
            conditions.append(User.username.contains(username))
        if real_name:
            conditions.append(User.real_name.contains(real_name))

        base_query = select(User).where(*conditions)
        count_query = select(User).where(*conditions)
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count()).select_from(count_query.subquery())
        )
        total = count_result.scalar() or 0

        query = base_query.order_by(User.id.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def update_user(
        self,
        user_id: int,
        real_name: Optional[str] = None,
        phone: Optional[str] = None,
        mail: Optional[str] = None,
        del_flag: Optional[int] = None,
    ) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        if real_name is not None:
            user.real_name = real_name
        if phone is not None:
            user.phone = phone
        if mail is not None:
            user.mail = mail
        if del_flag is not None:
            user.del_flag = del_flag
            if del_flag == 1:
                user.deletion_time = datetime.now(timezone.utc)
            else:
                user.deletion_time = None
        user.update_time = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_password(self, user_id: int, new_password: str) -> bool:
        user = await self.get_by_id(user_id)
        if user is None:
            return False
        user.password = hash_password(new_password)
        user.update_time = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.commit()
        return True

    async def delete_user(self, user_id: int, soft: bool = True) -> bool:
        user = await self.get_by_id(user_id)
        if user is None:
            return False
        if soft:
            user.del_flag = 1
            user.deletion_time = datetime.now(timezone.utc)
        else:
            await self.db.delete(user)
        await self.db.flush()
        await self.db.commit()
        return True

    async def is_username_exists(self, username: str) -> bool:
        user = await self.get_by_username(username)
        return user is not None

    def create_token(self, user: User) -> str:
        """为用户创建 JWT token"""
        return create_access_token({"sub": str(user.id), "user_id": user.id})
