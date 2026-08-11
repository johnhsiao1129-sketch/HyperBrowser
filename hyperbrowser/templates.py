"""
OperationTemplate / TemplateRegistry - 第2层操作模板系统
预定义常用操作组合（搜索 / 登录），按名称取用：
    plan = agent.use_template("Baidu_search", keyword="xxx")
    result = await plan.execute()
"""

from typing import Any, Callable, Dict, List, Optional

from .plan import OperationPlan


class OperationTemplate:
    """操作模板：将参数转成 OperationPlan 的构建器"""

    def __init__(
        self,
        name: str,
        category: str = "general",
        description: str = "",
        build: Optional[Callable[..., OperationPlan]] = None,
    ):
        self.name = name
        self.category = category
        self.description = description
        self._build = build

    def __call__(self, agent, **params) -> OperationPlan:
        if self._build is None:
            raise ValueError(f"Template '{self.name}' has no builder")
        return self._build(agent, **params)

    def __repr__(self) -> str:
        return f"<OperationTemplate {self.name} ({self.category})>"


class TemplateRegistry:
    """模板注册表"""

    def __init__(self):
        self._templates: Dict[str, OperationTemplate] = {}

    def register(self, template: OperationTemplate) -> None:
        self._templates[template.name] = template

    def get(self, name: str) -> Optional[OperationTemplate]:
        return self._templates.get(name)

    def list(self, category: Optional[str] = None) -> List[OperationTemplate]:
        if category is None:
            return list(self._templates.values())
        return [t for t in self._templates.values() if t.category == category]


# ========================================================================
# 内置模板构建器
# ========================================================================


def _build_search(
    agent,
    keyword: str,
    url: str,
    input_sel: str,
    submit_sel: str,
) -> OperationPlan:
    """通用搜索模板：导航 -> 输入关键词 -> 点击搜索"""
    return (
        agent.do(url)
        .input(input_sel, keyword)
        .click(submit_sel)
    )


def _build_login(
    agent,
    url: str,
    username_sel: str,
    password_sel: str,
    submit_sel: str,
    username: str,
    password: str,
) -> OperationPlan:
    """通用登录模板：导航 -> 填用户名/密码 -> 提交"""
    return (
        agent.do(url)
        .input(username_sel, username)
        .input(password_sel, password)
        .click(submit_sel)
    )


# ========================================================================
# 全局注册表 + 内置模板
# ========================================================================

registry = TemplateRegistry()

registry.register(
    OperationTemplate(
        name="Baidu_search",
        category="search",
        description="百度搜索",
        build=lambda agent, keyword: _build_search(
            agent, keyword,
            "https://www.baidu.com", "#kw", "#su",
        ),
    )
)

registry.register(
    OperationTemplate(
        name="Google_search",
        category="search",
        description="Google 搜索",
        build=lambda agent, keyword: _build_search(
            agent, keyword,
            "https://www.google.com",
            "input[name='q']", "input[name='btnK']",
        ),
    )
)

registry.register(
    OperationTemplate(
        name="Bing_search",
        category="search",
        description="Bing 搜索",
        build=lambda agent, keyword: _build_search(
            agent, keyword,
            "https://www.bing.com", "input[name='q']", "input[name='q']",
        ),
    )
)

registry.register(
    OperationTemplate(
        name="Taobao_search",
        category="search",
        description="淘宝搜索",
        build=lambda agent, keyword: _build_search(
            agent, keyword,
            "https://www.taobao.com",
            "#q", "#J_TSearchForm > div.search-button > button",
        ),
    )
)

registry.register(
    OperationTemplate(
        name="github_login",
        category="login",
        description="GitHub 登录",
        build=lambda agent, username, password: _build_login(
            agent,
            "https://github.com/login",
            "#login_field", "#password", "input[type='submit']",
            username, password,
        ),
    )
)

__all__ = ["OperationTemplate", "TemplateRegistry", "registry"]
