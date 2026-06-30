from django.urls import path

from sentinel.api_keys.views import APIKeyCreateView, APIKeyDetailView, APIKeyListView

urlpatterns = [
    path("", APIKeyListView.as_view(), name="api-key-list"),
    path("create/", APIKeyCreateView.as_view(), name="api-key-create"),
    path("<str:key_id>/", APIKeyDetailView.as_view(), name="api-key-detail"),
]
