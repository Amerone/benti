"""前端业务页面组件。
各页面只通过 `requests` 访问 `/api/v1`，不直接依赖 `mvp.core` 或 `mvp.api`。"""

from . import tab_commission_customer, tab_cq_engine
