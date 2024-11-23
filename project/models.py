from sqlmodel import Field, SQLModel


class Producto(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nombre: str = Field()
    precio: float = Field()
    cantidad_en_almacen: int = Field(default=0)
    descuento_por_devolucion: int = Field(default=10)


class Usuario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nombre: str = Field()
    empresa: str = Field()
    email: str = Field()
    esta_de_vaciones: bool = Field(default=False)
