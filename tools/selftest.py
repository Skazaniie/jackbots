"""Offline check of the game logic without network: fake model + fake room states.
Run: python tools/selftest.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import games, store  # noqa: E402


class FakeLLM:
    def __init__(self):
        self.answers = []
        self.prompts = []

    async def chat(self, p, model, messages, temperature, max_tokens, one_line=True, extra_body=None):
        u = messages[-1]["content"]
        self.prompts.append(u)
        if "числом от 0 до 100" in u:
            t = "37"
        elif "номерами" in u:
            t = "2, 1"
        elif "номером" in u:
            t = "2"
        elif "слово" in u:
            t = "Без нужного слова"
        else:
            t = "«Мама уже выбрала имена нашим детям»\nПояснение..."
        self.answers.append((str(u)[:60].replace("\n", " "), t))
        return {"text": t.split("\n")[0].strip("«»"), "ms": 5, "ttft": 3, "tokens": 3}


class FakeSession:
    code, host, traffic = "TEST", "localhost", None

    def __init__(self):
        self.llm = FakeLLM()
        self.events = []

    def emit(self, kind, **d):
        self.events.append((kind, d))


async def run(cls, steps, game_language="auto", **cfg):
    s = FakeSession()
    s.game_language = game_language
    # a fixed bot, not the first one from config/: the test must not depend on personal settings
    bot = cls(s, {**store.DEFAULT_BOTS[0], "enabled": True, "games": {}, "vision": False, **cfg})
    sent = []

    async def send(body):
        sent.append(body)
        return True
    bot.client.send = send
    bot.client.update_text = lambda k, v: send({"text/update": k, "val": v})
    bot.client.update_object = lambda k, v: send({"object/update": k, "val": v})
    bot.client.pid = 7
    for key, val in steps:
        await bot.on_entity(key, val)
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.2)
    errs = [d for k, d in s.events if k == "error"]
    return sent, errs, bot


async def main():
    me = "bc:customer:7"
    q2 = [
        ("bc:room", {"state": "Gameplay_AnswerQuestion", "round": 1}),
        (me, {"state": "Gameplay_AnswerQuestion", "question": {"id": 11, "prompt": "Худшее <BLANK> на свидании"}}),
        (me, {"state": "Gameplay_AnswerQuestion", "question": {"id": 11, "prompt": "Худшее <BLANK> на свидании"}}),
        (me, {"state": "Gameplay_Vote", "doneVoting": False}),
        ("bc:room", {"state": "Gameplay_Vote", "question": {"prompt": "Что сказать тёще"},
                     "choices": {"0": "Вы великолепны", "1": "Можно домой?"}, "order": [0, 1]}),
        ("bc:room", {"state": "Gameplay_Vote", "question": {"prompt": "Что сказать тёще"},
                     "choices": {"0": "Вы великолепны", "1": "Можно домой?"}, "order": [0, 1]}),
        ("bc:room", {"state": "Gameplay_Vote", "question": {"prompt": "Свои"},
                     "choices": {"0": "Мама уже выбрала имена нашим детям", "1": "Чужой"}, "order": [0, 1]}),
        (me, {"state": "Gameplay_AnswerQuestion", "question": {"id": 30, "type": "WordLash", "prompt": "КАРТОШКА", "quip": "Название сериала со словом"}}),
        ("bc:room", {"state": "Gameplay_R3Vote", "question": {"id": 30, "prompt": "КАРТОШКА"}}),
        (me, {"state": "Gameplay_R3Vote", "playerIndex": 0, "votesLeft": 3, "currentVote": 0,
              "votes": [{"answer": "A", "playerIndex": 1}, {"answer": "B", "playerIndex": 2}, {"answer": "C", "playerIndex": 0}]}),
        (me, {"state": "Gameplay_R3Vote", "playerIndex": 0, "votesLeft": 2, "currentVote": 1,
              "votes": [{"answer": "A", "playerIndex": 1}, {"answer": "B", "playerIndex": 2}, {"answer": "C", "playerIndex": 0}]}),
    ]
    sent, errs, bot = await run(games.Quiplash2, q2)
    print("Q2 sent:", sent)
    print("Q2 errors:", errs)
    print("Q2 memory:", bot.memory)
    exp = [{"answer": "Мама уже выбрала имена нашим детям", "questionId": 11}, {"vote": 1}]
    assert sent[:2] == exp, sent[:2]
    assert sum(1 for x in sent if "vote" in x) == 3, "один голос в паре + 2 медали"
    assert any("КАРТОШКА" in x.get("answer", "") for x in sent), "wordlash со словом"
    assert sent[-2:] == [{"vote": 2}, {"vote": 1}], sent[-2:]

    pp = [
        ("bc:room", {"state": "Lobby", "characters": [{"id": "a", "name": "x", "isSelected": 1}, {"id": "b", "name": "y"}]}),
        (me, {"state": "Lobby_ChooseCharacter"}),
        ("bc:room", {"state": "Gameplay_PickCategory"}),
        (me, {"state": "Gameplay_PickCategory", "choices": [{"id": 4, "text": "Еда"}, {"id": 9, "text": "Секс"}]}),
        ("bc:room", {"state": "Gameplay_EnterPercentage", "question": "Сколько % людей храпят?", "survey": "Сон"}),
        (me, {"state": "Gameplay_EnterPercentage"}),
        # real format from the game: the number is inside question, the question is in survey, id is capitalized
        ("bc:room", {"state": "Gameplay_ChooseUpOrDown", "question": "Батя ответил 42% ", "survey": "Сколько % людей храпят?",
                     "choices": [{"id": "Higher", "text": "Больше"}, {"id": "Lower", "text": "Меньше"}]}),
        (me, {"state": "Gameplay_ChooseUpOrDown"}),
        ("bc:room", {"state": "Gameplay_ChooseMultiple", "question": "Любимый суп"}),
        (me, {"state": "Gameplay_ChooseMultiple", "selection": "Выбери 3", "choices": [{"text": "Борщ"}, {"text": "Щи"}, {"text": "Уха"}]}),
        (me, {"state": "Gameplay_ChooseMultiple", "selection": "Выбери 3", "choices": [{"text": "Борщ"}, {"text": "Щи", "picked": True}, {"text": "Уха"}]}),
    ]
    import random
    random.seed(1)
    orig = asyncio.sleep
    sent, errs, bot = await run(games.PollPosition, pp)
    await orig(1.3)
    print("PP sent:", sent)
    print("PP errors:", errs)
    for want in ({"category": 9}, {"percentageUpdate": 37}, {"percentageEntered": 37}, {"choice": "Lower"}, {"choice": 1}, {"choice": 2}):
        assert want in sent, want
    assert not errs and True
    ud = next(p for p in bot.s.llm.prompts if "Другой игрок" in p)
    for want in ("Опрос: Сон", "«Сколько % людей храпят?»", "поставил 42%", "Больше", "Меньше"):
        assert want in ud, (want, ud)
    assert sum(1 for x in sent if "percentageEntered" in x) == 1, "процент отправлен один раз"
    await check_tmp2(me)
    await check_sti(me)
    from app.llm import LLM, _clean
    assert _clean("<mm:think>думаю\nещё</mm:think>\n«Ответ»", True) == "Ответ"
    assert _clean("<think>x</think>Да", True) == "Да"
    assert _clean("<mm:think>ещё думает", True) == ""
    b = LLM()._body({"base_url": "x", "extra_body": {"a": 1}}, "m", [], 0.9, 60, True, {"reasoning_effort": "none"})
    assert b["a"] == 1 and b["reasoning_effort"] == "none", b
    await check_english()
    await check_reconnect_limit()
    check_twitch()
    print("OK — все проверки пройдены")


async def check_tmp2(me):
    """Trivia Murder Party 2: fake blobs in the pp6-triviadeath2 format."""
    games.TriviaDeath2.SPEED = 0
    assert games.solve_math("7 − 12") == -5 and games.solve_math("3 × 4") == 12 and games.solve_math("привет") is None
    planet = {"state": "MakeSingleChoice", "prompt": {"html": "Самая большая планета?"},
              "choices": [{"text": "Сатурн"}, {"text": "Юпитер"}, {"text": "Марс"}]}
    tm = [
        ("bc:room", {"state": "Logo", "audience": {"state": "MakeSingleChoice"}}),
        (me, {"state": "Lobby", "playerCanStartGame": True, "gameCanStart": True,
              "characters": [{"name": "doll1", "available": True}, {"name": "doll2", "available": False}]}),
        (me, planet),
        (me, {**planet, "choices": [{"text": "Сатурн"}, {"text": "Юпитер", "disabled": True}, {"text": "Марс"}]}),
        (me, {**planet, "chosen": 1}),
        (me, {"state": "MakeSingleChoice", "choiceType": "Math", "prompt": {"html": "7 - 12"},
              "choices": [{"text": "-5"}, {"text": "5"}, {"text": "19"}]}),
        (me, {"state": "MakeSingleChoice", "type": "multiple", "roundType": "FinalRound", "prompt": {"html": "Фрукты"},
              "choices": [{"text": "Яблоко", "key": 10}, {"text": "Гвоздь", "key": 11}, {"text": "Груша", "key": 12}]}),
        (me, {"state": "EnterSingleText", "prompt": {"html": "Придумай пароль"}, "maxLength": 20, "textKey": "pw:7"}),
        (me, {"state": "EnterSingleText", "prompt": {"html": "Шутка про отель"}, "maxLength": 45}),
        (me, {"state": "Grid", "grid": [[{"type": "Hide", "text": "A"}, {"type": "Taken", "text": "B"}]]}),
        (me, {"state": "Scratch", "choices": [{} for _ in range(9)]}),
        (me, {"state": "Dial", "choices": [{"text": "666-1234"}], "status": "connected"}),
        ("player", {"state": "Drop"}),
        (me, {"state": "Draw", "prompt": {"html": "Нарисуй тату"}, "objectKey": "draw:7"}),
        (me, {"state": "Logo"}),
        # real formats from a game log: finale with toggles, mind meld, donations, mirror
        (me, {"state": "MakeSingleChoice", "roundType": "FinalRound", "prompt": {"html": "<div>Десятибуквенные слова</div>"},
              "choices": [{"className": "unselected", "html": "вафельница"}, {"className": "unselected", "html": "кот"},
                          {"className": "unselected", "html": "водопровод"}, {"className": "submit", "html": "ОТПРАВИТЬ"}]}),
        (me, {"state": "MakeSingleChoice", "roundType": "FinalRound", "prompt": {"html": "<div>Фрукты</div>"},
              "choices": [{"className": "unselected", "html": "Яблоко"}, {"className": "selected", "html": "Гвоздь"},
                          {"className": "unselected", "html": "Груша"}, {"className": "submit", "html": "ОТПРАВИТЬ"}]}),
        (me, {"state": "EnterSingleText", "entryId": "MindMeld0", "entry": False, "maxLength": 128, "prompt": {"html": "знак зодиака"}}),
        (me, {"state": "EnterSingleText", "entryId": "MindMeld1", "entry": True, "maxLength": 128, "prompt": {"html": "знак зодиака"}}),
        (me, {"state": "EnterSingleText", "entryId": "DonationAmount", "entry": False, "inputType": "number",
              "placeholder": "(0-500)", "prompt": {"html": "Сколько денег ты хочешь отдать? (0-500)."}}),
        (me, {"state": "EnterSingleText", "entryId": "DonationAmount", "entry": False, "inputType": "number", "error": "Некорректный ввод!",
              "placeholder": "(0-500)", "prompt": {"html": "Сколько денег ты хочешь отдать? (0-500)."}}),
        (me, {"state": "Draw", "roundType": "Mirror", "live": True, "hideSubmit": True, "colors": ["#000000"],
              "size": {"width": 360, "height": 140}, "prompt": {"html": "Напиши слово на зеркале"}}),
        (me, {"state": "Logo"}),
    ]
    sent, errs, bot = await run(games.TriviaDeath2, tm)
    print("TMP2 sent:", [x for x in sent if not ("object/update" in x)])
    print("TMP2 errors:", errs)
    assert not errs, errs
    assert {"action": "avatar", "name": "doll1"} in sent
    assert sent.count({"action": "choose", "choice": 1}) == 1, "один ответ на вопрос, даже если варианты обновились"
    assert {"action": "choose", "choice": 0} in sent, "математика посчитана сама"
    assert not any("Вопрос: «7 - 12»" in p for p in bot.s.llm.prompts), "математику не спрашиваем у модели"
    assert {"action": "submit", "choice": "10,11"} in sent
    assert {"text/update": "pw:7", "val": "Без нужного слова"} in sent
    assert sent.count({"action": "write", "entry": "Мама уже выбрала имена нашим детям"}) == 2, "отель + один ответ в слиянии разумов"
    def seq_in(want):
        it = iter(sent)
        return all(any(x == w for x in it) for w in want)
    assert seq_in([{"action": "choose", "choice": 0}, {"action": "choose", "choice": 2}, {"action": "choose", "choice": 3}]), "10 букв посчитаны кодом"
    assert seq_in([{"action": "choose", "choice": 3}, {"action": "choose", "choice": 0}, {"action": "choose", "choice": 3}]), "финал: переключатели + отправить"
    nums = [x["entry"] for x in sent if x.get("action") == "write" and str(x.get("entry")).isdigit()]
    assert len(nums) == 2 and all(0 <= int(n) <= 500 for n in nums), nums
    assert sum(1 for x in sent if x.get("action") == "line") > 20, "слово на зеркале штрихами"
    assert games.letter_rule("Десятибуквенные слова") == 10 and games.letter_rule("Слова из 7 букв") == 7
    assert games.letter_rule("Перцы") is None
    from app.llm import LLMError

    class Refuse:
        async def chat(self, *a, **k):
            return {"text": "I appreciate the creative setup, but I'm Claude", "ms": 1}
    bot.s.llm = Refuse()
    try:
        await bot.ask("text", {"вопрос": "x", "лимит": 10, "подсказка": ""})
        raise AssertionError("отказ модели не распознан")
    except LLMError:
        pass
    assert {"action": "click", "position": "0-0"} in sent
    assert sum(1 for x in sent if x.get("action") == "scratch") == 3
    assert [x["num"] for x in sent if x.get("action") == "dial"] == [6, 6, 6, 1, 2, 3, 4]
    assert any(x.get("action") == "drop" for x in sent)
    d = next(x for x in sent if "object/update" in x)
    assert d["object/update"] == "draw:7" and d["val"]["submit"] and d["val"]["lines"], d
    bot.me = {"state": "Lobby", "playerCanStartGame": True, "gameCanStart": True}
    assert bot.can_start and bot.start_body == {"action": "start"}
    bot.me["gameFinished"] = True
    assert bot.start_body == {"action": "PostGame_Continue"}
    print("TMP2: ok")


async def check_sti(me):
    """Survive the Internet: blobs in the pp4 format (bc:customer, text with a black bar, finale photo)."""
    games.TriviaDeath2.SPEED = 0
    img = "<img src='images/survivetheinternet/photos/Funeral.jpg'/>"
    st = [
        (me, {"state": "Lobby", "isAllowedToStartGame": True, "lobbyState": "CanStart"}),
        (me, {"state": "EnterSingleText", "entryId": "response", "entry": False, "maxLength": 80,
              "text": {"aboveBlackBox": "", "blackBox": "", "belowBlackBox": "Как ты проводишь выходные?"}}),
        (me, {"state": "EnterSingleText", "entryId": "response", "entry": True, "maxLength": 80,
              "text": {"belowBlackBox": "Как ты проводишь выходные?"}}),
        (me, {"state": "EnterSingleText", "entryId": "twist", "entry": False, "maxLength": 60,
              "text": {"blackBox": "Сплю до обеда", "belowBlackBox": "would be a terrible comment on this headline:"}}),
        (me, {"state": "Voting", "chosen": None, "text": {"blackBox": "Что смешнее?"},
              "choices": [{"header": "Новости", "body": "Пожар в школе", "footer": "Сплю до обеда"},
                          {"header": "Видео", "body": "Свадьба", "footer": "Наконец-то свободен",
                           "thumbnail": "images/survivetheinternet/photos/Wedding-thumb.jpg"}]}),
        (me, {"state": "Voting", "chosen": 1, "choices": []}),
        (me, {"state": "EnterSingleText", "entryId": "final", "entry": False, "maxLength": 70,
              "text": {"aboveBlackBox": img, "belowBlackBox": "Write an Instagram caption"}}),
        (me, {"state": "MakeSingleChoice", "chosen": None, "text": {"blackBox": "Pick one"},
              "choices": [{"id": "a", "text": "Один"}, {"id": "b", "text": "Два"}, {"id": "c", "text": "Три", "disabled": True}]}),
        (me, {"state": "Logo"}),
    ]
    sent, errs, bot = await run(games.SurviveTheInternet, st)
    print("STI sent:", sent)
    assert not errs, errs
    writes = [x for x in sent if x.get("action") == "write"]
    assert len(writes) == 3, writes
    assert sent.count({"action": "choose", "choice": 1}) == 2, "голос за пост 2 и выбор варианта 2"
    pr = bot.s.llm.prompts
    assert any("Сплю до обеда" in p and "нелепо" in p for p in pr), "подстава видит чужой ответ"
    assert any("casket" in p.lower() for p in pr if isinstance(p, str)), "финал: описание фото из каталога"
    assert any("wedding" in p.lower() for p in pr if isinstance(p, str)), "голосование: описание миниатюры"
    bot.me = {"state": "Lobby", "isAllowedToStartGame": True, "lobbyState": "CanStart"}
    assert bot.can_start and bot.start_body == {"action": "start"}
    bot.me = {"state": "Lobby", "isAllowedToStartGame": True, "lobbyState": "WaitingForMore"}
    assert not bot.can_start
    bot.me = {"state": "Lobby", "isAllowedToStartGame": True, "lobbyState": "PostGame"}
    assert bot.start_body == {"action": "PostGame_Continue"}
    assert len(games.sti_photos()) > 100 and games.sti_photos()["Funeral"]["url"].startswith("https://")

    async def fake_img(url):
        return "data:image/jpeg;base64,AAAA"
    real, games.photo_data_url = games.photo_data_url, fake_img
    try:
        bot.cfg = {**bot.cfg, "vision": True}
        bot.s.llm.prompts.clear()
        await bot.write({"state": "EnterSingleText", "maxLength": 70, "text": {"aboveBlackBox": img, "belowBlackBox": "caption"}})
        assert any(isinstance(p, list) and p[1]["type"] == "image_url" for p in bot.s.llm.prompts), "vision: картинка ушла модели"
    finally:
        games.photo_data_url = real
    print("STI: ok")


async def check_english():
    """English version (jackbox.tv): Latin-only answers, Latin nickname, English prompts."""
    from app import lang
    assert lang.detect("The worst thing to say") == "en" and lang.detect("Худшее, что можно") == "ru"
    assert lang.latin_safe("Привет, «мир» 😀 — ok") == 'Privet, "mir" - ok'
    assert lang.latin_name("Шутник") == "SHUTNIK" and lang.latin_name("😀😀") == "BOT"
    assert games.render("{question}|{вопрос}|{nope}", {"вопрос": "x"}) == "x|x|{nope}"
    me = "bc:customer:7"
    steps = [(me, {"state": "Gameplay_AnswerQuestion", "question": {"id": 5, "prompt": "The worst thing to say <BLANK> on a date"}})]
    sent, errs, bot = await run(games.Quiplash2, steps)  # auto: language by the question text
    assert not errs, errs
    assert bot.lang == "en", bot.lang
    assert sent == [{"answer": "Mama uzhe vybrala imena nashim detyam", "questionId": 5}], sent
    assert "The worst thing to say ___ on a date" in bot.s.llm.prompts[0], bot.s.llm.prompts[0]
    assert not any("Вопрос:" in p for p in bot.s.llm.prompts), "английская игра — английский промт"
    _, _, bot = await run(games.Quiplash2, [], game_language="en", name="Шутник")
    assert bot.client.name == "SHUTNIK" and bot.name == "Шутник", bot.client.name
    _, _, bot = await run(games.Quiplash2, [], game_language="ru", name="Шутник")
    assert bot.client.name == "Шутник" and bot.lang == "ru"
    print("EN: ok", sent)


async def check_reconnect_limit():
    """The server accepts the connection and immediately sends an error (as for a full room); the bot must give up."""
    import json as _json
    from app import jackbox
    attempts, statuses = [], []

    class FakeWS:
        def __init__(self, msgs):
            self.msgs = msgs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            for m in self.msgs:
                yield m

    def fake_connect(*a, **k):
        attempts.append(1)
        return FakeWS([_json.dumps({"opcode": "error", "result": {"code": 2003, "msg": "room is full"}})])

    async def on_status(s, d):
        statuses.append(s)

    async def on_entity(k, v):
        pass

    orig_connect, orig_sleep = jackbox.connect, jackbox.asyncio.sleep
    jackbox.connect = fake_connect
    jackbox.asyncio.sleep = lambda *_: orig_sleep(0)
    try:
        c = jackbox.EcastClient("TEST", "bot", "localhost", on_entity, on_status)
        await asyncio.wait_for(c.run(), timeout=5)
    finally:
        jackbox.connect, jackbox.asyncio.sleep = orig_connect, orig_sleep
    assert len(attempts) <= 6, f"бесконечные попытки: {len(attempts)}"
    assert statuses[-1] == "gone", statuses
    print("reconnect limit:", len(attempts), "попыток, статус", statuses[-1])



def check_twitch():
    """Twitch token: parsed from a pasted URL and sent as twitch-token only when set."""
    from urllib.parse import parse_qs, urlsplit
    from app import jackbox
    tok = "abcdefghij0123456789klmnopqrst"
    assert jackbox.twitch_token(f"https://jackbox.tv/#access_token={tok}&scope=user%3Aread%3Aemail&token_type=bearer") == tok
    assert jackbox.twitch_token(f" oauth:{tok} ") == tok and jackbox.twitch_token("not a token") == ""

    async def nop(*a):
        pass
    with_tok = jackbox.EcastClient("TEST", "bot", "h", nop, nop, twitch_token=tok)._url()
    assert parse_qs(urlsplit(with_tok).query)["twitch-token"] == [tok], with_tok
    assert "twitch-token" not in jackbox.EcastClient("TEST", "bot", "h", nop, nop)._url()
    print("twitch token: ok")

asyncio.run(main())
