import pytest

from app.errors import AppError, ErrorCode
from app.tools.calculator import calculate


@pytest.mark.parametrize(
    "op,a,b,expected",
    [("add", 2, 3, 5), ("subtract", 2, 3, -1), ("multiply", 4, 3, 12), ("divide", 9, 3, 3)],
)
async def test_operations(op, a, b, expected):
    assert (await calculate(op, a, b))["result"] == expected


async def test_divide_by_zero():
    with pytest.raises(AppError) as exc:
        await calculate("divide", 1, 0)
    assert exc.value.code == ErrorCode.INVALID_INPUT


async def test_invalid_operation():
    with pytest.raises(AppError) as exc:
        await calculate("power", 1, 2)
    assert exc.value.code == ErrorCode.INVALID_INPUT
