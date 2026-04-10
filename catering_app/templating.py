from fastapi.templating import Jinja2Templates

try:
    templates = Jinja2Templates(directory="catering_app/templates")
except RuntimeError:
    templates = None
