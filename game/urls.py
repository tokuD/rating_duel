from django.urls import path

from . import views

app_name = 'game'

urlpatterns = [
    path('<str:league_name>/search_for_opponent_ajax/', views.SearchForOpponentAjaxView.as_view(), name='search_for_opponent_ajax'),
    path('<str:league_name>/search_for_opponent/', views.SearchForOpponentView.as_view(), name='search_for_opponent'),
    path('<str:league_name>/room/<str:room_name>/', views.RoomView.as_view(), name='room'),
    path('enroll/<str:league_name>/', views.CreateResultTableView.as_view(), name='create_result_table'),
    path('league_list/', views.LeagueListView.as_view(), name='league_list'),
    path('', views.HomeView.as_view(), name='home'),
]