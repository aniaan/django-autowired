from enum import Enum

from django.http import HttpResponse


class DefaultUrl(Enum):
    swagger_js_url = (
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui-bundle.js"
    )
    swagger_css_url = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.css"
    swagger_favicon_url = "https://fastapi.tiangolo.com/img/favicon.png"


def get_swagger_ui_html(
    *,
    openapi_url: str,
    title: str,
    swagger_js_url: str = DefaultUrl.swagger_js_url.value,
    swagger_css_url: str = DefaultUrl.swagger_css_url.value,
    swagger_favicon_url: str = DefaultUrl.swagger_favicon_url.value,
) -> HttpResponse:
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <link type="text/css" rel="stylesheet" href="{swagger_css_url}">
    <link rel="shortcut icon" href="{swagger_favicon_url}">
    <title>{title}</title>
    </head>
    <body>
    <div id="swagger-ui">
    </div>
    <script src="{swagger_js_url}"></script>
    <!-- `SwaggerUIBundle` is now available on the page -->
    <script>
    const ui = SwaggerUIBundle({{
        url: '{openapi_url}',
    """

    html += """
        dom_id: '#swagger-ui',
        presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
        deepLinking: true,
        showExtensions: true,
        showCommonExtensions: true
    })"""

    html += """
    </script>
    </body>
    </html>
    """
    return HttpResponse(html)
