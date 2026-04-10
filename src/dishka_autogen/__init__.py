__all__ = (
    "CONTAINER_NAME",
    "AG2Provider",
    "DishkaMiddleware",
    "FromDishka",
    "inject",
)

from dishka import FromDishka

from .autogen import CONTAINER_NAME, AG2Provider, DishkaMiddleware, inject
