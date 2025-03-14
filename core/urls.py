from django.urls import path
from .views import analyze, home, export_csv, export_pdf

app_name = "analyzer"
urlpatterns = [
    path('', home, name='home'),
    path('analyze/', analyze, name='analyze'),
    path('export-csv/', export_csv, name='export_csv'),
    path('export-pdf/', export_pdf, name='export_pdf'),
]