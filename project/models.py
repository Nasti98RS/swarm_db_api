from sqlmodel import Field, SQLModel
from uuid import UUID, uuid4



class Producto(SQLModel, table=True):
    id: UUID = Field(default=uuid4(), primary_key=True)
    nombre: str = Field()
    precio: float = Field()
    cantidad_en_almacen: int = Field(default=0)
    descuento_por_devolucion: int = Field(default=10)


class Usuario(SQLModel, table=True):
    id: UUID = Field(default=uuid4(), primary_key=True)
    nombre: str = Field()
    empresa: str = Field()
    email: str = Field()
