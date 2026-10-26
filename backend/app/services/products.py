"""商品配置：价格以服务端为准，前端只提交商品编号"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    price_wei: int


PRODUCTS: dict[str, Product] = {
    "lesson17": Product(id="lesson17", name="第十七课 课程资料", price_wei=10**16),  # 0.01 ETH
}


def get_product(product_id: str) -> Product | None:
    return PRODUCTS.get(product_id)
