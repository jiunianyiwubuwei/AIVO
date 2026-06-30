"""Agent 服务层"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import AgentProperties, AiProperties


class AgentService:
    """Agent 服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_agent_properties(
        self,
        skip: int = 0,
        limit: int = 20,
        ai_mode: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> tuple[list[AgentProperties], int]:
        """获取 Agent 配置列表"""
        query = select(AgentProperties).where(AgentProperties.del_flag == 0)

        if ai_mode:
            query = query.where(AgentProperties.ai_mode == ai_mode)
        if agent_name:
            query = query.where(AgentProperties.agent_name.contains(agent_name))

        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(AgentProperties.id.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = result.scalars().all()

        return list(items), total

    async def get_agent_property(self, agent_id: int) -> Optional[AgentProperties]:
        result = await self.db.execute(
            select(AgentProperties).where(
                AgentProperties.id == agent_id,
                AgentProperties.del_flag == 0
            )
        )
        return result.scalar_one_or_none()

    async def get_by_api_flow_id(self, api_flow_id: str) -> Optional[AgentProperties]:
        result = await self.db.execute(
            select(AgentProperties).where(
                AgentProperties.api_flow_id == api_flow_id,
                AgentProperties.del_flag == 0
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, agent_name: str) -> Optional[AgentProperties]:
        result = await self.db.execute(
            select(AgentProperties).where(
                AgentProperties.agent_name == agent_name,
                AgentProperties.del_flag == 0
            )
        )
        return result.scalar_one_or_none()

    async def create_agent_property(
        self,
        agent_name: str,
        api_flow_id: Optional[str] = None,
        ai_mode: Optional[str] = None,
        ai_properties_id: Optional[int] = None,
        system_prompt: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> AgentProperties:
        agent = AgentProperties(
            agent_name=agent_name,
            api_flow_id=api_flow_id,
            ai_mode=ai_mode,
            ai_properties_id=ai_properties_id,
            system_prompt=system_prompt,
            api_key=api_key,
            api_secret=api_secret,
            del_flag=0,
        )
        self.db.add(agent)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def update_agent_property(
        self,
        agent_id: int,
        **kwargs,
    ) -> Optional[AgentProperties]:
        agent = await self.get_agent_property(agent_id)
        if agent is None:
            return None

        for key, value in kwargs.items():
            if hasattr(agent, key) and value is not None:
                setattr(agent, key, value)

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def delete_agent_property(self, agent_id: int, soft: bool = True) -> bool:
        agent = await self.get_agent_property(agent_id)
        if agent is None:
            return False
        if soft:
            agent.del_flag = 1
        else:
            await self.db.delete(agent)
        await self.db.flush()
        await self.db.commit()
        return True


class AiPropertiesService:
    """AI 模型配置服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_ai_properties(
        self,
        skip: int = 0,
        limit: int = 20,
        ai_type: Optional[str] = None,
        is_enabled: Optional[int] = None,
        ai_name: Optional[str] = None,
    ) -> tuple[list[AiProperties], int]:
        """获取 AI 模型配置列表"""
        query = select(AiProperties).where(AiProperties.del_flag == 0)

        if ai_type:
            query = query.where(AiProperties.ai_type == ai_type)
        if is_enabled is not None:
            query = query.where(AiProperties.is_enabled == is_enabled)
        if ai_name:
            query = query.where(AiProperties.ai_name.contains(ai_name))

        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(AiProperties.id.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = result.scalars().all()

        return list(items), total

    async def get_ai_property(self, ai_id: int) -> Optional[AiProperties]:
        result = await self.db.execute(
            select(AiProperties).where(
                AiProperties.id == ai_id,
                AiProperties.del_flag == 0
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, ai_name: str) -> Optional[AiProperties]:
        result = await self.db.execute(
            select(AiProperties).where(
                AiProperties.ai_name == ai_name,
                AiProperties.del_flag == 0
            )
        )
        return result.scalar_one_or_none()

    async def create_ai_property(
        self,
        ai_name: str,
        ai_type: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_url: Optional[str] = None,
        model_name: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        is_enabled: Optional[int] = None,
        enable_thinking: Optional[int] = None,
        thinking_budget_tokens: Optional[int] = None,
        project_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> AiProperties:
        ai = AiProperties(
            ai_name=ai_name,
            ai_type=ai_type,
            api_key=api_key,
            api_secret=api_secret,
            api_url=api_url,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            is_enabled=is_enabled,
            enable_thinking=enable_thinking,
            thinking_budget_tokens=thinking_budget_tokens,
            project_id=project_id,
            organization_id=organization_id,
            del_flag=0,
        )
        self.db.add(ai)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(ai)
        return ai

    async def update_ai_property(
        self,
        ai_id: int,
        **kwargs,
    ) -> Optional[AiProperties]:
        ai = await self.get_ai_property(ai_id)
        if ai is None:
            return None

        for key, value in kwargs.items():
            if hasattr(ai, key) and value is not None:
                setattr(ai, key, value)

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(ai)
        return ai

    async def delete_ai_property(self, ai_id: int, soft: bool = True) -> bool:
        ai = await self.get_ai_property(ai_id)
        if ai is None:
            return False
        if soft:
            ai.del_flag = 1
        else:
            await self.db.delete(ai)
        await self.db.flush()
        await self.db.commit()
        return True

    async def get_enabled_ai(self) -> list[AiProperties]:
        result = await self.db.execute(
            select(AiProperties).where(
                AiProperties.del_flag == 0,
                AiProperties.is_enabled == 1
            )
        )
        return list(result.scalars().all())
