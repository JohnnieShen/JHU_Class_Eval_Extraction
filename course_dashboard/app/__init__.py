from flask import Flask
from flask_caching import Cache

cache = Cache(config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})
def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    cache.init_app(app)
    from .routes.main import main_bp
    app.register_blueprint(main_bp)

    from .routes.analytics import analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    return app
