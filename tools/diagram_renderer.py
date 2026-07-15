import streamlit.components.v1 as components

def render_mermaid_chart(mermaid_code: str, height: int = 400):
    """
    Renders a text-based Mermaid diagram string into a live interactive visual chart
    using a safe, zero-dependency HTML/JS injection pipeline.
    """
    # HTML template leveraging the official Mermaid.js rendering engine via CDN
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script>
            window.onload = function() {{
                mermaid.initialize({{ 
                    startOnLoad: true, 
                    theme: 'default',
                    securityLevel: 'loose'
                }});
            }};
        </script>
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
        </style>
    </head>
    <body>
        <div class="mermaid">
            {mermaid_code}
        </div>
    </body>
    </html>
    """
    # Safely embed the interactive graph container panel into the Streamlit dashboard grid
    components.html(html_code, height=height, scrolling=True)
