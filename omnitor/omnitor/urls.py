from .views.pages import urlpatterns as view
from .views.apis import urlpatterns as api

urlpatterns = [
   *api,
   *view
]
