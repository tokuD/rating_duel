import json, time, random, string, secrets, math
from unicodedata import name
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.views import generic
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import mixins, get_user_model
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone

from . import models, forms, view_models

class HomeView(generic.TemplateView):
    template_name = 'home.html'


class SearchForOpponentView(mixins.LoginRequiredMixin, generic.TemplateView):
    template_name = 'game/search_for_opponent.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        league = models.LeagueCategory.objects.get(name=self.kwargs.get('league_name'))
        try:
            result = models.ResultTable.objects.get(player=self.request.user, league=league)
        except models.ResultTable.DoesNotExist:
            return HttpResponseRedirect(reverse('game:create_result_table', kwargs={"league_name": league.name}))
        game = models.Game.objects.filter(league=league).filter(Q(player1=self.request.user)|Q(player2=self.request.user)).exclude(submitted_players=self.request.user).distinct()
        if game.exists():
            messages.warning(self.request, "結果を入力してください")
            return HttpResponseRedirect(reverse('game:room', kwargs={"league_name": game[0].league, "room_name": game[0].room}))
        context.update({'league': league, 'result': result})
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse('game:search_for_opponent'))

class CancelAjaxView(mixins.LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs):
        league_name = self.kwargs.get('league_name')
        self.league = models.LeagueCategory.objects.get(name=league_name)
        try:
            models.WaitingPlayer.objects.get(player=self.request.user, league=self.league).delete()
        except models.WaitingPlayer.DoesNotExist:
            pass
        return JsonResponse({'message': "対戦を中止しました"})


class SearchForOpponentAjaxView(mixins.LoginRequiredMixin, generic.View):
    matching_range = 10000 #! matchingの際の±dp範囲
    dp_diff = 40000 #! 期待勝率が10倍になるであろうdp差

    def post(self, request, *args, **kwargs):
        self.start_time = time.time()
        league_name = self.kwargs.get('league_name')
        self.league = models.LeagueCategory.objects.get(name=league_name)
        self.dp = models.ResultTable.objects.get(player=self.request.user, league=self.league).dp
        models.WaitingPlayer.objects.get_or_create(player=self.request.user, league=self.league, dp=self.dp)
        opponent = self.search_for_opponent(0)
        if opponent == 'matched':
            try:
                game = models.Game.objects.exclude(submitted_players=self.request.user).get(player2=self.request.user, league=self.league)
            except models.Game.DoesNotExist:
                return JsonResponse({"message": "対戦を中止しました"})
            messages.success(self.request, "対戦相手が決定しました!")
            return JsonResponse({"is_success": True, "roomname": game.room})
        elif opponent:
            with transaction.atomic():
                waiting1 = models.WaitingPlayer.objects.get(player=self.request.user, league=self.league)
                waiting2 = models.WaitingPlayer.objects.get(player=opponent, league=self.league)
                waiting1.delete()
                waiting2.delete()
                opponent_dp = models.ResultTable.objects.get(player=opponent, league=self.league).dp
                win_rate12 = 1 / (1 + math.pow(10, (opponent_dp - self.dp) / self.dp_diff))
                while True:
                    roomname = self.generate_room()
                    if not models.Game.objects.filter(room=roomname).exists():
                        break
                game = models.Game.objects.create(
                    room=roomname,
                    player1=self.request.user,
                    player2=opponent,
                    league=self.league,
                    win_rate12=win_rate12,
                    win_rate21=1 - win_rate12
                )
            messages.success(self.request, "対戦相手が決定しました!")
            return JsonResponse({"is_success": True, "roomname": game.room})
        else:
            return JsonResponse({"is_success": False, "roomname": None, 'message': '対戦相手が見つかりませんでした'})

    def search_for_opponent(self, count):
        if not models.WaitingPlayer.objects.filter(player=self.request.user, league=self.league).exists():
            return 'matched'
        if time.time() - self.start_time >= 30.0:
            models.WaitingPlayer.objects.filter(player=self.request.user, league=self.league).delete()
            return False
        lowwer_dp, upper_dp = self.dp - self.matching_range, self.dp + self.matching_range
        opponent_candidates = models.WaitingPlayer.objects.filter(league=self.league, dp__gte=lowwer_dp, dp__lte=upper_dp).exclude(player=self.request.user).distinct()
        if not opponent_candidates.exists():
            time.sleep(0.5)
            return self.search_for_opponent(count+1)
        ind = random.randint(0, opponent_candidates.count()-1)
        opponent = opponent_candidates[ind]
        return opponent.player

    def generate_room(self):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(10))


class RoomView(mixins.LoginRequiredMixin, generic.TemplateView):
    template_name = 'game/room.html'
    ero_rate_const = 2000

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room_name = self.kwargs.get('room_name')
        self.game = models.Game.objects.get(room=room_name)
        result = json.loads(self.game.result)['player1' if self.request.user == self.game.player1 else 'player2']
        chat_messages = models.ChatMessage.objects.filter(game=self.game).order_by('-timestamp')
        opponent = self.game.player2 if self.request.user == self.game.player1 else self.game.player1
        context.update({"game": self.game, 'chat_messages': chat_messages, 'result': result, 'opponent': opponent})
        return context

    def post(self, request, *args, **kwargs):
        self.game = models.Game.objects.get(room=self.kwargs.get('room_name'))
        self.league = self.game.league
        self.result_table = models.ResultTable.objects.get(player=self.request.user, league=self.league)
        result_num = self.request.POST.get('result')
        player = 'player1' if self.request.user == self.game.player1 else 'player2'
        if self.request.user in self.game.submitted_players.all():
            #*更新処理
            self.reset_dp(json.loads(self.game.result, player))
        else:
            #*新規作成
            self.game.submitted_players.add(self.request.user)
        self.update_dp(result_num, self.game.result, player)
        self.update_result(result_num, player)
        return HttpResponseRedirect(reverse("game:search_for_opponent", kwargs={"league_name": self.league}))

    def reset_dp(self, results, player):
        result = results[player]
        win_rate = 0.5
        if player == 'player1': win_rate = self.game.win_rate12
        else: win_rate = self.game.win_rate21
        if 'WIN' == result:
            self.result_table.dp += -self.ero_rate_const * (1 - win_rate)
            self.result_table.win += -1
        elif 'LOOSE' == result:
            self.result_table.dp += self.ero_rate_const * (-win_rate)
            self.result_table.loose += -1
        else:
            self.result_table.dp += self.ero_rate_const * (0.5 - win_rate)
        self.result_table.game_num += -1
        self.result_table.dp = max(0, self.result_table.dp)
        self.result_table.save()

    def update_dp(self, result_num, result, player):
        win_rate = 0.5
        if player == 'player1': win_rate = self.game.win_rate12
        else: win_rate = self.game.win_rate21
        if result_num == '0':
            self.result_table.dp += self.ero_rate_const * (1 - win_rate)
            self.result_table.win += 1
            messages.info(self.request, "dp +{:.1f}".format(self.ero_rate_const * (1 - win_rate)))
        elif result_num == '1':
            self.result_table.dp += self.ero_rate_const * (-win_rate)
            self.result_table.loose += 1
            messages.info(self.request, "dp {:.1f}".format(self.ero_rate_const * (-win_rate)))
        else:
            self.result_table.dp += self.ero_rate_const * (0.5 - win_rate)
            if 0.5 > win_rate:
                messages.info(self.request, "dp +{:.1f}".format(self.ero_rate_const * (0.5 - win_rate)))
            elif 0.5 < win_rate:
                messages.info(self.request, "dp {:.1f}".format(self.ero_rate_const * (0.5 - win_rate)))
            else:
                messages.info(self.request, "dp {:.1f}".format(self.ero_rate_const * (0.5 - win_rate)))
        self.result_table.dp = max(0, self.result_table.dp)
        self.result_table.game_num += 1
        self.result_table.save()

    def update_result(self, result_num, player):
        result = json.loads(self.game.result)
        RESULT_CHAR = {'0': 'WIN', '1': 'LOOSE', '2': 'DRAW'}
        result[player] = RESULT_CHAR[result_num]
        self.game.result = json.dumps(result)
        self.game.save()


class CreateResultTableView(mixins.LoginRequiredMixin, generic.CreateView):
    model = models.ResultTable
    template_name = 'game/create_result_table.html'
    form_class = forms.CreateResultTableForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        league_name = self.kwargs.get('league_name')
        league = models.LeagueCategory.objects.get(name=league_name)
        context.update({'league': league})
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.player = self.request.user
        league_name = self.kwargs.get('league_name')
        self.league = models.LeagueCategory.objects.get(name=league_name)
        with transaction.atomic():
            self.object.league.players.add(self.request.user)
            self.league.participants += 1
            self.league.save()
            self.object.save()
            messages.success(self.request, "{}に参加登録しました。".format(self.object.league))
        return HttpResponseRedirect(self.get_success_url())

class LeagueListView(mixins.LoginRequiredMixin, generic.ListView):
    template_name = 'game/league_list.html'
    model = models.LeagueCategory

class LeagueFilterViewAjax(generic.View):
    def get(self, request, *args, **kwargs):
        paginated_by = 10
        filter_value = int(request.GET.get('filter_type'))
        order = request.GET.get('order')
        ordering = request.GET.get('ordering')
        search_key = request.GET.get('search_key')
        current_page = int(request.GET.get('current_page', 1))
        last_page = request.GET.get('last', False)
        searched = models.LeagueCategory.objects.all()
        if filter_value == 2:
            searched = models.LeagueCategory.objects.filter(players=self.request.user)
        elif filter_value == 3:
            searched = models.LeagueCategory.objects.filter(start_at__lte=timezone.now(), finish_at__gte=timezone.now())
        elif filter_value == 4:
            searched = models.LeagueCategory.objects.filter(finish_at__lte=timezone.now())
        if search_key != '':
            searched = searched.filter(name__icontains=search_key)
        if ordering == 'lower':
            if order == 'created_at': searched = searched.order_by('-created_at')
            else: searched = searched.order_by('-participants')
        else:
            if order == 'created_at': searched = searched.order_by('created_at')
            else: searched = searched.order_by('participants')
        leagues = []
        for obj in searched:
            leagues.append(view_models.LeagueCategoryMapper(obj).as_dict())
        max_page = math.ceil(len(leagues) / paginated_by)
        if last_page: current_page = max_page
        start = paginated_by * (current_page - 1)
        end = paginated_by * current_page
        res = {
            'leagues': leagues[start:end],
            'max_page': max_page,
            'current_page': current_page,
            'filter_type': filter_value,
            'order': order,
            'ordering': ordering,
            'search_key': search_key,
        }
        return JsonResponse(res, safe=False)



class CreateLeagueView(mixins.LoginRequiredMixin, generic.CreateView):
    model = models.LeagueCategory
    fields = ['name', 'start_at', 'finish_at', 'details']
    template_name = 'game/create_league.html'

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.host = self.request.user
        self.object.save()
        messages.success(self.request, '{}を登録しました。'.format(self.object.name))
        return HttpResponseRedirect(reverse('game:league_list'))

    def form_invalid(self, form):
        messages.warning(self.request, '失敗しました')
        return self.render_to_response(self.get_context_data(form=form))


class RankingView(generic.ListView):
    model = models.ResultTable
    template_name = 'game/ranking.html'
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        league = models.LeagueCategory.objects.get(name=self.kwargs.get('league_name'))
        self.objcet_list = models.ResultTable.objects.filter(league=league).order_by('-dp')
        rank = 0
        previous_dp = -1
        for user in self.objcet_list:
            if not previous_dp == user.dp:
                rank += 1
            user.rank = rank
            previous_dp = user.dp
            user.save()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_key = self.request.GET.get('search_key') or ''
        searched = self.objcet_list.all()
        current_page = int(self.request.GET.get('page') or 1)
        if search_key != '':
            searched = searched.filter(player__username__icontains=search_key).order_by('rank')
        max_page = max(math.ceil(searched.count() / self.paginate_by), 1)
        start = self.paginate_by * (current_page - 1)
        end = self.paginate_by * current_page
        page_nums = []
        if max_page <= 5:
            for i in range(1, max_page+1):
                page_nums.append(i)
        else:
            for i in range(max(0, current_page - 2), min(max_page, current_page + 2)):
                page_nums.append(i)
        context.update({
            "object_list": searched[start:end],
            "current_page": current_page,
            'max_page': max_page,
            'page_nums': page_nums,
            'search_key': search_key
        })
        print(context)
        return context


class ResultListView(generic.TemplateView):
    template_name = 'game/result_list.html'

class CheckLeagueNameAjax(mixins.LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        league_name = request.GET.get('league_name')
        if len(league_name) == 0:
            return JsonResponse({"help_text": "リーグ名を入力してください", "is_ok": False})
        if models.LeagueCategory.objects.filter(name=league_name).exists():
            return JsonResponse({"help_text":"そのリーグ名は既に使われています", "is_ok": False})
        return JsonResponse({"help_text": "使用可能です", "is_ok": True})



class GetGameAjaxView(generic.View):
    def get(self, request, *args, **kwargs):
        paginated_by = 8
        search_key = request.GET.get('search_key', '')
        current_page = int(request.GET.get('current_page', 1))
        last_page = request.GET.get('last')
        games = []
        searched = models.Game.objects.all().order_by('-start_at')
        if search_key != '':
            searched = searched.filter(
                Q(player1__username__icontains=search_key)|
                Q(player2__username__icontains=search_key)|
                Q(league__name__icontains=search_key)
            ).distinct()
        for obj in searched:
            games.append(view_models.GameMapper(obj).as_dict())
        max_page = math.ceil(len(games) / paginated_by)
        if last_page: current_page = max_page
        start = paginated_by * (current_page - 1)
        end = paginated_by * current_page
        res = {
            'games': games[start:end],
            'max_page': max_page,
            'current_page': current_page
        }
        return JsonResponse(res, safe=False)

