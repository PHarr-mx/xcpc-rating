import reflex as rx

config = rx.Config(
    app_name="xcpc_web",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)