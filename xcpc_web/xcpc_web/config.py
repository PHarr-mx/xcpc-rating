"""Web 层配置：OJ 个人页外链模板等。

handle 直接拼入平台个人页 URL；未登记的平台（如牛客，个人页需要数字 UID
而非 handle）不生成外链，仅展示文本。
"""

OJ_PROFILE_URL_TEMPLATES: dict[str, str] = {
    "codeforces": "https://codeforces.com/profile/{handle}",
    "atcoder": "https://atcoder.jp/users/{handle}",
    "luogu": "https://www.luogu.com.cn/user/{handle}",
}

_PLATFORM_LABELS = {
    "codeforces": "Codeforces",
    "atcoder": "AtCoder",
    "luogu": "洛谷",
    "nowcoder": "牛客",
}


def platform_label(platform: str) -> str:
    """平台展示名；未知平台原样返回。"""
    return _PLATFORM_LABELS.get(platform, platform)


def oj_profile_url(platform: str, handle: str | None) -> str | None:
    """平台 + handle → 个人页 URL；未登记平台或空 handle 返回 None。"""
    template = OJ_PROFILE_URL_TEMPLATES.get(platform)
    if template is None or not handle:
        return None
    return template.format(handle=handle)
