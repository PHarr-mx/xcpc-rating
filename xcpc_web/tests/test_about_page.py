"""关于页（/about）冒烟。

纯静态页无 State、无数据依赖。只做组件构建检查——
不要在这里导入 ``xcpc_web.xcpc_web``（app 模块）：其顶层 ``rx.App()`` +
全部 ``add_page`` 会初始化全局状态树，破坏 conftest 的手工状态链测试基建
（现象：web_engine 的 monkeypatch 时序被收集期导入打乱，出现跨测试的
DB 复用与 UNIQUE 冲突）。路由注册是否生效交给浏览器手工验收。
"""

from xcpc_web.pages.about import about


def test_about_page_builds():
    assert about() is not None
