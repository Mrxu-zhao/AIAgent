from typing import List, Optional

from .repository import ${ClassName}Repository
from .schemas import ${ClassName}DTO


class ${ClassName}Service:
    def __init__(self, repo: ${ClassName}Repository):
        self.repo = repo

    async def list(self) -> List[${ClassName}DTO]:
        return await self.repo.list()

    async def get_by_id(self, item_id: int) -> Optional[${ClassName}DTO]:
        return await self.repo.get_by_id(item_id)

    async def create(self, dto: ${ClassName}DTO) -> ${ClassName}DTO:
        return await self.repo.create(dto)

    async def update(self, item_id: int, dto: ${ClassName}DTO) -> ${ClassName}DTO:
        return await self.repo.update(item_id, dto)

    async def delete(self, item_id: int) -> None:
        await self.repo.delete(item_id)
