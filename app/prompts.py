"""Промты по умолчанию для двух версий игры: русской (jackbox.fun) и английской (jackbox.tv).

Переменные в фигурных скобках подставляет app/games.py. Внутри кода значения лежат под русскими ключами
({вопрос}, {история}…); английские промты пишутся с английскими именами ({question}, {history}…) —
соответствие задаёт VAR_ALIASES. В любом промте работают оба варианта.
"""

LANGS = {"ru": "Русский", "en": "English"}

# английское имя переменной → внутренний ключ
VAR_ALIASES = {
    "game": "игра", "name": "имя", "persona": "персонаж", "question": "вопрос", "history": "история",
    "options": "варианты", "word": "слово", "round": "раунд", "number": "число", "survey": "опрос",
    "instruction": "инструкция", "hint": "подсказка", "limit": "лимит", "range": "диапазон",
    "answer": "ответ", "photo": "фото", "vision": "зрение",
}

# ======================================================================= русская версия
SYSTEM_RU = (
    "Ты играешь в игру Jackbox «{игра}» под именем {имя}. Твой характер: {персонаж}. "
    "Играешь против других игроков, отвечаешь как обычный игрок и не объясняешь ответы. "
    "Пиши по-русски, коротко и своим голосом."
)

PROMPTS_RU = {
    "system": SYSTEM_RU,
    "quiplash2": {
        "answer": {
            "title": "Шутка", "hint": "Ответ на вопрос раунда", "format": "text", "max_tokens": 60,
            "text": "Вопрос: {вопрос}\n\nТвои прошлые ответы в этой игре (не повторяйся):\n{история}\n\n"
                    "Придумай ОДИН смешной, неожиданный ответ до 45 символов. "
                    "Напиши только сам ответ, без кавычек и пояснений.",
        },
        "vote": {
            "title": "Голосование", "hint": "Выбрать смешной ответ из двух", "format": "choice", "max_tokens": 8,
            "text": "Вопрос: {вопрос}\n\nОтветы игроков:\n{варианты}\n\nКакой ответ смешнее? Ответь ТОЛЬКО номером.",
        },
        "wordlash": {
            "title": "Финал: слово", "hint": "Ответ с обязательным словом", "format": "text", "max_tokens": 60,
            "text": "Задание: {вопрос}\nОбязательно используй слово «{слово}».\n"
                    "Придумай смешной ответ до 45 символов. Только сам ответ.",
        },
        "acrolash": {
            "title": "Финал: аббревиатура", "hint": "Смешная расшифровка", "format": "text", "max_tokens": 40,
            "text": "Смешно расшифруй аббревиатуру {вопрос}: по одному слову на каждую букву, по порядку. "
                    "Напиши только расшифровку.",
        },
        "comiclash": {
            "title": "Финал: комикс", "hint": "Последняя реплика комикса", "format": "text", "max_tokens": 60,
            "text": "Комикс: {вопрос}\nПридумай смешную последнюю реплику до 45 символов. Только реплику.",
        },
        "r3vote": {
            "title": "Финал: медали", "hint": "Раздать золото, серебро, бронзу", "format": "ranking", "max_tokens": 20,
            "text": "Финальное задание: {вопрос}\n\nОтветы игроков:\n{варианты}\n\n"
                    "Расставь ответы от самого смешного к менее смешному. Ответь ТОЛЬКО номерами через запятую.",
        },
    },
    "pollposition": {
        "guess": {
            "title": "Угадать процент", "hint": "Твой ход: ставишь число 0–100", "format": "number", "max_tokens": 10,
            "text": "Вопрос опроса: «{вопрос}»\nКакой процент людей ответил «да»?\n\n"
                    "Твои прошлые оценки и реальные ответы:\n{история}\n\nОтветь ТОЛЬКО числом от 0 до 100.",
        },
        "updown": {
            "title": "Больше или меньше", "hint": "Споришь с числом другого игрока", "format": "choice", "max_tokens": 8,
            "text": "Опрос: {опрос}\nВопрос: «{вопрос}»\nДругой игрок поставил {число}.\n\n"
                    "Твои прошлые оценки и реальные ответы:\n{история}\n\nРеальный процент:\n{варианты}\n\nОтветь ТОЛЬКО номером.",
        },
        "multiple": {
            "title": "Финал: топ-3", "hint": "Выбрать самые популярные варианты", "format": "choice", "max_tokens": 8,
            "text": "Вопрос: «{вопрос}»\n{инструкция}\n\nВарианты:\n{варианты}\n\n"
                    "Какой вариант выбрало больше всего людей? Ответь ТОЛЬКО номером.",
        },
        "category": {
            "title": "Выбор темы", "hint": "Когда бот выбирает категорию", "format": "choice", "max_tokens": 8,
            "text": "Выбери тему опроса, которая тебе ближе:\n{варианты}\n\nОтветь ТОЛЬКО номером.",
        },
    },
    "triviadeath2": {
        "choice": {
            "title": "Вопрос / выбор", "hint": "Викторина, «Правила», выбор в мини-играх", "format": "choice", "max_tokens": 8,
            "text": "Ситуация: {подсказка}\nВопрос: «{вопрос}»\n\nВарианты:\n{варианты}\n\nТвои прошлые ходы:\n{история}\n\n"
                    "На кону жизнь, тут не до шуток: если есть правильный ответ — выбери его. Ответь ТОЛЬКО номером.",
        },
        "multiple": {
            "title": "Финал: несколько ответов", "hint": "Отметить все подходящие варианты", "format": "choice", "max_tokens": 16,
            "text": "Ситуация: {подсказка}\nЗадание: «{вопрос}»\n\nВарианты:\n{варианты}\n\n"
                    "Подходить может один, несколько или все варианты. "
                    "Ответь ТОЛЬКО номерами всех подходящих через запятую, без рассуждений.",
        },
        "text": {
            "title": "Ввод текста", "hint": "Смехлыст, пароль, «Слияние разумов» и т.п.", "format": "text", "max_tokens": 40,
            "text": "Задание на телефоне: «{вопрос}»\nЛимит: {лимит} символов.\n{подсказка}\n\n"
                    "Твои прошлые ходы:\n{история}\n\nПиши на языке задания. Напиши только сам ответ, без кавычек и пояснений.",
        },
        "number": {
            "title": "Число (деньги)", "hint": "Пожертвования, «Жадность»: игра принимает только число", "format": "number",
            "max_tokens": 10,
            "text": "Задание на телефоне: «{вопрос}»\nДопустимо: {диапазон}.\n{подсказка}\n\n"
                    "Твои прошлые ходы:\n{история}\n\nОтветь ТОЛЬКО одним целым числом.",
        },
    },
    "survivetheinternet": {
        "response": {
            "title": "Ответ о себе", "hint": "Первый шаг: честный ответ на личный вопрос", "format": "text", "max_tokens": 50,
            "text": "Вопрос о тебе: «{вопрос}»\nЛимит: {лимит} символов.\n\nОтветь коротко (до 10 слов), как обычный "
                    "человек о себе, своим характером. Другой игрок потом вырвет твои слова из контекста.\n"
                    "Твои прошлые ответы (не повторяйся):\n{история}\n\nПиши на языке вопроса. Только сам ответ.",
        },
        "twist": {
            "title": "Подстава", "hint": "Чужой ответ вырвать из контекста", "format": "text", "max_tokens": 60,
            "text": "Ответ другого игрока: «{ответ}»\nЗадание: {вопрос}\nЛимит: {лимит} символов.\n\n"
                    "Придумай заголовок, пост или ситуацию, где этот ответ выглядит максимально нелепо, стыдно или "
                    "безумно. Смешно и неожиданно. Пиши на языке задания. Только сам текст.",
        },
        "photo": {
            "title": "Финал: фото", "hint": "Подпись к фотографии в соцсети", "format": "text", "max_tokens": 60,
            "text": "Финальный раунд, фото из соцсети. {зрение}\nНа фото: {фото}\nЗадание: {вопрос}\nЛимит: {лимит} символов.\n\n"
                    "Напиши абсурдную подпись к этому фото, чтобы её автор выглядел странным, жутким или безумным. "
                    "Шутка должна опираться на то, что на фото. Пиши на языке задания. Только подпись.",
        },
        "vote": {
            "title": "Голосование", "hint": "Выбрать самый нелепый пост", "format": "choice", "max_tokens": 8,
            "text": "Задание: {вопрос}\n\nПосты:\n{варианты}\n\nКакой пост самый смешной и нелепый? Ответь ТОЛЬКО номером.",
        },
        "choice": {
            "title": "Выбор", "hint": "Выбор из вариантов на экране", "format": "choice", "max_tokens": 8,
            "text": "Задание: {вопрос}\n{зрение}\nФото: {фото}\n\nВарианты:\n{варианты}\n\n"
                    "Выбери вариант, с которым будет смешнее. Ответь ТОЛЬКО номером.",
        },
    },
}

VARS_RU = {
    "system": ["игра", "имя", "персонаж"],
    "quiplash2": ["вопрос", "история", "варианты", "слово", "раунд", "имя", "персонаж"],
    "pollposition": ["вопрос", "история", "варианты", "число", "опрос", "инструкция", "имя", "персонаж"],
    "triviadeath2": ["вопрос", "варианты", "подсказка", "лимит", "диапазон", "история", "имя", "персонаж"],
    "survivetheinternet": ["вопрос", "ответ", "фото", "зрение", "варианты", "лимит", "история", "имя", "персонаж"],
}

# ======================================================================= English version
SYSTEM_EN = (
    "You are playing the Jackbox game \"{game}\" as {name}. Your personality: {persona}. "
    "You play against other people, answer like a regular player and never explain your answers. "
    "Write in English, keep it short and in your own voice."
)

PROMPTS_EN = {
    "system": SYSTEM_EN,
    "quiplash2": {
        "answer": {
            "title": "Joke", "hint": "Answer to the round prompt", "format": "text", "max_tokens": 60,
            "text": "Prompt: {question}\n\nYour previous answers in this game (do not repeat them):\n{history}\n\n"
                    "Come up with ONE funny, unexpected answer, 45 characters max. "
                    "Write only the answer itself, no quotes, no explanations.",
        },
        "vote": {
            "title": "Vote", "hint": "Pick the funnier of two answers", "format": "choice", "max_tokens": 8,
            "text": "Prompt: {question}\n\nPlayers' answers:\n{options}\n\nWhich answer is funnier? Reply with the number ONLY.",
        },
        "wordlash": {
            "title": "Final: word", "hint": "Answer that must contain the word", "format": "text", "max_tokens": 60,
            "text": "Task: {question}\nYou must use the word \"{word}\".\n"
                    "Come up with a funny answer, 45 characters max. Only the answer.",
        },
        "acrolash": {
            "title": "Final: acronym", "hint": "Funny expansion of the letters", "format": "text", "max_tokens": 40,
            "text": "Make a funny expansion of the acronym {question}: one word per letter, in order. "
                    "Write only the expansion.",
        },
        "comiclash": {
            "title": "Final: comic", "hint": "Last line of the comic", "format": "text", "max_tokens": 60,
            "text": "Comic: {question}\nCome up with a funny last line, 45 characters max. Only the line.",
        },
        "r3vote": {
            "title": "Final: medals", "hint": "Hand out gold, silver, bronze", "format": "ranking", "max_tokens": 20,
            "text": "Final task: {question}\n\nPlayers' answers:\n{options}\n\n"
                    "Rank the answers from funniest to least funny. Reply ONLY with numbers separated by commas.",
        },
    },
    "pollposition": {
        "guess": {
            "title": "Guess the percent", "hint": "Your turn: a number from 0 to 100", "format": "number", "max_tokens": 10,
            "text": "Poll question: \"{question}\"\nWhat percentage of people said yes?\n\n"
                    "Your previous guesses and the real results:\n{history}\n\nReply ONLY with a number from 0 to 100.",
        },
        "updown": {
            "title": "Higher or lower", "hint": "Bet against another player's number", "format": "choice", "max_tokens": 8,
            "text": "Poll: {survey}\nQuestion: \"{question}\"\nAnother player guessed {number}.\n\n"
                    "Your previous guesses and the real results:\n{history}\n\nThe real percentage is:\n{options}\n\n"
                    "Reply with the number ONLY.",
        },
        "multiple": {
            "title": "Final: top 3", "hint": "Pick the most popular options", "format": "choice", "max_tokens": 8,
            "text": "Question: \"{question}\"\n{instruction}\n\nOptions:\n{options}\n\n"
                    "Which option did the most people choose? Reply with the number ONLY.",
        },
        "category": {
            "title": "Topic choice", "hint": "When the bot picks a category", "format": "choice", "max_tokens": 8,
            "text": "Pick the poll topic you like most:\n{options}\n\nReply with the number ONLY.",
        },
    },
    "triviadeath2": {
        "choice": {
            "title": "Question / choice", "hint": "Trivia, \"Rules\", choices in mini-games", "format": "choice", "max_tokens": 8,
            "text": "Situation: {hint}\nQuestion: \"{question}\"\n\nOptions:\n{options}\n\nYour previous moves:\n{history}\n\n"
                    "Your life is at stake, no jokes here: if there is a correct answer, pick it. Reply with the number ONLY.",
        },
        "multiple": {
            "title": "Final: several answers", "hint": "Mark every matching option", "format": "choice", "max_tokens": 16,
            "text": "Situation: {hint}\nTask: \"{question}\"\n\nOptions:\n{options}\n\n"
                    "One, several or all options may fit. "
                    "Reply ONLY with the numbers of all matching options separated by commas, no reasoning.",
        },
        "text": {
            "title": "Text input", "hint": "Quiplash, password, Mind Meld and similar", "format": "text", "max_tokens": 40,
            "text": "Task on the phone: \"{question}\"\nLimit: {limit} characters.\n{hint}\n\n"
                    "Your previous moves:\n{history}\n\nWrite only the answer itself, no quotes, no explanations.",
        },
        "number": {
            "title": "Number (money)", "hint": "Donations, Greed: the game accepts only a number", "format": "number",
            "max_tokens": 10,
            "text": "Task on the phone: \"{question}\"\nAllowed: {range}.\n{hint}\n\n"
                    "Your previous moves:\n{history}\n\nReply ONLY with a single whole number.",
        },
    },
    "survivetheinternet": {
        "response": {
            "title": "About yourself", "hint": "Step one: an honest answer to a personal question", "format": "text",
            "max_tokens": 50,
            "text": "Question about you: \"{question}\"\nLimit: {limit} characters.\n\nAnswer briefly (up to 10 words), "
                    "like a regular person talking about themselves, in your own character. Another player will later "
                    "take your words out of context.\nYour previous answers (do not repeat them):\n{history}\n\n"
                    "Only the answer itself.",
        },
        "twist": {
            "title": "Twist", "hint": "Take someone else's answer out of context", "format": "text", "max_tokens": 60,
            "text": "Another player's answer: \"{answer}\"\nTask: {question}\nLimit: {limit} characters.\n\n"
                    "Come up with a headline, post or situation where this answer looks as ridiculous, embarrassing or "
                    "absurd as possible. Funny and unexpected. Only the text itself.",
        },
        "photo": {
            "title": "Final: photo", "hint": "Caption for a social media photo", "format": "text", "max_tokens": 60,
            "text": "Final round, a photo from social media. {vision}\nIn the photo: {photo}\nTask: {question}\n"
                    "Limit: {limit} characters.\n\n"
                    "Write an absurd caption for this photo that makes its author look weird, creepy or unhinged. "
                    "The joke should build on what is in the photo. Only the caption.",
        },
        "vote": {
            "title": "Vote", "hint": "Pick the most ridiculous post", "format": "choice", "max_tokens": 8,
            "text": "Task: {question}\n\nPosts:\n{options}\n\nWhich post is the funniest and most absurd? Reply with the number ONLY.",
        },
        "choice": {
            "title": "Choice", "hint": "Pick one of the options on screen", "format": "choice", "max_tokens": 8,
            "text": "Task: {question}\n{vision}\nPhoto: {photo}\n\nOptions:\n{options}\n\n"
                    "Pick the option that will be funnier. Reply with the number ONLY.",
        },
    },
}

VARS_EN = {
    "system": ["game", "name", "persona"],
    "quiplash2": ["question", "history", "options", "word", "round", "name", "persona"],
    "pollposition": ["question", "history", "options", "number", "survey", "instruction", "name", "persona"],
    "triviadeath2": ["question", "options", "hint", "limit", "range", "history", "name", "persona"],
    "survivetheinternet": ["question", "answer", "photo", "vision", "options", "limit", "history", "name", "persona"],
}

# ======================================================================= примеры для превью и теста
# Значения переменных, пока игра не идёт: «Промты» показывают по ним, что уйдёт модели.
SAMPLES_RU = {
    "quiplash2": {
        "вопрос": "Худшее, что можно сказать на первом свидании",
        "варианты": "1. Мама уже выбрала имена нашим детям\n2. Счёт делим на троих: ты, я и твоя мама",
        "слово": "КАРТОШКА", "история": "- «Что нельзя говорить стоматологу» → ты ответил «А можно без рук?»",
    },
    "pollposition": {
        "вопрос": "Сколько процентов людей пели в душе на этой неделе?", "опрос": "Опрос 1000 взрослых",
        "число": "42%", "варианты": "1. Больше\n2. Меньше", "инструкция": "Выбери самый популярный ответ",
        "история": "- «Сколько % людей боятся пауков»: ты 30%, было 18% (завысил)",
    },
    "triviadeath2": {
        "вопрос": "Какая планета самая большая в Солнечной системе?", "подсказка": "вопрос викторины",
        "варианты": "1. Сатурн\n2. Юпитер\n3. Нептун\n4. Земля", "лимит": 45, "диапазон": "0–500",
        "история": "- «Столица Австралии» → Канберра",
    },
    "survivetheinternet": {
        "вопрос": "Как ты обычно проводишь выходные?", "ответ": "Сплю до обеда и ем пиццу", "лимит": 80,
        "фото": "A group of people posing for a photo at a funeral", "зрение": "Картинку ты не видишь, вот её описание.",
        "варианты": "1. Новости: «Пожарный спас кота» — коммент: Сплю до обеда и ем пиццу\n"
                    "2. Видео «Как сделать предложение» — коммент: Наконец-то свободен",
        "история": "- «Любимая еда» → гречка с котлетой",
    },
}
SAMPLES_EN = {
    "quiplash2": {
        "вопрос": "The worst thing to say on a first date",
        "варианты": "1. My mom already picked names for our kids\n2. We split the bill three ways: you, me and my mom",
        "слово": "POTATO", "история": "- \"Things you shouldn't tell your dentist\" → you answered \"Can we skip the hands?\"",
    },
    "pollposition": {
        "вопрос": "What percentage of people sang in the shower this week?", "опрос": "A poll of 1000 adults",
        "число": "42%", "варианты": "1. Higher\n2. Lower", "инструкция": "Pick the most popular answer",
        "история": "- \"What % of people are afraid of spiders\": you 30%, real 18% (too high)",
    },
    "triviadeath2": {
        "вопрос": "Which planet is the largest in the Solar System?", "подсказка": "a trivia question",
        "варианты": "1. Saturn\n2. Jupiter\n3. Neptune\n4. Earth", "лимит": 45, "диапазон": "0–500",
        "история": "- \"Capital of Australia\" → Canberra",
    },
    "survivetheinternet": {
        "вопрос": "How do you usually spend your weekends?", "ответ": "Sleeping till noon and eating pizza", "лимит": 80,
        "фото": "A group of people posing for a photo at a funeral",
        "зрение": "You can't see the picture, here is its description.",
        "варианты": "1. News: \"Firefighter saves a cat\" — comment: Sleeping till noon and eating pizza\n"
                    "2. Video \"How to propose\" — comment: Finally free",
        "история": "- \"Favorite food\" → mac and cheese",
    },
}

PROMPTS = {"ru": PROMPTS_RU, "en": PROMPTS_EN}
VARS = {"ru": VARS_RU, "en": VARS_EN}
SAMPLES = {"ru": SAMPLES_RU, "en": SAMPLES_EN}
