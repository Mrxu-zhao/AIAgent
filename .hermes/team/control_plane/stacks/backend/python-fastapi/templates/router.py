from fastapi import APIRouter, HTTPException, Depends
from typing import List

from .service import ${ClassName}Service
from .schemas import ${ClassName}DTO

router = APIRouter(prefix="${endpoint}", tags=["${class_name}"])


@router.get("/", response_model=List[${ClassName}DTO])
async def list_items(service: ${ClassName}Service = Depends()):
    return await service.list()


@router.get("/{item_id}", response_model=${ClassName}DTO)
async def get_item(item_id: int, service: ${ClassName}Service = Depends()):
    item = await service.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/", response_model=${ClassName}DTO, status_code=201)
async def create_item(dto: ${ClassName}DTO, service: ${ClassName}Service = Depends()):
    return await service.create(dto)


@router.put("/{item_id}", response_model=${ClassName}DTO)
async def update_item(item_id: int, dto: ${ClassName}DTO, service: ${ClassName}Service = Depends()):
    return await service.update(item_id, dto)


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: int, service: ${ClassName}Service = Depends()):
    await service.delete(item_id)
