from app.routers.auth import router as auth_router
from app.routers.funds import router as funds_router
from app.routers.signals import router as signals_router
from app.routers.execution_list import router as execution_list_router
from app.routers.auto import router as auto_router
from app.routers.manual import router as manual_router
from app.routers.watchlist import router as watchlist_router
from app.routers.market import router as market_router
from app.routers.admin import router as admin_router
from app.routers.tools import router as tools_router
from app.routers.macro import router as macro_router

routers = [
    auth_router,
    funds_router,
    signals_router,
    execution_list_router,
    auto_router,
    manual_router,
    watchlist_router,
    market_router,
    admin_router,
    tools_router,
    macro_router,
]
