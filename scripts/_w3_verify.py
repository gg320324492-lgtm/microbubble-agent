from app.core.database import engine, async_session, Base, get_db, _get_engine, _get_session_factory
from app.core.database import _EngineProxy, _SessionFactoryProxy

print("✓ 老 import 全部 OK: engine / async_session / Base / get_db")
print(f"  engine type: {type(engine).__name__}")
print(f"  async_session type: {type(async_session).__name__}")

# Test 2: 代理对象方法访问
print(f"  engine proxy: {engine!r}")
print(f"  async_session callable: {callable(async_session)}")

# Test 3: 验证 _get_engine() 第一次在 running loop 里创建真 engine
import asyncio

async def test_lazy_engine_creation():
    """loop 内调 _get_engine() 应返真 AsyncEngine (并绑当前 loop)."""
    real_engine = _get_engine()
    print(f"  real engine type: {type(real_engine).__name__}")
    print(f"  current_loop == _engine_loop: {asyncio.get_running_loop() is _get_engine_loop_id()}")

def _get_engine_loop_id():
    """peek into _engine_loop without making it public."""
    import app.core.database as dbmod
    return dbmod._engine_loop

# Skip loop test - just verify the function exists
print("  _get_engine callable: ", callable(_get_engine))
print("  _get_session_factory callable: ", callable(_get_session_factory))

# Test 4: 模拟 W5+1 follow-up 复现场景: 两次跨 loop 调用
async def test_two_loops():
    """loop A 创 engine → loop B 调应重建."""
    import app.core.database as dbmod

    # Loop A
    loop_a = asyncio.new_event_loop()
    asyncio.set_event_loop(loop_a)
    try:
        with loop_a:
            engine_a = _get_engine()
            loop_a_id = id(asyncio.get_running_loop())
            print(f"  loop_a engine: {id(engine_a)}, loop id: {loop_a_id}")
    finally:
        loop_a.close()

    # Loop B (新 loop, 模拟 pytest loop_scope=function)
    loop_b = asyncio.new_event_loop()
    asyncio.set_event_loop(loop_b)
    try:
        with loop_b:
            engine_b = _get_engine()
            loop_b_id = id(asyncio.get_running_loop())
            print(f"  loop_b engine: {id(engine_b)}, loop id: {loop_b_id}")
            print(f"  expect: engine_a is NOT engine_b (loop 切换重建)")
            print(f"  actual: {engine_a is not engine_b}")
    finally:
        loop_b.close()

# 这里我们只验证 import + 代理行为, 真 engine 创建需要 DATABASE_URL 可达
# (SKIP 模式没真 DB, _get_engine 调 create_async_engine 可能 hang on first connect)
print()
print("✓ all import paths + proxy types verified")
