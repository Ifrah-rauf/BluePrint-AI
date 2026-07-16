import json
import streamlit.components.v1 as components


def render_mermaid_chart(mermaid_code: str, height: int = 400):
    """
    Renders a text-based Mermaid diagram string into a live interactive visual chart
    using a safe, zero-dependency HTML/JS injection pipeline.
    """
    # Safely pass the diagram text into JS as a JSON string, instead of interpolating
    # it directly into the HTML. Raw interpolation breaks (or silently fails to render)
    # if the diagram contains characters like <, >, &, or quotes in node labels.
    safe_mermaid_code = json.dumps(mermaid_code)

    # HTML template leveraging the official Mermaid.js rendering engine via CDN.
    # NOTE: Mermaid has been ESM-only since v10 - there is no reliable global
    # "mermaid.min.js" UMD bundle to <script src="..."> anymore. It must be loaded
    # via a pinned, versioned ESM import, or `mermaid` is undefined and nothing renders.
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                background-color: transparent;
                display: flex;
                justify-content: center;
                align-items: center;
                margin: 0;
                padding: 10px;
                font-family: sans-serif;
            }}
            .mermaid {{
                width: 100%;
                text-align: center;
            }}
            .mermaid-error {{
                color: #B42318;
                font-size: 0.85rem;
                text-align: center;
                white-space: pre-wrap;
            }}
        </style>
    </head>
    <body>
        <div id="mermaid-container" class="mermaid"></div>
        <div id="mermaid-error" class="mermaid-error"></div>

        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';

            const diagramDefinition = {safe_mermaid_code};
            const container = document.getElementById('mermaid-container');
            const errorBox = document.getElementById('mermaid-error');

            mermaid.initialize({{
                startOnLoad: false,
                theme: 'default',
                securityLevel: 'loose'
            }});

            (async () => {{
                try {{
                    const {{ svg, bindFunctions }} = await mermaid.render('mermaid-svg', diagramDefinition);
                    container.innerHTML = svg;
                    if (bindFunctions) bindFunctions(container);
                }} catch (err) {{
                    // Surface parse/render errors instead of a silent blank output.
                    errorBox.textContent = 'Diagram failed to render: ' + err.message;
                }}
            }})();
        </script>
    </body>
    </html>
    """
    # Safely embed the interactive graph container panel into the Streamlit dashboard grid
    components.html(html_code, height=height, scrolling=True)